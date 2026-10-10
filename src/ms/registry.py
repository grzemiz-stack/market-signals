"""Rejestr modeli: kto odpowiada na pytanie (mistrz), kto czeka (pretendenci), kto jest fallbackiem.

Reguły (stałe; także w docs/DECISIONS.md):
- Częstość bazowa = zawsze fallback dla prob_* (decomp_weekly: decomp_none).
- Awans pretendenta: różnica metryki vs mistrz z ostatnich 6 liczonych miesięcy poza próbą, bootstrap blokowy,
  dolna granica 95% CI > 0 i n >= 100 dni (prob_*; dla decomp: >= 20 tygodni).
- Degradacja mistrza: przez 6 miesięcy gorszy od fallbacku (górna granica CI metryki vs fallback < 0) -> mistrz = fallback.
- Zmiana roli wyłącznie przez regułę albo ręcznie z niepustym reason; rejestr append-only (historia zmian).
- Liczą się tylko miesiące zaczynające się po SELECTION_END (mistrzowie startowi wybrani na okresie testowym 3A).
Szczegóły i interpretacje: docs/ETAP4R-PLAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ms.models.base import Model

SELECTION_END = pd.Timestamp("2026-10-06")
RULE_MONTHS = 6
MIN_N = {"prob_up_5d": 100, "prob_down_5d": 100, "decomp_weekly": 20}
BLOCK = {"prob_up_5d": 5, "prob_down_5d": 5, "decomp_weekly": 4}
N_BOOT = 2000
SEED = 20261006
FALLBACK = {"prob_up_5d": "base_rate", "prob_down_5d": "base_rate", "decomp_weekly": "decomp_none"}
METRIC = {"prob_up_5d": "bss", "prob_down_5d": "bss", "decomp_weekly": "r2_oos"}
ROLES = ("champion", "challenger", "retired", "fallback")
START_REASON = "wybór na okresie testowym 3A (zawyżony przez selekcję)"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS model_registry (
    asset VARCHAR NOT NULL, question VARCHAR NOT NULL, model_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL CHECK (role IN {ROLES}), since TIMESTAMP NOT NULL,
    reason VARCHAR NOT NULL CHECK (length(trim(reason)) > 0));
CREATE TABLE IF NOT EXISTS model_scores (
    asset VARCHAR NOT NULL, question VARCHAR NOT NULL, model_id VARCHAR NOT NULL, month DATE NOT NULL,
    metric VARCHAR NOT NULL, value DOUBLE, ci_lo DOUBLE, ci_hi DOUBLE, n INTEGER,
    PRIMARY KEY (asset, question, model_id, month, metric));
CREATE TABLE IF NOT EXISTS model_trials (
    model_id VARCHAR NOT NULL, params_hash VARCHAR NOT NULL, added_at TIMESTAMP NOT NULL, note VARCHAR,
    PRIMARY KEY (model_id, params_hash));
"""


def init_schema(con) -> None:
    con.execute(SCHEMA)


def _has_table(con, name: str) -> bool:
    return con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]).fetchone()[0] > 0


def now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


# --------------------------------------------------------------------------- próby (do korekty wielokrotnych testów)


def register_trial(con, m: Model, note: str = "") -> bool:
    """Nowa para (model, params_hash) = nowa próba. Zwraca True, gdy dodano."""
    init_schema(con)
    n0 = con.execute("SELECT count(*) FROM model_trials").fetchone()[0]
    con.execute("INSERT INTO model_trials VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING", [m.id, m.params_hash, now(), note])
    return con.execute("SELECT count(*) FROM model_trials").fetchone()[0] > n0


def n_trials(con, question_prefix: str = "") -> int:
    return con.execute("SELECT count(*) FROM model_trials").fetchone()[0]


# --------------------------------------------------------------------------- role


def set_role(con, asset: str, question: str, model_id: str, role: str, reason: str, since=None) -> None:
    if not reason or not reason.strip():
        raise ValueError("zmiana roli wymaga reason")
    con.execute("INSERT INTO model_registry VALUES (?, ?, ?, ?, ?, ?)",
                [asset, question, model_id, role, since or now(), reason])


def roles(con, asset: str | None = None, question: str | None = None) -> pd.DataFrame:
    """Bieżąca rola = ostatni wpis dla (aktywo, pytanie, model). Odczyt nic nie tworzy (działa na read-only);
    brak tabeli = pusty rejestr (champion() użyje fallbacku)."""
    if not _has_table(con, "model_registry"):
        return pd.DataFrame(columns=["asset", "question", "model_id", "role", "since", "reason"])
    df = con.execute("""SELECT * FROM model_registry
                        QUALIFY row_number() OVER (PARTITION BY asset, question, model_id ORDER BY since DESC, rowid DESC) = 1""").df()
    if asset:
        df = df[df.asset == asset]
    if question:
        df = df[df.question == question]
    return df


def initialize(con, models: list[Model], champions: dict[tuple[str, str], str]) -> int:
    """Start rejestru (gdy pusty): mistrzowie z 3A, fallback, reszta pretendentami. Zwraca liczbę wpisów."""
    init_schema(con)
    if con.execute("SELECT count(*) FROM model_registry").fetchone()[0]:
        return 0
    t0, n = now(), 0
    for m in models:
        register_trial(con, m, "start rejestru")
        for a in m.assets:
            if m.question == "event_response":
                continue
            champ = champions.get((a, m.question))
            if m.id == FALLBACK[m.question]:
                role, reason = "fallback", "reguła: fallback zawsze"
            elif m.id == champ:
                role, reason = "champion", START_REASON
            else:
                role, reason = "challenger", "start rejestru"
            set_role(con, a, m.question, m.id, role, reason, t0)
            n += 1
    return n


# --------------------------------------------------------------------------- ocena


def daily_frame(pred: pd.Series, truth: pd.DataFrame, base: pd.Series | None) -> pd.DataFrame:
    df = pd.DataFrame({"p": pred}).join(truth, how="inner")
    if base is not None:
        df = df.join(base.rename("b"), how="inner")
    return df.dropna()


def metric_value(df: pd.DataFrame, question: str, pcol: str = "p", bcol: str = "b") -> float:
    if question.startswith("prob_"):
        bb = ((df[bcol] - df["y"]) ** 2).mean()
        return float(1 - ((df[pcol] - df["y"]) ** 2).mean() / bb) if bb > 0 else np.nan
    sst = ((df["y"] - df["y"].mean()) ** 2).sum()
    return float(1 - ((df["y"] - df[pcol]) ** 2).sum() / sst) if sst > 0 else np.nan


def block_ci(df: pd.DataFrame, stat, block: int, n: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    if len(df) < 2 * block:
        return np.nan, np.nan
    df = df.sort_index()
    blocks = np.arange(len(df)) // block
    ids = np.unique(blocks)
    groups = {b: np.where(blocks == b)[0] for b in ids}
    rng = np.random.default_rng(seed)
    vals = [stat(df.iloc[np.concatenate([groups[b] for b in rng.choice(ids, len(ids))])]) for _ in range(n)]
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def month_slice(df: pd.DataFrame, month: pd.Timestamp) -> pd.DataFrame:
    """Dni, których etykieta rozstrzyga się w miesiącu (resolved_at w [M, M+1)) — nic po końcu M."""
    end = month + pd.offsets.MonthBegin(1)
    return df[(df["resolved_at"] >= month) & (df["resolved_at"] < end)]


def score_month(df: pd.DataFrame, question: str, month: pd.Timestamp) -> dict:
    sub = month_slice(df, month)
    v = metric_value(sub, question) if len(sub) else np.nan
    lo, hi = block_ci(sub, lambda x: metric_value(x, question), BLOCK[question]) if len(sub) else (np.nan, np.nan)
    return {"metric": METRIC[question], "value": v, "ci_lo": lo, "ci_hi": hi, "n": len(sub)}


def rule_months(last_month: pd.Timestamp) -> list[pd.Timestamp]:
    """6 ostatnich pełnych miesięcy, tylko te zaczynające się po SELECTION_END."""
    months = [last_month - pd.DateOffset(months=k) for k in range(RULE_MONTHS)]
    return sorted(m for m in months if m > SELECTION_END)


def window_slice(df: pd.DataFrame, months: list[pd.Timestamp]) -> pd.DataFrame:
    return pd.concat([month_slice(df, m) for m in months]) if months else df.iloc[0:0]


# --------------------------------------------------------------------------- reguły


@dataclass
class Change:
    asset: str
    question: str
    model_id: str
    old_role: str
    new_role: str
    reason: str


def decide(question: str, champion: str, frames: dict[str, pd.DataFrame], months: list[pd.Timestamp]) -> tuple[list[tuple], dict]:
    """Czysta funkcja reguł (deterministyczna). frames: model_id -> dzienna ramka (p, y, resolved_at[, b]).
    Zwraca (lista (model_id, nowa_rola, reason), diagnostyka)."""
    diag: dict = {"months": len(months)}
    if len(months) < RULE_MONTHS:
        diag["note"] = f"za mało miesięcy poza próbą: {len(months)}/{RULE_MONTHS}"
        return [], diag
    fb = FALLBACK[question]
    win = {m: window_slice(f, months) for m, f in frames.items()}
    ch = win.get(champion)
    # degradacja: mistrz vs fallback
    if champion != fb and ch is not None and len(ch) >= MIN_N[question]:
        if question.startswith("prob_"):
            stat = lambda x: metric_value(x, question)  # noqa: E731  BSS vs częstość bazowa (= fallback)
        else:
            stat = lambda x: metric_value(x, question)  # noqa: E731  R² vs średnia (= fallback)
        lo, hi = block_ci(ch, stat, BLOCK[question])
        diag["champion_vs_fallback"] = (metric_value(ch, question), lo, hi)
        if hi < 0:
            return [(fb, "champion", f"reguła degradacji: {champion} gorszy od fallbacku przez {RULE_MONTHS} mies., "
                                     f"CI [{lo:+.3f}; {hi:+.3f}]"),
                    (champion, "challenger", "reguła degradacji")], diag
    # awans: pretendent vs mistrz na wspólnych dniach
    best = None
    for m, f in win.items():
        if m in (champion,) or ch is None:
            continue
        both = f.join(ch[["p"]].rename(columns={"p": "pc"}), how="inner")
        if len(both) < MIN_N[question]:
            continue
        diff = lambda x: metric_value(x, question, "p") - metric_value(x, question, "pc")  # noqa: E731
        lo, hi = block_ci(both, diff, BLOCK[question])
        d = diff(both)
        diag[f"diff:{m}"] = (d, lo, hi, len(both))
        if lo > 0 and (best is None or d > best[1]):
            best = (m, d, lo, hi, len(both))
    if best:
        m, d, lo, hi, n = best
        return [(m, "champion", f"reguła awansu: +{d:.3f} vs {champion}, CI [{lo:+.3f}; {hi:+.3f}], n={n}"),
                (champion, "challenger", f"reguła awansu: zastąpiony przez {m}")], diag
    return [], diag


def apply(con, asset: str, question: str, decisions: list[tuple]) -> list[Change]:
    cur = roles(con, asset, question).set_index("model_id")["role"].to_dict()
    out = []
    for model_id, role, reason in decisions:
        if cur.get(model_id) != role:
            set_role(con, asset, question, model_id, role, reason)
            out.append(Change(asset, question, model_id, cur.get(model_id, "—"), role, reason))
    return out


# --------------------------------------------------------------------------- API dla UI


@dataclass
class Champion:
    asset: str
    question: str
    model_id: str
    role: str
    since: pd.Timestamp
    reason: str
    metric: str
    value: float
    ci_lo: float
    ci_hi: float
    score_source: str
    card: str


def _pl(x, fmt):
    return "—" if x is None or not np.isfinite(x) else format(x, fmt).replace(".", ",")


def champion(con, asset: str, question: str) -> Champion:
    """Mistrz pytania; gdy brak mistrza -> fallback. Wynik: ostatnie 6 liczonych miesięcy z model_scores,
    a gdy jeszcze ich nie ma — wynik startowy z 3A (oznaczony jako zawyżony przez selekcję)."""
    from ms.models.catalog import display

    r = roles(con, asset, question)
    ch = r[r.role == "champion"]
    if ch.empty:
        ch = r[r.role == "fallback"]
    if ch.empty:
        fb = FALLBACK.get(question)
        row = pd.Series({"model_id": fb, "role": "fallback", "since": pd.NaT, "reason": "brak wpisu w rejestrze"})
    else:
        row = ch.sort_values("since").iloc[-1]
    mid = row["model_id"]
    metric = METRIC.get(question, "")
    sc = (con.execute("""SELECT value, ci_lo, ci_hi, month FROM model_scores WHERE asset=? AND question=? AND model_id=?
                         AND month > ? ORDER BY month DESC LIMIT ?""", [asset, question, mid, SELECTION_END.date(), RULE_MONTHS]).df()
          if _has_table(con, "model_scores") else pd.DataFrame())
    if len(sc):
        v, lo, hi = sc["value"].mean(), sc["ci_lo"].mean(), sc["ci_hi"].mean()
        src = f"średnia z {len(sc)} mies. poza próbą (CI: średnie miesięcznych)"
    else:
        v = lo = hi = np.nan
        src = "brak miesięcy poza próbą"
        if question.startswith("prob_") and mid != "base_rate":
            e = con.execute("SELECT bss, ci_lo, ci_hi FROM baseline_eval WHERE aktywo=? AND model=? AND wariant='wszystkie'",
                            [asset, mid]).fetchone()
            if e:
                v, lo, hi = e
                src = "3A, okres selekcji (zawyżony przez selekcję)"
    name = display(mid, asset)
    since = row["since"]
    since_txt = since.date() if isinstance(since, pd.Timestamp) and not pd.isna(since) else "—"
    if question.startswith("prob_"):
        if mid == "base_rate":
            edge = "to jest częstość bazowa (fallback)"
        else:
            edge = f"Przewaga nad częstością bazową: BSS {_pl(v, '+.3f')} [{_pl(lo, '+.3f')}; {_pl(hi, '+.3f')}] ({src})"
    else:
        edge = f"R² poza próbą: {_pl(v, '+.3f')} [{_pl(lo, '+.3f')}; {_pl(hi, '+.3f')}] ({src})"
    role_txt = "Mistrz" if row["role"] == "champion" else "Fallback"
    card = f"Odpowiada: {name}. {edge}. {role_txt} od: {since_txt}."
    return Champion(asset, question, mid, row["role"], since, row["reason"], metric, v, lo, hi, src, card)

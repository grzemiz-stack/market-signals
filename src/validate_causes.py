"""Etap 4N: walidacja klasyfikatora Qwen (E1–E4) wg docs/ETAP4N-WALIDACJA-PLAN.md. Tylko lokalnie (ms.llm, 127.0.0.1).

uv run src/validate_causes.py start --model M     # wpis próby w runs (stage 4N-val), prompt v1 zamrożony hashem
uv run src/validate_causes.py e1 --model M        # BBDS 1950–2022 (492 jednostki); wznawialne
uv run src/validate_causes.py e4 --model M        # 42 dni kalendarza (FOMC/OPEC/hack/ETF) z slugami GDELT; wznawialne
uv run src/validate_causes.py e3 --model M        # epizody (ref/oil_episodes.csv) + wariant zamaskowany (E3m)
uv run src/validate_causes.py report              # miary + progi -> reports/move-causes-validation-<data>.md

Wyniki pozycji: data/validation.duckdb (osobna baza — wielogodzinne przebiegi nie blokują market.duckdb).
E2 (etykiety użytkownika) i E3 (epizody z literatury) — dopisywane, gdy złoto będzie gotowe; bez nich validated = false.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import classify as C, db, llm  # noqa: E402

VAL_DB = db.ROOT / "data" / "validation.duckdb"
STAGE = "4N-val"
E1_YEARS = (1950, 2022)
E4_SOURCES = {"fomc": "monetary", "opec": "oil_supply", "defillama": "crypto_hack", "manual": None}   # manual: tylko ETF
E4_MAX_ITEMS = 600
THRESHOLDS = {"E1_kappa": 0.695, "E2_acc": 0.75, "E2_kappa": 0.60, "E3_hits": 14, "E4_agree": 0.60}
THRESHOLD_COMMIT = "d488231"   # commit z κ_ludzie i progiem E1 w DECISIONS (przed pierwszym uruchomieniem modelu)
# Kopia publiczna ma czystą historię (bez tego commita) — czas commita z historii prywatnej, gdy git go nie zna:
THRESHOLD_COMMITTED_AT = "2026-10-07T09:55:36Z"
# E3 = kontrola, nie bramka (decyzja 2026-10-07: n małe); validated wymaga E1, E2 (+ wariant zamaskowany) i E4.

SCHEMA = """
CREATE TABLE IF NOT EXISTS val_items (run_id VARCHAR, set_name VARCHAR, item_id VARCHAR, gold VARCHAR, pred VARCHAR,
    pred_secondary VARCHAR, confidence VARCHAR, evidence VARCHAR, raw VARCHAR, seconds DOUBLE, done_at TIMESTAMP,
    PRIMARY KEY (run_id, set_name, item_id));
"""


def run_id(model: str) -> str:
    """Próba = (model, wersja promptu). Hash promptu w runs.params; zmiana przed E2 (2026-10-07) = ta sama próba."""
    return f"4N-val-{model.replace(':', '_')}-{C.PROMPT_VERSION}"


def vcon():
    con = duckdb.connect(str(VAL_DB))
    con.execute(SCHEMA)
    return con


def start(model: str) -> str:
    """Wpis próby w runs (market.duckdb). Ta sama (model, prompt) = ta sama próba (bez duplikatu). Limit 3 próby."""
    rid = run_id(model)
    m = db.connect()
    row = m.execute("SELECT params FROM runs WHERE run_id=?", [rid]).fetchone()
    if row:
        p = json.loads(row[0])
        if p["prompt_hash"] != C.prompt_hash():
            v = vcon()
            if v.execute("SELECT count(*) FROM val_items WHERE run_id=? AND set_name IN ('E2', 'E2m')", [rid]).fetchone()[0]:
                raise SystemExit("prompt zmieniony PO przebiegu E2 — to byłaby nowa próba (wpis w DECISIONS, limit 3)")
            p.setdefault("historia_promptu", []).append({"hash": p["prompt_hash"], "do": str(pd.Timestamp.now()),
                                                         "powod": "definicje kodów doprecyzowane przed E2 (DECISIONS 2026-10-07)"})
            p["prompt_hash"] = C.prompt_hash()
            m.execute("UPDATE runs SET params=? WHERE run_id=?", [json.dumps(p), rid])
            print(f"próba {rid}: prompt zaktualizowany przed E2 -> {p['prompt_hash']} (ta sama próba)")
        else:
            print(f"próba {rid} już jest")
        return rid
    n = m.execute("SELECT count(*) FROM runs WHERE stage=?", [STAGE]).fetchone()[0]
    if n >= 3:
        raise SystemExit("limit 3 prób etapu 4N wyczerpany — raport „nie da się wiarygodnie”, bez dalszego strojenia")
    m.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
              [rid, pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s"), "ALL", STAGE,
               json.dumps({"model": model, "digest": llm.model_digest(model), "prompt_version": C.PROMPT_VERSION,
                           "prompt_hash": C.prompt_hash(), "options": C.OPTIONS, "progi": THRESHOLDS}), 0,
               f"walidacja E1–E4, próba {n + 1}/3"])
    print(f"zapisano próbę {rid} ({n + 1}/3)")
    return rid


# --------------------------------------------------------------------------- zbiory


def e1_units(mcon) -> pd.DataFrame:
    b = mcon.execute("SELECT date, row_no, coder, primary_cat, passage FROM bbds_codings WHERE year(date) BETWEEN ? AND ?",
                     list(E1_YEARS)).df()
    b["gold"] = b["primary_cat"].map(C.bbds_map())
    b = b.dropna(subset=["gold", "passage"])
    b["item_id"] = b["date"].astype(str) + "|" + b["coder"].astype(str) + "|" + b["row_no"].astype(str)
    return b.sort_values("item_id")


def e4_days(mcon) -> pd.DataFrame:
    mc = mcon.execute("""SELECT day, cause, source_ref FROM move_causes WHERE day >= DATE '2015-02-18'""").df()
    mc["src"] = mc["source_ref"].str.split(":").str[0]
    keep = mc[mc["src"].isin(["fomc", "opec", "defillama"]) | ((mc["src"] == "manual") & (mc["cause"] == "crypto_etf"))]
    return keep.groupby("day")["cause"].apply(lambda s: sorted(set(s))).reset_index()


def slug(url: str) -> str:
    p = urllib.parse.urlsplit(url or "").path.rstrip("/").split("/")
    s = max(p, key=len) if p else ""
    s = re.sub(r"\.(html?|php|aspx?)$", "", s)
    s = re.sub(r"[-_+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def e4_text(gcon, day) -> list[str]:
    d = pd.Timestamp(day)
    lo, hi = d - pd.Timedelta(hours=2), d + pd.Timedelta(hours=22)
    ev = gcon.execute("""SELECT source_url, max(num_mentions) m FROM events WHERE known_at > ? AND known_at <= ?
                         AND NOT (coalesce(actor1_country,'')='USA' AND coalesce(actor2_country,'')='USA')
                         GROUP BY 1 ORDER BY m DESC LIMIT ?""", [lo.to_pydatetime(), hi.to_pydatetime(), E4_MAX_ITEMS]).df()
    out = []
    for u in ev["source_url"]:
        s = slug(u)
        if len(s) >= 12 and not s.isdigit() and s not in out:
            out.append(s)
    return out


# --------------------------------------------------------------------------- przebiegi


def _run_items(model: str, set_name: str, items: list[tuple[str, str, list[str]]], codes: list[str], examples) -> None:
    rid = run_id(model)
    v = vcon()
    done = {r[0] for r in v.execute("SELECT item_id FROM val_items WHERE run_id=? AND set_name=?", [rid, set_name]).fetchall()}
    todo = [it for it in items if it[0] not in done]
    print(f"{set_name} {model}: do zrobienia {len(todo)} z {len(items)}", flush=True)
    for k, (iid, gold, text) in enumerate(todo, 1):
        t0 = time.time()
        out = C.classify(model, text, codes, examples)
        v.execute("INSERT INTO val_items VALUES (?,?,?,?,?,?,?,?,?,?,now()::TIMESTAMP)",
                  [rid, set_name, iid, gold, out.get("cause"), out.get("cause_secondary"), out.get("confidence"),
                   json.dumps(out.get("evidence_ids")), out.get("raw"), time.time() - t0])
        if k % 25 == 0:
            print(f"  {k}/{len(todo)} ({time.time() - t0:.1f} s/poz.)", flush=True)


def run_e1(model: str) -> None:
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    u = e1_units(m)
    ex = C.bbds_fewshots(m)
    m.close()
    codes = sorted(set(C.bbds_map().values()))
    _run_items(model, "E1", [(r.item_id, r.gold, [r.passage.strip()]) for r in u.itertuples()], codes, ex)


def run_e4(model: str) -> None:
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    days = e4_days(m)
    m.close()
    g = duckdb.connect(str(db.GDELT_PATH), read_only=True)
    items = [(str(pd.Timestamp(r.day).date()), "|".join(r.cause), e4_text(g, r.day)) for r in days.itertuples()]
    g.close()
    codes = taxonomy_codes()
    _run_items(model, "E4", items, codes, all_fewshots())


def all_fewshots() -> list[tuple[str, str]]:
    """Plan 4N pkt 4: przykłady BBDS (tylko 1900–1949) + po 2 na każde rozszerzenie — dla zadań na pełnej taksonomii."""
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    try:
        return C.bbds_fewshots(m) + C.ext_fewshots()
    finally:
        m.close()


E2_FILE = db.ROOT / "ref" / "e2_wgc_gold.csv"   # lokalnie, poza gitem: uv run src/e2_wgc_restore.py (z ref/e2_wgc_index.csv)


def run_e2(model: str) -> None:
    """E2: cytat WGC -> kod (wzorzec: mapowanie wg ref/e2_wgc_rules.md, zamrożone przed przebiegiem) + wariant zamaskowany."""
    chk = db.ROOT / "ref" / "e2_wgc_check20_agent.csv"          # niezależna kontrola 20 wierszy (decyzja 2026-10-07)
    if not chk.exists():
        raise SystemExit("E2 wstrzymane: brak wyniku niezależnej kontroli (ref/e2_wgc_check20_agent.csv)")
    nie = int((pd.read_csv(chk, comment="#")["TAK/NIE"].str.upper() == "NIE").sum())
    if nie > 3:
        raise SystemExit(f"E2 wstrzymane: niezależna kontrola NIE = {nie} > 3 — decyzja użytkownika")
    if not E2_FILE.exists():
        raise SystemExit(f"brak {E2_FILE} — cytaty WGC nie są w repo; zapisz strony i uruchom: uv run src/e2_wgc_restore.py")
    g = pd.read_csv(E2_FILE, comment="#")
    g = g[g["wlaczony"] == "tak"]
    codes, ex = taxonomy_codes(), all_fewshots()
    _run_items(model, "E2", [(r.miesiac, r.kod, [r.cytat]) for r in g.itertuples()], codes, ex)
    _run_items(model, "E2m", [(r.miesiac, r.kod, mask([r.cytat])) for r in g.itertuples()], codes, ex)


def taxonomy_codes() -> list[str]:
    return C.taxonomy()["code"].tolist()


E4H_DB = db.ROOT / "data" / "gdelt_e4.duckdb"
E4H_MAX = 600


def e4hist_rows(gcon, day) -> pd.DataFrame:
    """E4-hist (plan 4N E4 pkt 7): adresy z export (SOURCEURL) ∪ mentions (web) z okna [D−1 22:00, D 22:00] UTC, zdarzenia
    przez GlobalEventID; ranking max NumMentions malejąco, remis URL rosnąco. Bez filtra konfliktów i bez filtra USA–USA."""
    d = pd.Timestamp(day)
    lo, hi = (d - pd.Timedelta(hours=2)).to_pydatetime(), (d + pd.Timedelta(hours=22)).to_pydatetime()
    return gcon.execute("""
        WITH pool AS (
            SELECT source_url AS url, event_id FROM ev WHERE dateadded > ? AND dateadded <= ?
            UNION ALL
            SELECT url, event_id FROM men WHERE mention_type = 1 AND mention_time > ? AND mention_time <= ?),
        j AS (SELECT p.url, e.event_code, e.a1c, e.a2c, e.num_mentions
              FROM pool p LEFT JOIN (SELECT DISTINCT ON (event_id) * FROM ev) e ON e.event_id = p.event_id)
        SELECT url, arg_max(event_code, num_mentions) AS code, arg_max(a1c, num_mentions) AS a1c,
               arg_max(a2c, num_mentions) AS a2c, max(num_mentions) AS m
        FROM j GROUP BY url ORDER BY m DESC NULLS LAST, url ASC""", [lo, hi, lo, hi]).df()


def e4hist_text(gcon, day) -> tuple[list[str], float]:
    """(pozycje „slug | CAMEO kod A1→A2” — najwyżej 600, odsetek par USA–USA wśród nich — diagnostyka)."""
    out, seen, usa = [], set(), 0
    for r in e4hist_rows(gcon, day).itertuples():
        sl = slug(r.url)
        if len(sl) < 12 or sl.isdigit() or sl in seen:
            continue
        seen.add(sl)
        cam = f"CAMEO {r.code} {r.a1c or '—'}→{r.a2c or '—'}" if isinstance(r.code, str) else "CAMEO ?"
        usa += int(r.a1c == "USA" and r.a2c == "USA")
        out.append(f"{sl} | {cam}")
        if len(out) >= E4H_MAX:
            break
    return out, (usa / len(out) if out else np.nan)


def run_e4hist(model: str) -> None:
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    days = e4_days(m)
    m.close()
    g = duckdb.connect(str(E4H_DB), read_only=True)
    items, diag = [], {}
    for r in days.itertuples():
        txt, usa = e4hist_text(g, r.day)
        diag[str(pd.Timestamp(r.day).date())] = usa
        items.append((str(pd.Timestamp(r.day).date()), "|".join(r.cause), txt))
    g.close()
    (db.ROOT / "logs" / "e4hist_usa_usa.json").write_text(json.dumps(diag))
    _run_items(model, "E4h", items, taxonomy_codes(), all_fewshots())


E3_FILE = db.ROOT / "ref" / "oil_episodes.csv"
MASK_FILE = db.ROOT / "ref" / "mask_terms.csv"
MONTHS = r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\b"


def mask(texts: list[str]) -> list[str]:
    """Kraje/regiony/organizacje -> [KRAJ_A], [REGION_A], [ORGANIZACJA_A] (spójnie w obrębie zestawu), bez lat i miesięcy."""
    terms = pd.read_csv(MASK_FILE, comment="#")
    terms = terms.iloc[terms["term"].str.len().argsort()[::-1]]       # najdłuższe najpierw („Saudi Arabia” przed „Saudi”)
    ids: dict[tuple[str, str], str] = {}
    out = []
    for t in texts:
        for term, kind, ent in zip(terms["term"], terms["kind"], terms["entity"]):
            def rep(_m, ent=ent, kind=kind):
                key = (kind, ent.lower())                              # „Saudi” i „Saudi Arabia” -> ten sam znacznik
                if key not in ids:
                    ids[key] = f"[{kind}_{chr(65 + sum(1 for k in ids if k[0] == kind))}]"
                return ids[key]
            t = re.sub(rf"(?<![\w.]){re.escape(term)}(?![\w])", rep, t)
        t = re.sub(r"\b(1[89]\d\d|20\d\d)s?\b", "", t)
        t = re.sub(MONTHS, "", t)
        out.append(re.sub(r"\s+", " ", t).strip())
    return out


def e3_items(mcon, masked: bool) -> list[tuple[str, str, list[str]]]:
    ep = pd.read_csv(E3_FILE, comment="#")
    ev = mcon.execute("""SELECT event_date, text FROM cause_events WHERE source IN ('eia_chron', 'wiki_chron')
                         ORDER BY event_date""").df()
    ev["event_date"] = pd.to_datetime(ev["event_date"])
    items = []
    for r in ep.itertuples():
        lo = pd.Timestamp(r.start + "-01")
        hi = pd.Timestamp(r.end + "-01") + pd.offsets.MonthEnd(0)
        if hi > ev.event_date.max() + pd.offsets.MonthEnd(0):
            continue                                       # okno wychodzi poza chronologię (do 2003) -> wejście byłoby niepełne
        texts = ev.loc[(ev.event_date >= lo) & (ev.event_date <= hi), "text"].tolist()   # bez dat (nie przekazujemy)
        if not texts:
            continue
        gold = r.dominant_cause if r.disputed == "nie" else f"SPORNY:{r.cause_hamilton}|{r.cause_bk}"
        items.append((str(r.episode_id), gold, mask(texts) if masked else texts))
    return items


def run_e3(model: str) -> None:
    if not E3_FILE.exists():
        raise SystemExit("brak ref/oil_episodes.csv — złoto E3 musi być w commicie przed uruchomieniem")
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    plain, masked = e3_items(m, False), e3_items(m, True)
    m.close()
    codes = list(C.E3_CODES)
    _run_items(model, "E3", plain, codes, [])
    _run_items(model, "E3m", masked, codes, [])


# --------------------------------------------------------------------------- raport


def _check_summary() -> str:
    f = db.ROOT / "ref" / "e2_wgc_check20_agent.csv"
    if not f.exists():
        return "brak"
    c = pd.read_csv(f, comment="#")
    return f"NIE = {int((c['TAK/NIE'].str.upper() == 'NIE').sum())} z {len(c)} (bramka: ≤ 3); runda 1: NIE = 7 → kierunek A"


def _e2_conventions(e2: pd.DataFrame) -> list[str]:
    """Ile wierszy wzorca zależy od konwencji (zapisanych od 2026-10-07 w definicjach kodów) i trafność w obu grupach."""
    if not E2_FILE.exists():
        raise SystemExit(f"brak {E2_FILE} — cytaty WGC nie są w repo; zapisz strony i uruchom: uv run src/e2_wgc_restore.py")
    g = pd.read_csv(E2_FILE, comment="#")
    g = g[g["wlaczony"] == "tak"].set_index("miesiac")["konwencja"].fillna("")
    x = e2.assign(konw=e2["item_id"].map(g).fillna(""), hit=e2["gold"] == e2["pred"])
    out = [f"Wiersze wzorca zależne od konwencji: **{int((g != '').sum())} z {len(g)}** "
           f"({', '.join(f'{k}: {v}' for k, v in g[g != ''].value_counts().items())}). Konwencje są w definicjach kodów "
           "(ref/taxonomy.csv, kolumna prompt) — model je widzi.", ""]
    for nm, sub in (("zależne od konwencji", x[x.konw != ""]), ("niezależne", x[x.konw == ""])):
        out.append(f"- {nm}: trafienia {int(sub.hit.sum())}/{len(sub)}" + (f" ({sub.hit.mean():.3f})" if len(sub) else ""))
    return out


def kappa(a, b) -> float:
    from sklearn.metrics import cohen_kappa_score

    return float(cohen_kappa_score(a, b))


def boot_by_day(df: pd.DataFrame, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    df = df.assign(day=df["item_id"].str.split("|").str[0])
    groups = [g for _, g in df.groupby("day")]
    ks = []
    for _ in range(n):
        s = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        ks.append(kappa(s["gold"], s["pred"].fillna("BRAK")))
    return float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def report() -> Path:
    v = vcon()
    df = v.execute("SELECT * FROM val_items").df()
    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    runs = m.execute("SELECT run_id, params FROM runs WHERE stage=? ORDER BY started_at", [STAGE]).df()
    L = [f"# Walidacja klasyfikatora przyczyn (Qwen, lokalnie) — {date.today()}", "",
         "Plan i progi: docs/ETAP4N-WALIDACJA-PLAN.md (progi z 2026-10-06, κ_ludzie z 2026-10-07 przed uruchomieniem). "
         "`validated = true` tylko gdy E1, E2 (z wariantem zamaskowanym) i E4 przeszły; E3 to kontrola (decyzja 2026-10-07).", ""]
    import subprocess

    git_t = subprocess.run(["git", "log", "-1", "--format=%cI", THRESHOLD_COMMIT], capture_output=True, text=True,
                           cwd=db.ROOT).stdout.strip()
    thr_at = pd.Timestamp(git_t or THRESHOLD_COMMITTED_AT).tz_convert(None)    # UTC
    summary = []
    for r in runs.itertuples():
        p = json.loads(r.params)
        L += [f"## {p['model']} (digest {p['digest'][:12]}, prompt {p['prompt_version']} {p['prompt_hash']})", ""]
        d = df[df.run_id == r.run_id]
        first = pd.Timestamp(d["done_at"].min()).tz_localize("Europe/Warsaw").tz_convert(None) if len(d) else None
        L += ["**Progi akceptacji i kiedy zapisane:**", "",
              f"- E1: κ(model, człowiek) ≥ {THRESHOLDS['E1_kappa']} = max(0,60; κ_ludzie 0,795 − 0,10); reguła z planu 4N "
              f"(2026-10-06), wartość w DECISIONS i commicie `{THRESHOLD_COMMIT}` ({thr_at} UTC).",
              f"- E4: zgodność z kalendarzem ≥ {THRESHOLDS['E4_agree']} (plan 4N, 2026-10-06).",
              f"- Pierwsza odpowiedź modelu w walidacji: {first} UTC → progi zapisane "
              f"**{'PRZED' if thr_at is not None and first is not None and thr_at < first else 'PO — UWAGA'}** przebiegami.", ""]
        verdict = {}
        e1 = d[d.set_name == "E1"]
        if len(e1):
            ok = e1["pred"].notna()
            k = kappa(e1["gold"], e1["pred"].fillna("BRAK"))
            lo, hi = boot_by_day(e1)
            acc = float((e1["gold"] == e1["pred"]).mean())
            verdict["E1"] = k >= THRESHOLDS["E1_kappa"]
            L += [f"**E1 (BBDS 1950–2022, n = {len(e1)}, bez odpowiedzi {int((~ok).sum())})**: dokładność {acc:.3f}, "
                  f"κ {k:.3f} [{lo:.3f}; {hi:.3f}] — próg κ ≥ {THRESHOLDS['E1_kappa']} → "
                  f"**{'ZALICZONE' if verdict['E1'] else 'NIEZALICZONE'}**", "",
                  "Macierz pomyłek (wiersze: człowiek, kolumny: model):", "",
                  pd.crosstab(e1["gold"], e1["pred"].fillna("BRAK")).to_markdown(), ""]
        e4 = d[d.set_name == "E4"]
        if len(e4):
            hit = [p_ in g.split("|") for p_, g in zip(e4["pred"], e4["gold"])]
            k_, n_ = int(sum(hit)), len(e4)
            lo, hi = wilson(k_, n_)
            verdict["E4"] = k_ / n_ >= THRESHOLDS["E4_agree"]
            L += [f"**E4 (dni kalendarza 2015–2026, n = {n_})**: zgodność {k_}/{n_} = {k_ / n_:.3f} [Wilson {lo:.3f}; {hi:.3f}] — "
                  f"próg ≥ {THRESHOLDS['E4_agree']} → **{'ZALICZONE' if verdict['E4'] else 'NIEZALICZONE'}**", "",
                  pd.crosstab(e4["gold"], e4["pred"].fillna("BRAK")).to_markdown(), ""]
        e4h = d[d.set_name == "E4h"]
        if len(e4h):
            hit = [p_ in g.split("|") for p_, g in zip(e4h["pred"], e4h["gold"])]
            k_, n_ = int(sum(hit)), len(e4h)
            lo, hi = wilson(k_, n_)
            verdict["E4-hist"] = k_ / n_ >= THRESHOLDS["E4_agree"]
            diag = json.loads((db.ROOT / "logs" / "e4hist_usa_usa.json").read_text()) if (db.ROOT / "logs" / "e4hist_usa_usa.json").exists() else {}
            dd = pd.Series({k: v for k, v in diag.items()}).reindex(e4h["item_id"].values)
            L += [f"**E4-hist (pełne GDELT 2.0 export + mentions, 42 dni, n = {n_})**: zgodność {k_}/{n_} = {k_ / n_:.3f} "
                  f"[Wilson {lo:.3f}; {hi:.3f}] — próg ≥ {THRESHOLDS['E4_agree']} → **{'ZALICZONE' if verdict['E4-hist'] else 'NIEZALICZONE'}**",
                  f"Diagnostyka (bez wpływu na wynik): odsetek pozycji USA–USA wśród wybranych — mediana {dd.median():.2f}.", "",
                  pd.crosstab(e4h["gold"], e4h["pred"].fillna("BRAK")).to_markdown(), ""]
        e3, e3m = d[d.set_name == "E3"], d[d.set_name == "E3m"]
        if len(e3):
            m3 = e3m.set_index("item_id")["pred"]
            cnt = e3[~e3["gold"].str.startswith("SPORNY")]
            dis = e3[e3["gold"].str.startswith("SPORNY")]
            h = int((cnt["gold"] == cnt["pred"]).sum())
            hm = int((cnt["gold"] == m3.reindex(cnt["item_id"]).values).sum())
            drop = h / len(cnt) - hm / len(cnt) if len(cnt) else np.nan
            verdict["E3 (kontrola)"] = f"{h}/{len(cnt)}"
            L += ["### E3 — kontrola (nie bramka; decyzja 2026-10-07: n małe)", "",
                  f"Epizody liczone (bez spornych): {h}/{len(cnt)} trafień; wariant zamaskowany {hm}/{len(cnt)}; spadek {drop:+.2f} "
                  "(sygnał odpowiadania z pamięci, gdy > 0,15).", "",
                  pd.DataFrame({"epizod": cnt["item_id"].values, "literatura": cnt["gold"].values, "model": cnt["pred"].values,
                                "model (zamaskowany)": m3.reindex(cnt["item_id"]).values}).to_markdown(index=False), "",
                  "Epizody sporne (poza metryką) — odpowiedź modelu obok obu wersji ze źródeł:", "",
                  pd.DataFrame({"epizod": dis["item_id"].values,
                                "Hamilton (2011)": dis["gold"].str.split(":").str[1].str.split("|").str[0].values,
                                "Baumeister–Kilian (2016)": dis["gold"].str.split("|").str[1].values,
                                "model": dis["pred"].values, "model (zamaskowany)": m3.reindex(dis["item_id"]).values}
                               ).to_markdown(index=False), ""]
        e2, e2m = d[d.set_name == "E2"], d[d.set_name == "E2m"]
        if len(e2):
            res = {}
            for nm, x in (("zwykły", e2), ("zamaskowany", e2m)):
                acc = float((x["gold"] == x["pred"]).mean()) if len(x) else np.nan
                k = kappa(x["gold"], x["pred"].fillna("BRAK")) if len(x) else np.nan
                res[nm] = (acc, k, len(x))
            ok = all(a >= THRESHOLDS["E2_acc"] and k >= THRESHOLDS["E2_kappa"] for a, k, n in res.values() if n) and len(e2m) > 0
            verdict["E2"] = ok
            drop = res["zwykły"][0] - res["zamaskowany"][0]
            L += ["### E2 — komentarze WGC (wzorzec: zdanie WGC + kod przypisany wg ref/e2_wgc_rules.md, nie przez Qwena)", "",
                  f"Próg (bez zmian): dokładność ≥ {THRESHOLDS['E2_acc']} i κ ≥ {THRESHOLDS['E2_kappa']}, oba warianty.", ""] + [
                  f"- wariant {nm}: n = {n}, dokładność {a:.3f} [Wilson {wilson(round(a * n), n)[0]:.3f}; "
                  f"{wilson(round(a * n), n)[1]:.3f}], κ {k:.3f}" for nm, (a, k, n) in res.items()] + [
                  f"- **n ≈ {res['zwykły'][2]}: wynik bliski progu nie jest rozstrzygający** (przedział dokładności ma szerokość "
                  "rzędu ±0,15).",
                  f"- niezależna kontrola wzorca (subagent, 20 wierszy): {_check_summary()}",
                  f"- spadek dokładności po zamaskowaniu: {drop:+.3f} (sygnał pamięci, gdy > 0,15)",
                  f"- → **{'ZALICZONE' if ok else 'NIEZALICZONE'}**", "",
                  *_e2_conventions(e2), "",
                  "Ograniczenie wzorca (odnotowane, wzorzec bez zmian): 2023-10 (komentarz WGC o ataku z 7 października; cytat poza kopią publiczną) → sovmil — "
                  "niezależna kontrola (runda 3) dała TAK, ale zauważyła, że strona niepaństwowa słabo pasuje do definicji "
                  "„geopolitical tensions between states” (bliżej `terror`).", "",
                  pd.crosstab(e2["gold"], e2["pred"].fillna("BRAK")).to_markdown(), ""]
        gate_sets = ("E1", "E2", "E4-hist") if p["prompt_version"] == "v2" else ("E1", "E2", "E4")
        gate = all(verdict.get(x) is True for x in gate_sets)
        summary.append({"model": p["model"], "prompt": p["prompt_version"], **{k: v for k, v in verdict.items()},
                        "validated": gate})
        L += ["", f"**Werdykt: validated = {'true' if gate else 'false'}** (bramka: E1, E2 z wariantem zamaskowanym, E4; "
              f"E3 to kontrola; wyniki: {verdict}).".replace("E4; ", ("E4-hist; " if p["prompt_version"] == "v2" else "E4; ")), ""]
    if summary:
        cmp = pd.DataFrame(summary).fillna("—")
        L[3:3] = ["## Porównanie prób (1–2: prompt v1; 3: prompt v2, ostatnia — po niej koniec etapu)", "",
                  cmp.astype(str).to_markdown(index=False), ""]
    path = db.ROOT / "reports" / f"move-causes-validation-{date.today()}.md"
    path.write_text("\n".join(L) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "e1", "e2", "e4", "e4hist", "e3", "report"])
    ap.add_argument("--model")
    a = ap.parse_args()
    if a.cmd == "start":
        start(a.model)
    elif a.cmd == "e1":
        run_e1(a.model)
    elif a.cmd == "e4":
        run_e4(a.model)
    elif a.cmd == "e3":
        run_e3(a.model)
    elif a.cmd == "e2":
        run_e2(a.model)
    elif a.cmd == "e4hist":
        run_e4hist(a.model)
    else:
        print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())

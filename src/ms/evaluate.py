"""Walidacja analogii na historii: czy częstość up/down w analogiach przewiduje lepiej niż częstość bazowa.

Zapytania co 20 dni decyzji w ostatnich 10 latach (krypto: od kiedy są cechy i dopuszczalni kandydaci).
Dla zapytania q (wszystko wyłącznie z etykiet z path_end < q — tak jak w analogiach):
- p_up/p_down analogii = częstość w 20 analogiach; losowe = częstość w 20 losowych datach z tercyla rv_60d;
  bazowa = częstość we wszystkich etykietach widocznych w q.
- fakt = etykieta dnia q z labels (używana WYŁĄCZNIE do oceny).
Metryki: Brier (średnia z up i down), BSS = 1 − Brier/Brier_bazowej; Spearman mediany zwrotu 20d/60d analogii
z faktycznym zwrotem. 95% CI: bootstrap blokowy (nienakładające się bloki po 6 kolejnych zapytań, 2000 powtórzeń) —
sąsiednie zapytania mają zachodzące na siebie ścieżki 60 dni, więc nie są niezależne.
Werdykt: „lepsze od bazowej” tylko gdy dolna granica CI dla BSS > 0.
bss_noise_k: oczekiwany BSS samego szumu próby K dat (p(1−p)/K) — część ujemnego BSS, która nie jest złą kalibracją.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ms.analogs import K, Data, select

STEP = 20
YEARS = 10
BLOCK = 6
N_BOOT = 2000


def query_dates(d: Data, end: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    days = d.z.index
    end = end or days.max()
    days = days[(days >= end - pd.DateOffset(years=YEARS)) & (days <= end)]
    return days[::STEP]


def evaluate_query(d: Data, q: pd.Timestamp) -> dict | None:
    """Prognozy dla jednego zapytania (bez faktu). None, gdy za mało kandydatów na K analogii i K losowych."""
    r = select(d, q, n_null=0)
    if len(r.analogs) < K or len(r.random) < K:
        return None
    f = lambda df, c: float(df[c].astype(float).mean())  # noqa: E731
    return {
        "query": r.query,
        "p_up": f(r.analogs, "up_5d"), "p_down": f(r.analogs, "down_5d"),
        "p_up_rand": f(r.random, "up_5d"), "p_down_rand": f(r.random, "down_5d"),
        "p_up_base": r.base_up, "p_down_base": r.base_down,
        "med_ret_20d": float(r.analogs["fwd_ret_20d"].median()), "med_ret_60d": float(r.analogs["fwd_ret_60d"].median()),
        "med_ret_20d_rand": float(r.random["fwd_ret_20d"].median()), "med_ret_60d_rand": float(r.random["fwd_ret_60d"].median()),
        "oldest_candidate": r.oldest_candidate,
    }


def run(d: Data, end=None) -> tuple[pd.DataFrame, int]:
    rows, skipped = [], 0
    for q in query_dates(d, end):
        e = evaluate_query(d, q)
        if e is None:
            skipped += 1
            continue
        fact = d.lab.loc[e["query"]] if e["query"] in d.lab.index else None
        if fact is None or pd.isna(fact["up_5d"]):
            skipped += 1
            continue
        e.update(y_up=float(fact["up_5d"]), y_down=float(fact["down_5d"]),
                 fwd_ret_20d=fact["fwd_ret_20d"], fwd_ret_60d=fact["fwd_ret_60d"])
        rows.append(e)
    return pd.DataFrame(rows), skipped


def brier(df: pd.DataFrame, suffix: str = "") -> float:
    return float(np.mean([((df[f"p_up{suffix}"] - df["y_up"]) ** 2).mean(),
                          ((df[f"p_down{suffix}"] - df["y_down"]) ** 2).mean()]))


def metrics(df: pd.DataFrame) -> dict:
    b_a, b_r, b_b = brier(df), brier(df, "_rand"), brier(df, "_base")
    out = {"brier_analog": b_a, "brier_random": b_r, "brier_base": b_b,
           "bss_analog": 1 - b_a / b_b if b_b > 0 else np.nan,
           "bss_random": 1 - b_r / b_b if b_b > 0 else np.nan}
    out["bss_analog_minus_random"] = out["bss_analog"] - out["bss_random"]
    # kara za sam szum estymatora „częstość w K datach” przy prawdziwym p = bazowe: E[(p̂−p)²] = p(1−p)/K
    noise = np.mean([(df["p_up_base"] * (1 - df["p_up_base"]) / K).mean(),
                     (df["p_down_base"] * (1 - df["p_down_base"]) / K).mean()])
    out["bss_noise_k"] = -noise / b_b if b_b > 0 else np.nan
    for h in (20, 60):
        ok = df[[f"med_ret_{h}d", f"fwd_ret_{h}d"]].dropna()
        out[f"spearman_{h}d"] = float(ok.corr(method="spearman").iloc[0, 1]) if len(ok) > 5 else np.nan
        okr = df[[f"med_ret_{h}d_rand", f"fwd_ret_{h}d"]].dropna()
        out[f"spearman_{h}d_rand"] = float(okr.corr(method="spearman").iloc[0, 1]) if len(okr) > 5 else np.nan
    return out


def bootstrap(df: pd.DataFrame, n: int = N_BOOT, block: int = BLOCK, seed: int = 0) -> pd.DataFrame:
    """95% CI metryk: losowanie ze zwracaniem nienakładających się bloków `block` kolejnych zapytań."""
    df = df.sort_values("query").reset_index(drop=True)
    blocks = [df.iloc[i : i + block] for i in range(0, len(df), block)]
    rng = np.random.default_rng(seed)
    reps = [metrics(pd.concat([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))], ignore_index=True))
            for _ in range(n)]
    reps = pd.DataFrame(reps)
    return pd.DataFrame({"lo": reps.quantile(0.025), "hi": reps.quantile(0.975)})


def verdict(m: dict, ci: pd.DataFrame) -> str:
    lo, hi = ci.loc["bss_analog", "lo"], ci.loc["bss_analog", "hi"]
    vs_base = ("**analogie lepsze od bazowej**" if lo > 0 else
               "**analogie gorsze od bazowej**" if hi < 0 else "**analogie nie lepsze od bazowej**")
    lo2 = ci.loc["bss_analog_minus_random", "lo"]
    vs_rand = "lepsze od losowych z tercyla" if lo2 > 0 else "nie lepsze od losowych z tercyla"
    return f"{vs_base} (BSS {m['bss_analog']:+.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}]); {vs_rand}."

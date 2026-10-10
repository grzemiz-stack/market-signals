"""Ewaluacja prognoz p_up/p_down vs częstość bazowa (etap 3): Brier, BSS, bootstrap blokowy, niezawodność.

Warianty:
- "co20": zapytania co 20 dni decyzji w ostatnich 10 latach, bloki po 6 zapytań (jak walidacja analogii),
- "wszystkie": wszystkie dni decyzji w ostatnich 10 latach, bloki 60 dni kalendarzowych.
Brier = średnia z up i down; BSS = 1 − Brier/Brier_bazowej. 95% CI z 2000 powtórzeń.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

YEARS = 10
N_BOOT = 2000
BINS = [0, 0.02, 0.05, 0.10, 0.20, 1.0001]


def window(df: pd.DataFrame, end: pd.Timestamp | None = None) -> pd.DataFrame:
    end = end or df.index.max()
    return df[(df.index > end - pd.DateOffset(years=YEARS)) & (df.index <= end)]


def variant(df: pd.DataFrame, name: str) -> tuple[pd.DataFrame, np.ndarray]:
    """(podzbiór, identyfikatory bloków)."""
    if name == "co20":
        sub = df.iloc[::20]
        return sub, np.arange(len(sub)) // 6
    days = (df.index - df.index.min()).days
    return df, np.asarray(days // 60)


def brier(p: pd.Series, y: pd.Series) -> float:
    return float(((p - y) ** 2).mean())


def scores(df: pd.DataFrame, cols=("p_up", "p_down")) -> dict:
    bm = np.mean([brier(df[cols[0]], df["y_up"]), brier(df[cols[1]], df["y_down"])])
    bb = np.mean([brier(df["base_up"], df["y_up"]), brier(df["base_down"], df["y_down"])])
    return {"brier": bm, "brier_base": bb, "bss": 1 - bm / bb if bb > 0 else np.nan}


def bootstrap(df: pd.DataFrame, blocks: np.ndarray, stat, n: int = N_BOOT, seed: int = 0) -> tuple[float, float]:
    """95% CI dowolnej statystyki stat(df) przy losowaniu bloków ze zwracaniem."""
    ids = np.unique(blocks)
    groups = {b: np.where(blocks == b)[0] for b in ids}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        take = np.concatenate([groups[b] for b in rng.choice(ids, len(ids))])
        vals.append(stat(df.iloc[take]))
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def reliability(df: pd.DataFrame, pcol: str, ycol: str) -> pd.DataFrame:
    b = pd.cut(df[pcol], BINS, right=False)
    g = df.groupby(b, observed=True).agg(n=(ycol, "size"), prognoza=(pcol, "mean"), fakt=(ycol, "mean"))
    g.index = [f"[{iv.left:.2f}, {min(iv.right, 1):.2f})" for iv in g.index]
    return g

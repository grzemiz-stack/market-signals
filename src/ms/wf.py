"""Wspólna rama walk-forward dla modeli p_up/p_down (etap 3).

Chwila prognozy dnia D = D 22:00 UTC. L(D) = ostatnia obserwacja ceny z known_at <= D 22:00, g = pos(D) − pos(L).
Model prognozuje sumę kroków g+1..g+5 od L (= D+1..D+5, okno etykiety).
Foldy testowe = lata kalendarzowe. Trening dla foldu [Y-01-01, Y+1-01-01):
  próbki z end_5d < początek foldu (purge) ORAZ data <= początek foldu − 40 dni (embargo/luka bezpieczeństwa).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ms.pit import CRYPTO_ASSETS, align, available_from, decision_days, decision_times
from ms.prices import price_frame

EMBARGO = pd.Timedelta(days=40)
MIN_TRAIN_YEARS = 3


@dataclass
class AssetData:
    asset: str
    prices: pd.DataFrame       # indeks observed_at: value, logret, known_at
    r: np.ndarray              # logret jako float, NaN -> 0 (np. WTI ujemne; brak informacji, nie skok)
    table: pd.DataFrame        # indeks D (dni decyzji z obserwacją ceny): pos_d, pos_l, g, sigma_5d, y_up, y_down, end_5d
    ann: int                   # 365 krypto / 252 reszta


def load(con, asset: str) -> AssetData:
    pf = price_frame(con, asset)
    lab = con.execute("SELECT date, sigma_5d, up_5d, down_5d, end_5d FROM labels WHERE asset=?", [asset]).df()
    lab["date"] = pd.to_datetime(lab["date"]).astype("datetime64[ns]")
    lab["end_5d"] = pd.to_datetime(lab["end_5d"]).astype("datetime64[ns]")
    lab = lab.set_index("date")
    days = decision_days(asset, pf.index.min(), pf.index.max())
    days = days[days.isin(pf.index)]  # etykieta istnieje tylko dla dni z obserwacją ceny
    pos = pd.Series(np.arange(len(pf)), index=pf.index)
    pos_l = align(pd.Series(np.arange(len(pf), dtype=float)), available_from(pf["known_at"].reset_index(drop=True)),
                  decision_times(days))
    t = pd.DataFrame({"pos_d": pos.loc[days].to_numpy(), "pos_l": pos_l.to_numpy()}, index=days)
    t = t.dropna(subset=["pos_l"])
    t["pos_l"] = t["pos_l"].astype(int)
    t["g"] = t["pos_d"] - t["pos_l"]
    t = t.join(lab)
    t["y_up"] = t["up_5d"].astype(float)
    t["y_down"] = t["down_5d"].astype(float)
    t = t.drop(columns=["up_5d", "down_5d"])
    r = pf["logret"].to_numpy(dtype=float)
    r = np.where(np.isfinite(r), r, 0.0)
    return AssetData(asset, pf, r, t, 365 if asset in CRYPTO_ASSETS else 252)


def base_rate(t: pd.DataFrame) -> pd.DataFrame:
    """Częstość bazowa w D: średnia y z etykiet o end_5d < D (wyłącznie zakończone przed D)."""
    lab = t.dropna(subset=["y_up", "end_5d"]).sort_values("end_5d")
    cum = pd.DataFrame({"end": lab["end_5d"].values, "n": np.arange(1, len(lab) + 1),
                        "up": lab["y_up"].cumsum().values, "down": lab["y_down"].cumsum().values})
    q = pd.DataFrame({"d": t.index}).sort_values("d")
    m = pd.merge_asof(q, cum, left_on="d", right_on="end", direction="backward", allow_exact_matches=False)
    out = pd.DataFrame({"base_up": (m["up"] / m["n"]).values, "base_down": (m["down"] / m["n"]).values}, index=q["d"].values)
    return out.reindex(t.index)


def folds(t: pd.DataFrame, first_year: int | None = None) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start = t.index.min() + pd.DateOffset(years=MIN_TRAIN_YEARS)
    y0 = max(first_year or 0, start.year + (1 if start.month > 1 or start.day > 1 else 0))
    return [(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")) for y in range(y0, t.index.max().year + 1)]


def train_mask(t: pd.DataFrame, fold_start: pd.Timestamp) -> pd.Series:
    """Purge (end_5d < początek foldu) + embargo (data <= początek − 40 d) + znana etykieta."""
    return (t["end_5d"] < fold_start) & pd.Series(t.index <= fold_start - EMBARGO, index=t.index) & t["y_up"].notna()


def test_mask(t: pd.DataFrame, fold: tuple[pd.Timestamp, pd.Timestamp]) -> pd.Series:
    return pd.Series((t.index >= fold[0]) & (t.index < fold[1]), index=t.index)

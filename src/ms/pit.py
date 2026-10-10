"""Narzędzia point-in-time dla cech: kalendarze decyzji, szereg pierwszych publikacji, dopasowanie do chwil decyzji.

Chwila decyzji dnia D = D 22:00 UTC. Wszystko, co trafia do cech dnia D, ma known_at <= D 22:00.
"""

from __future__ import annotations

import pandas as pd

from ms import db
from ms.common import us_holidays

DECISION_HOUR = pd.Timedelta(hours=22)
BDAY_ASSETS = ("XAU", "XAG", "WTI", "BRENT")
CRYPTO_ASSETS = ("BTC", "ETH")


def decision_days(asset: str, start, end) -> pd.DatetimeIndex:
    days = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D")
    if asset in CRYPTO_ASSETS:
        return days
    hol = {pd.Timestamp(d) for d in us_holidays()}
    return pd.DatetimeIndex([d for d in days if d.weekday() < 5 and d not in hol])


def decision_times(days: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return days + DECISION_HOUR


def first_release(con, series_ids: list[str]) -> pd.DataFrame:
    """Dla każdej obserwacji wersja o najmniejszym known_at: series_id, observed_at, value, known_at, flags."""
    return con.execute("""
        SELECT series_id, observed_at, arg_min(value, known_at) AS value, min(known_at) AS known_at,
               arg_min(flags, known_at) AS flags
        FROM observations WHERE series_id IN (SELECT unnest(?))
        GROUP BY series_id, observed_at ORDER BY series_id, observed_at
    """, [list(series_ids)]).df()


def available_from(known: pd.Series) -> pd.Series:
    """Statystyka liczona po obserwacjach do i (w kolejności observed_at) jest dostępna od cummax(known_at):
    chroni przed obserwacją wcześniejszą opublikowaną później niż nowsza."""
    return known.cummax()


def align(values: pd.Series, avail: pd.Series, times: pd.DatetimeIndex) -> pd.Series:
    """Dla każdej chwili t: wartość ostatniej (w kolejności observed_at) pozycji z avail <= t.
    values/avail: ten sam indeks, posortowane po observed_at; avail niemalejące (cummax)."""
    left = pd.DataFrame({"t": times})
    right = pd.DataFrame({"avail": avail.values, "v": values.values}).dropna(subset=["avail"])
    right = right.sort_values("avail", kind="stable")
    out = pd.merge_asof(left, right, left_on="t", right_on="avail", direction="backward")
    return pd.Series(out["v"].values, index=times)


def panel(con, series_ids: list[str], times: pd.DatetimeIndex) -> pd.DataFrame:
    """Szeroka ramka t × seria: wartość ostatniej obserwacji (w ostatniej wersji) znanej w t (db.panel_asof)."""
    p = db.panel_asof(con, list(series_ids), list(times))
    return p.pivot(index="t", columns="series_id", values="value").reindex(index=times)

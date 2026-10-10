"""Wspólne dla yf_oil / yf_metals: dzienne świece Yahoo z cache (1 zapytanie/symbol/dzień, >= 1 s, backoff 429).

Ciągłe kontrakty Yahoo (=F) mają roll -> tylko uzupełnienie bieżących dni, nie historia.
known_at = koniec sesji dnia: 17:00 ET, flaga known_at_market_close (jak ceny EIA/Stooq). Licencja: tos_restricted.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import pandas as pd

from ms import db
from ms.collectors import write
from ms.common import CACHE, local_series_to_utc

SOURCE = "yahoo"
LICENSE = "tos_restricted"
log = logging.getLogger("collect")


def fetch(sym: str, period: str) -> pd.DataFrame:
    path = CACHE / "yfinance" / f"{sym}_{period}_{date.today()}.csv"
    if path.exists():
        return pd.read_csv(path, parse_dates=["Date"], float_precision="round_trip")
    import yfinance as yf
    from yfinance.exceptions import YFRateLimitError

    delay = 5
    for _ in range(5):
        time.sleep(1.0)
        try:
            df = yf.Ticker(sym).history(period=period, interval="1d", auto_adjust=False, actions=False)
            break
        except YFRateLimitError:
            log.warning("yahoo %s 429, backoff %ds", sym, delay)
            time.sleep(delay)
            delay *= 2
    else:
        raise RuntimeError(f"yahoo {sym}: rate limit")
    if df.empty:
        raise RuntimeError(f"yahoo {sym}: brak danych")
    df = df.reset_index()
    df["Date"] = df["Date"].dt.tz_localize(None).dt.normalize()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def collect_symbols(con, symbols: dict[str, tuple[str, str]], period: str) -> int:
    """symbols: {ticker: (series_id, opis)}."""
    n = 0
    for sym, (sid, desc) in symbols.items():
        db.register_series(con, SOURCE, [(sid, "1d_bday", desc)], LICENSE)
        df = fetch(sym, period)
        df = df[df["Date"] < pd.Timestamp(date.today())]  # dzisiejsza świeca może być niezamknięta
        out = pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": df["Date"],
                            "known_at": local_series_to_utc(df["Date"], "17:00"), "value": df["Close"].astype(float),
                            "license": LICENSE, "flags": "known_at_market_close"})
        added = write(con, out)
        log.info("yahoo %s: %d świec %s..%s, +%d", sym, len(df), df.Date.min().date(), df.Date.max().date(), added)
        n += added
    return n

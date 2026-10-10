"""Krypto ceny: Binance Vision spot BTCUSDT, ETHUSDT 1d od 2017-08.

Pełne miesiące z plików monthly, bieżący miesiąc z plików daily.
known_at = zamknięcie świecy (open_time + 1 d).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.collectors._binance_vision import fetch_zip, months, read_csv_zip, to_ms
from ms.common import long_frame

NAME = "binance_klines"
SOURCE = "binance"
LICENSE = "tos_restricted"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
START = date(2017, 8, 1)
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {
        "open_time": pa.Column("int64"),
        "open": pa.Column(float, pa.Check.gt(0)),
        "high": pa.Column(float, pa.Check.gt(0)),
        "low": pa.Column(float, pa.Check.gt(0)),
        "close": pa.Column(float, pa.Check.gt(0)),
        "volume": pa.Column(float, pa.Check.ge(0)),
        "close_time": pa.Column("int64"),
    },
    checks=pa.Check(lambda d: ((d.close_time - d.open_time) // 1000 == 86399).all(), error="świeca != 1 dzień"),
    coerce=True,
)


def parse(content: bytes) -> pd.DataFrame:
    df = read_csv_zip(content, COLS)
    df["open_time"], df["close_time"] = to_ms(df["open_time"]), to_ms(df["close_time"])
    return RAW_SCHEMA.validate(df)


def to_long(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    raw = raw.copy()
    raw["observed_at"] = pd.to_datetime(raw["open_time"], unit="ms")
    raw["known_at"] = raw["observed_at"] + pd.Timedelta(days=1)
    return long_frame(raw, SOURCE, LICENSE, {c: f"{symbol}.{c}" for c in ("open", "high", "low", "close", "volume")})


def collect(con, full: bool = False) -> int:
    today = date.today()
    last_full_month = (today.replace(day=1) - timedelta(days=1))
    n = 0
    for sym in SYMBOLS:
        db.register_series(con, SOURCE, [(f"{sym}.{c}", "1d_all", f"Binance spot {sym} 1d {c}")
                                         for c in ("open", "high", "low", "close", "volume")], LICENSE)
        frames = []
        for ym in months(START, last_full_month):
            c = fetch_zip(f"data/spot/monthly/klines/{sym}/1d/{sym}-1d-{ym}.zip")
            if c is None:
                # miesiąc tuż po zamknięciu bywa jeszcze nieopublikowany -> dni z plików daily
                y, m = map(int, ym.split("-"))
                d = date(y, m, 1)
                while d.month == m:
                    cd = fetch_zip(f"data/spot/daily/klines/{sym}/1d/{sym}-1d-{d}.zip")
                    if cd is not None:
                        frames.append(parse(cd))
                    d += timedelta(days=1)
                continue
            frames.append(parse(c))
        d = today.replace(day=1)
        while d < today:  # bieżący miesiąc: dni zamknięte
            c = fetch_zip(f"data/spot/daily/klines/{sym}/1d/{sym}-1d-{d}.zip")
            if c is not None:
                frames.append(parse(c))
            d += timedelta(days=1)
        raw = pd.concat(frames, ignore_index=True).drop_duplicates("open_time")
        n += write(con, to_long(raw, sym))
        log.info("binance %s: %d świec %s..%s", sym, len(raw),
                 pd.to_datetime(raw.open_time.min(), unit="ms").date(), pd.to_datetime(raw.open_time.max(), unit="ms").date())
    return n

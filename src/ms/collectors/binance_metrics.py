"""Krypto pochodne: Binance Vision futures/um daily metrics (5 min): OI, long/short.

Start (listing S3, 2026-10-06): BTCUSDT 2020-09-01, ETHUSDT 2021-12-01.
Lista plików z listingu S3 (nie zgadujemy dat) -> brakujące dni widać w raporcie.
known_at = create_time + 5 min (statystyka okna 5-min).
Stare pliki mają zdublowane wiersze (identyczne) -> deduplikacja; sprzeczne duplikaty -> log + ostatni.
"""

from __future__ import annotations

import logging
import re

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.collectors._binance_vision import fetch_zip, list_keys, read_csv_zip

NAME = "binance_metrics"
SOURCE = "binance"
LICENSE = "tos_restricted"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
METRICS = ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
           "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"create_time": pa.Column(pa.DateTime), "symbol": pa.Column(str),
     **{m: pa.Column(float, nullable=True) for m in METRICS}},
    strict=True, coerce=True,
)


def parse(content: bytes) -> pd.DataFrame:
    df = RAW_SCHEMA.validate(read_csv_zip(content, ["create_time", "symbol", *METRICS]))
    df = df.drop_duplicates()
    dup = df["create_time"].duplicated(keep="last")
    if dup.any():
        log.warning("metrics %s: %d sprzecznych duplikatów create_time", df["symbol"].iat[0], int(dup.sum()))
    return df[~dup]


def to_long(raw: pd.DataFrame, sym: str) -> pd.DataFrame:
    parts = []
    for m in METRICS:
        v = raw[["create_time", m]].dropna()
        parts.append(pd.DataFrame({"source": SOURCE, "series_id": f"{sym}.{m}", "observed_at": v["create_time"],
                                   "known_at": v["create_time"] + pd.Timedelta(minutes=5),
                                   "value": v[m].astype(float), "license": LICENSE}))
    return pd.concat(parts, ignore_index=True)


def prefetch(keys: list[str], workers: int = 6) -> None:
    """Równoległe pobranie do cache (statyczne pliki S3/CloudFront); parsowanie potem sekwencyjnie."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(fetch_zip, keys), 1):
            if i % 500 == 0:
                log.info("metrics: pobrano %d/%d", i, len(keys))


def collect(con, full: bool = False) -> int:
    n = 0
    for sym in SYMBOLS:
        db.register_series(con, SOURCE, [(f"{sym}.{m}", "5min", f"Binance UM {sym} {m}") for m in METRICS], LICENSE)
        keys = [k for k in list_keys(f"data/futures/um/daily/metrics/{sym}/") if k.endswith(".zip")]
        day_of = {k: re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", k).group(1) for k in keys}
        if not full:
            last = con.execute("SELECT max(observed_at)::DATE FROM observations WHERE series_id=?",
                               [f"{sym}.sum_open_interest"]).fetchone()[0]
            if last is not None:
                keys = [k for k in keys if day_of[k] >= str(last)]
        log.info("metrics %s: %d plików do przetworzenia (start %s)", sym, len(keys), min(day_of.values()))
        prefetch(sorted(keys))
        batch = []
        for i, k in enumerate(sorted(keys)):
            c = fetch_zip(k)
            if c is not None:
                batch.append(parse(c))
            if len(batch) >= 120 or i == len(keys) - 1:  # partie ~4 mies., żeby nie trzymać wszystkiego w pamięci
                if batch:
                    n += write(con, to_long(pd.concat(batch, ignore_index=True), sym))
                batch = []
    return n

"""Deribit DVOL BTC/ETH, resolution 1D. Start (sprawdzone start_timestamp=0): 2021-03-24.

API zwraca max 1000 świec od końca zakresu + `continuation` (nowy end_timestamp) -> stronicowanie wstecz.
known_at = koniec świecy (ts + 1 d).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import Http, long_frame

NAME = "dvol"
SOURCE = "deribit"
LICENSE = "tos_restricted"
URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"ts": pa.Column("int64"), **{c: pa.Column(float, pa.Check.in_range(1, 500)) for c in ("open", "high", "low", "close")}},
    checks=pa.Check(lambda d: (d.ts % 86_400_000 == 0).all(), error="świeca nie na granicy doby UTC"),
    unique=["ts"], coerce=True,
)


def fetch(http: Http, cur: str, start_ms: int = 0) -> pd.DataFrame:
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = []
    while end:
        r = http.get(URL, params={"currency": cur, "start_timestamp": start_ms, "end_timestamp": end, "resolution": "1D"}).json()
        if "result" not in r:
            raise RuntimeError(f"deribit {cur}: {r}")
        rows += r["result"]["data"]
        nxt = r["result"].get("continuation")
        if nxt is not None and nxt >= end:
            raise RuntimeError("deribit: continuation nie cofa się")
        end = nxt
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"]).drop_duplicates("ts").sort_values("ts")
    return RAW_SCHEMA.validate(df)


def collect(con, full: bool = False) -> int:
    http = Http(min_interval=0.3)
    n = 0
    for cur in ("BTC", "ETH"):
        sids = {c: f"DVOL.{cur}.{c}" for c in ("open", "high", "low", "close")}
        db.register_series(con, SOURCE, [(s, "1d_all", f"Deribit DVOL {cur} {c}") for c, s in sids.items()], LICENSE)
        start = 0
        if not full:
            last = con.execute("SELECT max(observed_at) FROM observations WHERE series_id=?", [sids["close"]]).fetchone()[0]
            if last is not None:
                start = int(pd.Timestamp(last).tz_localize("UTC").timestamp() * 1000) - 5 * 86_400_000
        raw = fetch(http, cur, start)
        raw["observed_at"] = pd.to_datetime(raw["ts"], unit="ms")
        raw["known_at"] = raw["observed_at"] + pd.Timedelta(days=1)
        raw = raw[raw["known_at"] <= pd.Timestamp.now(tz="UTC").tz_localize(None)]  # tylko zamknięte świece
        log.info("DVOL %s: %d świec %s..%s", cur, len(raw), raw.observed_at.min().date(), raw.observed_at.max().date())
        n += write(con, long_frame(raw, SOURCE, LICENSE, sids))
    return n

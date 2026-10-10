"""Crypto Fear & Greed (alternative.me), dziennie od 2018-02-01.

Wartość dnia D liczona i publikowana o 00:00 UTC dnia D (timestamp API) -> known_at = timestamp
(reguła; API nie podaje czasu publikacji). Bieżący dzień bywa aktualizowany w ciągu doby
(time_until_update) -> ingest wersjonujący zapisze zmianę jako nową wersję.
"""

from __future__ import annotations

import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import Http

NAME = "fng"
SOURCE = "alternative_me"
LICENSE = "cc_by"
SID = "FNG.crypto"
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"value": pa.Column(int, pa.Check.in_range(0, 100)), "timestamp": pa.Column("int64", pa.Check(lambda s: (s % 86400 == 0).all())),
     "value_classification": pa.Column(str)},
    unique=["timestamp"], coerce=True, strict=False,
)


def collect(con, full: bool = False) -> int:
    db.register_series(con, SOURCE, [(SID, "1d_all", "Crypto Fear & Greed Index (alternative.me)")], LICENSE)
    j = Http().get("https://api.alternative.me/fng/", params={"limit": 0 if full or not _have(con) else 30, "format": "json"}).json()
    raw = RAW_SCHEMA.validate(pd.DataFrame(j["data"]))
    obs = pd.to_datetime(raw["timestamp"], unit="s")
    df = pd.DataFrame({"source": SOURCE, "series_id": SID, "observed_at": obs, "known_at": obs,
                       "value": raw["value"].astype(float), "license": LICENSE, "flags": "known_at_rule"})
    log.info("F&G: %d dni %s..%s", len(df), obs.min().date(), obs.max().date())
    return write(con, df)


def _have(con) -> bool:
    return con.execute("SELECT count(*) FROM observations WHERE series_id=?", [SID]).fetchone()[0] > 0

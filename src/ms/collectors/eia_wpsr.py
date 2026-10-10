"""EIA Weekly Petroleum Status Report: zapasy ropy (bez SPR), Cushing, produkcja, utylizacja rafinerii.

Okres = tydzień kończący się w piątek (data EIA = piątek).
known_at (reguła, flaga): środa po okresie 10:30 ET; jeśli w tygodniu publikacji (pn–śr) jest
święto federalne -> czwartek 11:00 ET. Bez futures (EIA przestało je publikować po 2024-04-05).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.collectors._eia import fetch_series
from ms.common import local_to_utc, us_holidays

NAME = "eia_wpsr"
SOURCE = "eia"
LICENSE = "public_domain"
SERIES = {
    "PET.WCESTUS1.W": ("EIA.WCESTUS1", "US crude stocks ex SPR, kbbl"),
    "PET.W_EPC0_SAX_YCUOK_MBBL.W": ("EIA.CUSHING", "Cushing OK crude stocks ex SPR, kbbl"),
    "PET.WCRFPUS2.W": ("EIA.WCRFPUS2", "US field production of crude, kbbl/d"),
    "PET.WPULEUS3.W": ("EIA.WPULEUS3", "US refinery utilization, %"),
    "PET.WCSSTUS1.W": ("EIA.SPR", "US Strategic Petroleum Reserve stocks, kbbl"),
}
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"period": pa.Column(pa.DateTime, pa.Check(lambda s: (s.dt.weekday == 4).all(), error="okres nie kończy się w piątek")),
     "value": pa.Column(float, nullable=True)},
    coerce=True,
)


def known_at_wpsr(period) -> pd.Timestamp:
    fri = pd.Timestamp(period).date()
    mon, wed = fri + timedelta(days=3), fri + timedelta(days=5)
    hol = us_holidays()
    if any(mon + timedelta(days=i) in hol for i in range(3)):
        return pd.Timestamp(local_to_utc(wed + timedelta(days=1), "11:00"))
    return pd.Timestamp(local_to_utc(wed, "10:30"))


def collect(con, full: bool = False) -> int:
    n = 0
    for eia_id, (sid, desc) in SERIES.items():
        db.register_series(con, SOURCE, [(sid, "1w", desc)], LICENSE)
        raw = RAW_SCHEMA.validate(fetch_series(eia_id)).dropna(subset=["value"])
        df = pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": raw["period"].values,
                           "known_at": [known_at_wpsr(p) for p in raw["period"]],
                           "value": raw["value"].astype(float).values, "license": LICENSE, "flags": "known_at_rule"})
        log.info("%s: %d tyg. %s..%s", sid, len(raw), raw.period.min().date(), raw.period.max().date())
        n += write(con, df)
    return n

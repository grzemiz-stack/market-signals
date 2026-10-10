"""Ropa ceny do etykiet: EIA spot RWTC (WTI Cushing) i RBRTE (Brent), pełna historia, bez rolla.

known_at = zamknięcie sesji dnia notowania: 14:30 ET (settlement NYMEX WTI; ICE Brent 19:30 Londyn ≈ 14:30 ET),
z czasem letnim -> 18:30/19:30 UTC; flaga known_at_market_close (decyzja 2026-10-06: cena rynkowa jest publiczna
w dniu notowania — opóźnienie publikacji EIA dotyczy tylko danych powstających w chwili publikacji, np. WPSR).
Wartości <= 0 (WTI 2020-04-20) -> flaga nonpositive; log-zwroty liczy ms.transforms.
"""

from __future__ import annotations

import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.collectors._eia import fetch_series
from ms.common import local_series_to_utc

NAME = "eia_spot"
SOURCE = "eia"
LICENSE = "public_domain"
SERIES = {"PET.RWTC.D": "EIA.RWTC", "PET.RBRTE.D": "EIA.RBRTE",
          # etap 4H: produkty do cracku 3-2-1 (NY Harbor, $/gal) i futures WTI 1–4 (EIA przestało publikować po 2024-04-05)
          "PET.EER_EPMRU_PF4_Y35NY_DPG.D": "EIA.GASOLINE_NYH", "PET.EER_EPD2F_PF4_Y35NY_DPG.D": "EIA.ULSD_NYH",
          "PET.RCLC1.D": "EIA.RCLC1", "PET.RCLC2.D": "EIA.RCLC2", "PET.RCLC3.D": "EIA.RCLC3", "PET.RCLC4.D": "EIA.RCLC4"}
# Luka bez wypełniania (decyzja 2026-10-06): futures WTI z EIA kończą się 2024-04-05, snapshoty krzywej zaczynają 2026-10-06
GAPS = [(f"EIA.RCLC{k}", "2024-04-06", "2026-10-05", "EIA przestało publikować futures; krzywa z snapshotów od 2026-10-06; bez przybliżenia")
        for k in range(1, 5)]
MARKET_CLOSE_ET = "14:30"
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"period": pa.Column(pa.DateTime), "value": pa.Column(float, nullable=True),
     "units": pa.Column(str, pa.Check.isin(["$/BBL", "$/GAL"]))},
    coerce=True,
)




def to_long(raw: pd.DataFrame, sid: str) -> pd.DataFrame:
    raw = raw.dropna(subset=["value"])
    flags = ["known_at_market_close,nonpositive" if v <= 0 else "known_at_market_close" for v in raw["value"]]
    return pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": raw["period"].values,
                         "known_at": local_series_to_utc(raw["period"], MARKET_CLOSE_ET).values,
                         "value": raw["value"].astype(float).values, "license": LICENSE, "flags": flags})


def collect(con, full: bool = False) -> int:
    n = 0
    for eia_id, sid in SERIES.items():
        db.register_series(con, SOURCE, [(sid, "1d_bday", f"EIA {eia_id} ({'futures' if 'RCLC' in eia_id else 'spot'})")], LICENSE)
        raw = RAW_SCHEMA.validate(fetch_series(eia_id))
        log.info("%s: %d obs %s..%s", sid, len(raw), raw.period.min().date(), raw.period.max().date())
        n += write(con, to_long(raw, sid))
    con.executemany("INSERT OR REPLACE INTO series_gaps VALUES (?, ?, ?, ?)", GAPS)
    return n

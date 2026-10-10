"""EIA STEO (miesięczne): zapasy komercyjne OECD (PASC_OECD_T3, mln bbl) i produkcja światowa (PAPR_WORLD, mb/d).

STEO zawiera PROGNOZY do końca kolejnego roku -> odcinamy miesiące >= (bieżący miesiąc − 2) (historia/oszacowania).
API daje tylko NAJNOWSZE wydanie (wartości zrewidowane) -> flaga steo_latest_vintage; known_at (reguła) = koniec
miesiąca + 40 dni (STEO wychodzi ~6–12 dnia, dane za miesiąc m pierwszy raz w wydaniu m+2). Do testów hipotez
na dacie obserwacji, NIE jako cecha PIT bez dodatkowej weryfikacji.
"""

from __future__ import annotations

import logging

import pandas as pd

from ms import db
from ms.collectors import write
from ms.collectors._eia import fetch_series

NAME = "eia_steo"
SOURCE = "eia"
LICENSE = "public_domain"
SERIES = {"STEO.PASC_OECD_T3.M": ("EIA.STEO_OECD_STOCKS", "OECD commercial crude+liquids inventory, mln bbl"),
          "STEO.PAPR_WORLD.M": ("EIA.STEO_WORLD_PROD", "World petroleum production, mb/d")}
log = logging.getLogger("collect")


def collect(con, full: bool = False) -> int:
    cutoff = (pd.Timestamp.now().normalize().replace(day=1) - pd.DateOffset(months=2))
    n = 0
    for eid, (sid, desc) in SERIES.items():
        db.register_series(con, SOURCE, [(sid, "1m", desc + " (STEO, najnowsze wydanie)")], LICENSE)
        raw = fetch_series(eid)
        raw["period"] = pd.to_datetime(raw["period"])
        raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
        raw = raw[(raw["period"] < cutoff)].dropna(subset=["value"])
        df = pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": raw["period"],
                           "known_at": raw["period"] + pd.offsets.MonthEnd(0) + pd.Timedelta(days=40),
                           "value": raw["value"].astype(float), "license": LICENSE,
                           "flags": "known_at_rule,steo_latest_vintage"})
        log.info("%s: %d mies. %s..%s (bez prognoz od %s)", sid, len(df), df.observed_at.min().date(), df.observed_at.max().date(), cutoff.date())
        n += write(con, df)
    return n

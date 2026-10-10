"""Szoki strukturalne rynku ropy Baumeister–Hamilton (miesięczne, mediany a posteriori), pliki autorki (Google Drive).

- BH.SUPPLY (szok podażowy; dodatni = więcej podaży wg BH 2019): tylko do 2023-04 (publiczna wersja nieaktualizowana).
- BH.ECON_ACTIVITY, BH.CONS_DEMAND, BH.INV_DEMAND (popyt zapobiegawczy/zapasowy): do 2026-03.
Wartości z najnowszej estymacji (rewidowane) -> flaga latest_vintage; known_at (reguła) = koniec miesiąca + 3 mies.
Licencja: dane badawcze z cytowaniem (Baumeister & Hamilton, AER 2019) -> cc_by.
"""

from __future__ import annotations

import io
import logging

import pandas as pd

from ms import db
from ms.collectors import write
from ms.common import CACHE, Http, cached_get

NAME = "bh_shocks"
SOURCE = "baumeister"
LICENSE = "cc_by"
DRIVE = "https://drive.google.com/uc?export=download&id={}"
FILES = {"fundamental": "1_LMvR279GJl7U64wY0EsbZ4Kjv-if7N4", "demand": "1neFXLrIvGwggebQRwjmtrWK-dfQZ9NH8"}
log = logging.getLogger("collect")


def _sheet(content: bytes, sheet: str, cols: dict[int, str]) -> pd.DataFrame:
    d = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None)
    d = d[pd.to_datetime(d[0], errors="coerce").notna()]
    out = pd.DataFrame({"observed_at": pd.to_datetime(d[0])})
    for i, name in cols.items():
        out[name] = pd.to_numeric(d[i], errors="coerce")
    return out


def collect(con, full: bool = False) -> int:
    http = Http()
    fund = cached_get(http, DRIVE.format(FILES["fundamental"]), CACHE / "bh" / "fundamental.xlsx", refresh=True)
    dem = cached_get(http, DRIVE.format(FILES["demand"]), CACHE / "bh" / "demand.xlsx", refresh=True)
    a = _sheet(fund, "fundamental oil market shocks", {1: "BH.SUPPLY"})
    b = _sheet(dem, "demand shocks", {1: "BH.ECON_ACTIVITY", 2: "BH.CONS_DEMAND", 3: "BH.INV_DEMAND"})
    n = 0
    for df in (a, b):
        for sid in [c for c in df.columns if c != "observed_at"]:
            s = df[["observed_at", sid]].dropna()
            db.register_series(con, SOURCE, [(sid, "1m", f"Baumeister–Hamilton {sid[3:].lower()} shock")], LICENSE)
            n += write(con, pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": s["observed_at"],
                                          "known_at": s["observed_at"] + pd.offsets.MonthEnd(0) + pd.DateOffset(months=3),
                                          "value": s[sid], "license": LICENSE, "flags": "known_at_rule,latest_vintage"}))
            log.info("%s: %d mies. %s..%s", sid, len(s), s.observed_at.min().date(), s.observed_at.max().date())
    return n

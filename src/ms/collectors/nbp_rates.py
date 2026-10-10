"""Stopa referencyjna NBP (historia zmian) — do oprocentowania gotówki w grze na sucho (stopa ref. − 1 pp).

Źródło: https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml (wszystkie zmiany od 1998).
Seria schodkowa: observed_at = known_at = dzień wejścia w życie, 00:00 UTC (decyzję RPP ogłasza się dzień
wcześniej — known_at konserwatywny), flaga known_at_rule. Wartość obowiązuje do następnej zmiany.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import pandas as pd

from ms import db
from ms.collectors import write
from ms.common import Http

NAME = "nbp_rates"
SOURCE = "nbp"
LICENSE = "cc_by"
SID = "NBP.REF"
URL = "https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml"
log = logging.getLogger("collect")


def parse(xml: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml)
    rows = []
    for p in root.iter("pozycje"):
        ref = next((x.get("oprocentowanie") for x in p if x.get("id") == "ref"), None)
        if ref is None:
            raise ValueError("format NBP: brak pozycji id=ref")
        rows.append((pd.Timestamp(p.get("obowiazuje_od")), float(ref.replace(",", "."))))
    df = pd.DataFrame(rows, columns=["d", "v"]).drop_duplicates("d").sort_values("d")
    if df.empty or not df["v"].between(0, 50).all():
        raise ValueError("format NBP: nieoczekiwane wartości")
    return df


def collect(con, full: bool = False) -> int:
    db.register_series(con, SOURCE, [(SID, "irregular", "NBP stopa referencyjna, % (od dnia wejścia w życie)")], LICENSE)
    df = parse(Http().get(URL).content)
    log.info("NBP stopa ref.: %d zmian %s..%s, ostatnia %.2f%%", len(df), df.d.min().date(), df.d.max().date(), df.v.iat[-1])
    return write(con, pd.DataFrame({"source": SOURCE, "series_id": SID, "observed_at": df["d"],
                                    "known_at": df["d"], "value": df["v"],
                                    "license": LICENSE, "flags": "known_at_rule"}))

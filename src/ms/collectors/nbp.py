"""NBP tabela A: USD/PLN, EUR/PLN (kurs średni), od 2002-01-02.

API: max 93 dni na zapytanie -> okna kwartalne. known_at: dzień publikacji (effectiveDate)
12:15 Europe/Warsaw (tabela A publikowana między 11:45 a 12:15) — reguła.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import WAW, Http, local_series_to_utc

NAME = "nbp"
SOURCE = "nbp"
LICENSE = "cc_by"
CODES = ("usd", "eur")
START = date(2002, 1, 2)
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"no": pa.Column(str, pa.Check.str_contains("/A/NBP/")), "effectiveDate": pa.Column(pa.DateTime),
     "mid": pa.Column(float, pa.Check.in_range(0.5, 20))},
    unique=["effectiveDate"], coerce=True, strict=True,
)


def fetch(http: Http, code: str, start: date, end: date) -> pd.DataFrame:
    rows, a = [], start
    while a <= end:
        b = min(a + timedelta(days=92), end)
        r = http.get(f"https://api.nbp.pl/api/exchangerates/rates/a/{code}/{a}/{b}/", params={"format": "json"})
        if r.status_code != 404:  # 404 = brak notowań w oknie
            rows += r.json()["rates"]
        a = b + timedelta(days=1)
    return RAW_SCHEMA.validate(pd.DataFrame(rows))


def collect(con, full: bool = False) -> int:
    http = Http(min_interval=0.2)
    n = 0
    for code in CODES:
        sid = f"NBP.{code.upper()}PLN"
        db.register_series(con, SOURCE, [(sid, "1d_bday", f"NBP tabela A {code.upper()}/PLN kurs średni")], LICENSE)
        start = START
        if not full:
            last = con.execute("SELECT max(observed_at) FROM observations WHERE series_id=?", [sid]).fetchone()[0]
            if last is not None:
                start = pd.Timestamp(last).date() - timedelta(days=10)
        raw = fetch(http, code, start, date.today())
        df = pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": raw["effectiveDate"],
                           "known_at": local_series_to_utc(raw["effectiveDate"], "12:15", WAW),
                           "value": raw["mid"], "license": LICENSE, "flags": "known_at_rule"})
        log.info("%s: %d dni %s..%s", sid, len(df), raw.effectiveDate.min().date(), raw.effectiveDate.max().date())
        n += write(con, df)
    return n

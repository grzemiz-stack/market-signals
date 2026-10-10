"""Metale: Stooq xauusd, xagusd (dziennie od początku).

Stooq blokuje automaty (JS proof-of-work) -> tylko skrzynka ręczna:
pobierz w przeglądarce https://stooq.com/q/d/l/?s=xauusd&i=d (i xagusd)
i zapisz do data/inbox/stooq/ (nazwy xauusd_d.csv, xagusd_d.csv).
Każdy plik to pełna historia; parsujemy najnowszy.

known_at = zamknięcie sesji dnia: 17:00 ET (koniec dnia handlowego spot metali w NY), flaga known_at_market_close.
Weryfikacja 2026-10-06: od 1990 brak słupków niedzielnych — handel od niedzieli 18:00 ET trafia do poniedziałku,
czyli Stooq tnie dzień o 17:00 ET (przy cięciu o północy Warszawy zimą powstawałyby słupki niedzielne).

Wczesna historia (od 1792/1793) to pojedyncze notowania miesięczne. Początek notowań dziennych =
pierwszy dzień pierwszego roku z >= 200 notowaniami (2026-10-06: XAUUSD 1970-01-05, XAGUSD 1964-01-02);
wcześniejsze wiersze -> flaga sparse_history (raport pokrycia liczy dziury od początku notowań dziennych).
Świeca z dnia archiwizacji pliku jest odrzucana (plik pobrany w trakcie sesji = świeca niezamknięta).
Bieżący okres między ręcznymi aktualizacjami (raz na kwartał) pokrywa yf_metals.
"""

from __future__ import annotations

import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import archive_inbox, latest_raw, local_series_to_utc, long_frame

NAME = "metals_stooq"
SOURCE = "stooq"
LICENSE = "tos_restricted"
SYMBOLS = {"xauusd": "XAUUSD", "xagusd": "XAGUSD"}
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {
        "Date": pa.Column(pa.DateTime),
        "Open": pa.Column(float, pa.Check.gt(0)),
        "High": pa.Column(float, pa.Check.gt(0)),
        "Low": pa.Column(float, pa.Check.gt(0)),
        "Close": pa.Column(float, pa.Check.gt(0)),
    },
    unique=["Date"],
    coerce=True,
    strict=False,  # Volume bywa/nie bywa
)


DAILY_MIN_PER_YEAR = 200


def daily_start(dates: pd.Series) -> pd.Timestamp:
    per_year = dates.groupby(dates.dt.year).size()
    year = per_year[per_year >= DAILY_MIN_PER_YEAR].index.min()
    return dates[dates.dt.year == year].min()


def parse(path, symbol: str, archived_on: pd.Timestamp | None = None) -> pd.DataFrame:
    raw = pd.read_csv(path, float_precision="round_trip")
    raw = RAW_SCHEMA.validate(raw)
    if archived_on is not None:
        raw = raw[raw["Date"] < archived_on]
    start = daily_start(raw["Date"])
    log.info("stooq %s: notowania dzienne od %s", symbol, start.date())
    sparse = raw["Date"] < start
    raw["observed_at"] = raw["Date"]
    raw["known_at"] = local_series_to_utc(raw["Date"], "17:00")
    raw["flags"] = ["known_at_market_close,sparse_history" if x else "known_at_market_close" for x in sparse]
    df = long_frame(raw, SOURCE, LICENSE, {c: f"{symbol}.{c.lower()}" for c in ("Open", "High", "Low", "Close")},
                    flags="flags")
    return df


def collect(con, full: bool = False) -> int:
    archive_inbox(SOURCE, "*.csv")
    files = latest_raw(SOURCE, "*_d.csv")
    if not files:
        log.warning("stooq: brak plików — pobierz ręcznie do data/inbox/stooq/ (patrz docstring)")
        return 0
    n = 0
    for p in files:
        key = p.name.split("_")[0].lower()
        if key not in SYMBOLS:
            continue
        sym = SYMBOLS[key]
        db.register_series(con, SOURCE, [(f"{sym}.{c}", "1d_bday", f"Stooq {sym} {c}") for c in ("open", "high", "low", "close")], LICENSE)
        n += write(con, parse(p, sym, archived_on=pd.Timestamp(p.parent.name)))
    return n

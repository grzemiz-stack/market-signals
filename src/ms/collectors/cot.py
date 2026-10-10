"""CFTC Commitments of Traders (cot_reports): legacy + disaggregated (futures only).

Rynki (kody CFTC, sprawdzone w danych 2024):
  088691 GOLD (COMEX), 084691 SILVER (COMEX), 067651 WTI (NYMEX; dawniej "CRUDE OIL, LIGHT SWEET"),
  06765T BRENT LAST DAY (NYMEX), 133741 BITCOIN (CME), 146021 ETHER CASH SETTLED (CME).
BTC/ETH są tylko w legacy (finansowe -> brak w disaggregated; ich odpowiednik to TFF).

known_at: piątek tygodnia raportu 15:30 ET. Święto federalne w śr/czw/pt tygodnia publikacji ->
najbliższy dzień roboczy po piątku (reguła odtwarza cały harmonogram CFTC 2026 — test).
Shutdowny rządu: raporty z okna przerwy publikowano z opóźnieniem w trybie nadrabiania;
dokładnych dat nie mamy -> konserwatywnie known_at = koniec nadrabiania (przybliżony), flaga known_at_uncertain.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import CACHE, local_series_to_utc, next_us_bday, us_holidays

NAME = "cot"
SOURCE = "cftc"
LICENSE = "public_domain"
log = logging.getLogger("collect")

MARKETS = {"088691": "GOLD", "084691": "SILVER", "067651": "WTI", "06765T": "BRENT", "133741": "BTC", "146021": "ETH"}

REPORTS = {
    "legacy_fut": {
        "date": "As of Date in Form YYYY-MM-DD", "code": "CFTC Contract Market Code", "hist_from": 1986,
        "cols": ["Open Interest (All)", "Noncommercial Positions-Long (All)", "Noncommercial Positions-Short (All)",
                 "Noncommercial Positions-Spreading (All)", "Commercial Positions-Long (All)",
                 "Commercial Positions-Short (All)", "Nonreportable Positions-Long (All)",
                 "Nonreportable Positions-Short (All)"],
    },
    "disaggregated_fut": {
        "date": "Report_Date_as_YYYY-MM-DD", "code": "CFTC_Contract_Market_Code", "hist_from": 2006,
        "cols": ["Open_Interest_All", "Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All",
                 "Swap_Positions_Long_All", "Swap__Positions_Short_All", "Swap__Positions_Spread_All",
                 "M_Money_Positions_Long_All", "M_Money_Positions_Short_All", "M_Money_Positions_Spread_All",
                 "Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All", "Other_Rept_Positions_Spread_All",
                 "NonRept_Positions_Long_All", "NonRept_Positions_Short_All"],
    },
}

# (pierwszy dotknięty raport, ostatni dotknięty raport, koniec nadrabiania — PRZYBLIŻONY, z zapasem)
SHUTDOWNS = [
    (date(2013, 10, 1), date(2013, 10, 15), date(2013, 12, 31)),
    (date(2018, 12, 25), date(2019, 3, 5), date(2019, 3, 8)),
    (date(2025, 9, 30), date(2025, 12, 31), date(2026, 1, 31)),
]


def release_date(report: date) -> date:
    fri = report + timedelta(days=(4 - report.weekday()) % 7)
    hol = us_holidays()
    if any(fri - timedelta(days=i) in hol for i in range(3)):  # śr, czw, pt
        return next_us_bday(fri + timedelta(days=1))
    return fri


def known_at(reports: pd.Series) -> tuple[pd.Series, pd.Series]:
    rel, flags = [], []
    for r in pd.to_datetime(reports).dt.date:
        d, f = release_date(r), "known_at_rule"
        for a, b, catchup in SHUTDOWNS:
            if a <= r <= b:
                d, f = max(d, catchup), "known_at_uncertain"
        rel.append(d)
        flags.append(f)
    return local_series_to_utc(pd.Series(rel, index=reports.index), "15:30"), pd.Series(flags, index=reports.index)


def slug(col: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", col)).strip("_").lower()


def raw_schema(rep: str) -> pa.DataFrameSchema:
    spec = REPORTS[rep]
    return pa.DataFrameSchema(
        {spec["date"]: pa.Column(pa.DateTime), spec["code"]: pa.Column(str),
         **{c: pa.Column(float, nullable=True) for c in spec["cols"]}},  # ujemne = błąd źródła -> flaga, nie wyjątek
        coerce=True, strict=False,
    )


def download(rep: str, years: list[int], hist: bool) -> pd.DataFrame:
    import cot_reports as cot

    workdir = CACHE / "cot"
    workdir.mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(workdir)  # cot_reports zapisuje pliki tymczasowe w cwd
    try:
        frames = [cot.cot_hist(cot_report_type=rep, store_txt=False, verbose=False)] if hist else []
        frames += [cot.cot_year(y, cot_report_type=rep, store_txt=False, verbose=False) for y in years]
    finally:
        os.chdir(cwd)
    return pd.concat(frames, ignore_index=True)


def to_long(raw: pd.DataFrame, rep: str) -> pd.DataFrame:
    spec = REPORTS[rep]
    raw = raw.copy()
    raw[spec["code"]] = raw[spec["code"]].astype(str).str.strip()
    raw = raw[raw[spec["code"]].isin(MARKETS)]
    raw = raw_schema(rep).validate(raw)
    raw = raw.drop_duplicates(subset=[spec["date"], spec["code"]], keep="last")
    k, fl = known_at(raw[spec["date"]])
    parts = []
    short = rep.split("_")[0]
    for col in spec["cols"]:
        parts.append(pd.DataFrame({
            "source": SOURCE,
            "series_id": [f"COT.{short}.{MARKETS[c]}.{slug(col)}" for c in raw[spec["code"]]],
            "observed_at": raw[spec["date"]].values, "known_at": k.values,
            "value": pd.to_numeric(raw[col], errors="coerce").values, "license": LICENSE,
            "flags": [f + ",source_anomaly" if v < 0 else f for f, v in zip(fl, raw[col])],
        }).dropna(subset=["value"]))
    return pd.concat(parts, ignore_index=True)


def collect(con, full: bool = False) -> int:
    n = 0
    this_year = date.today().year
    for rep, spec in REPORTS.items():
        short = rep.split("_")[0]
        have = con.execute("SELECT count(*) FROM observations WHERE source=? AND series_id LIKE ?",
                           [SOURCE, f"COT.{short}.%"]).fetchone()[0]
        hist = full or have == 0
        years = list(range(2017, this_year + 1)) if hist else [this_year - 1, this_year]
        raw = download(rep, years, hist)
        df = to_long(raw, rep)
        db.register_series(con, SOURCE, [(s, "1w", f"CFTC COT {rep}") for s in sorted(df.series_id.unique())], LICENSE)
        found = sorted({s.split(".")[2] for s in df.series_id})
        log.info("COT %s: %d wierszy, rynki %s, %s..%s", rep, len(df), found, df.observed_at.min().date(), df.observed_at.max().date())
        n += write(con, df)
    return n

"""Coin Metrics (on-chain) z snapshotów data/raw/coinmetrics/: initial (repo), backfill i dzienne (API).

known_at: initial = data commita repo (publicznie dostępne od tej chwili), API = czas pobrania.
Pomijamy ReferenceRate* (darmowe API ma tylko ~7 dni -> luka 2026-05-25…09-29) oraz pola *-status*.
PriceUSD to osobna seria — NIE sklejamy jej z ReferenceRateUSD (inne definicje).
Repo vs API różnią się na zakładce (rewizje) -> ingest zapisze wartości API jako nowsze wersje.
Dodatkowo wersja przybliżona: known_at = observed_at + 1 dzień, flaga known_at_approx (wartość z najwcześniejszego
snapshotu z tą obserwacją; wersje snapshotowe zostają).
"""

from __future__ import annotations

import json
import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import approx_versions, first_seen, write, write_exact
from ms.collectors._snapshots import done, mark, snapshot_files
from ms.common import CACHE, Http

NAME = "coinmetrics"
SOURCE = "coinmetrics"
LICENSE = "cc_by_nc"
APPROX_LAG = pd.Timedelta(days=1)
log = logging.getLogger("collect")

CSV_SCHEMA = pa.DataFrameSchema({"time": pa.Column(pa.DateTime)}, coerce=True, strict=False)
JSON_ROW = pa.DataFrameSchema({"asset": pa.Column(str, pa.Check.isin(["btc", "eth"])), "time": pa.Column(str)}, strict=False)


def keep(metric: str) -> bool:
    return not metric.startswith("ReferenceRate") and "-status" not in metric and metric not in ("asset", "time")


def commit_time(sha: str) -> pd.Timestamp:
    p = CACHE / "coinmetrics" / f"commit_{sha}.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(Http().get(f"https://api.github.com/repos/coinmetrics/data/commits/{sha}").text)
    return pd.Timestamp(json.loads(p.read_text())["commit"]["committer"]["date"]).tz_convert("UTC").tz_localize(None)


def melt(wide: pd.DataFrame, asset: str, known: pd.Timestamp) -> pd.DataFrame:
    cols = [c for c in wide.columns if keep(c)]
    long = wide.melt(id_vars=["time"], value_vars=cols, var_name="metric", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    long = long[long["time"] <= known]
    return pd.DataFrame({"source": SOURCE, "series_id": "CM." + asset + "." + long["metric"],
                         "observed_at": long["time"].values, "known_at": known, "value": long["value"].values,
                         "vintage": known.date(), "license": LICENSE})


def parse_csv(path) -> pd.DataFrame:
    return CSV_SCHEMA.validate(pd.read_csv(path, float_precision="round_trip", low_memory=False))


def parse_json(path) -> pd.DataFrame:
    j = json.loads(path.read_text())
    df = JSON_ROW.validate(pd.DataFrame(j["data"]))
    df["time"] = pd.to_datetime(df["time"].str[:10])
    return df


def collect(con, full: bool = False) -> int:
    n = 0
    for fetched, path, e in snapshot_files(SOURCE):
        if not full and done(con, path):
            continue
        if path.suffix == ".csv":
            asset, known, wide = path.stem, commit_time(e["commit"]), parse_csv(path)
        else:
            wide = parse_json(path)
            asset, known = wide["asset"].iat[0], fetched
        df = melt(wide, asset, known)
        db.register_series(con, SOURCE, [(s, "1d_all", f"Coin Metrics community {s[3:]}") for s in df.series_id.unique()], LICENSE)
        approx = approx_versions(first_seen(con, df), APPROX_LAG)  # przed zapisem snapshotu
        added = write(con, df)
        added += write_exact(con, approx)
        log.info("coinmetrics %s (known %s): %d wierszy, +%d", path.relative_to(path.parents[2]), known, len(df), added)
        n += added
        mark(con, path)
    return n

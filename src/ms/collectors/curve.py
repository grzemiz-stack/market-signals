"""Krzywa ropy: parsowanie snapshotów data/raw/curve/{data}/ (snapshot_raw.py).

Serie:
- CURVE.{kontrakt}.close (np. CURVE.CLX26.NYM.close): wszystkie wiersze z każdego snapshotu,
  known_at = fetched_at snapshotu z manifestu (wersjonowanie pomija powtórzenia),
- CURVE.{CL|BZ}.M{1..6}: miesiąc k krzywej wg curve_map.json, tylko ostatnia świeca snapshotu.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import RAW

NAME = "curve"
SOURCE = "yahoo"
LICENSE = "tos_restricted"
log = logging.getLogger("collect")

RAW_SCHEMA = pa.DataFrameSchema(
    {"Date": pa.Column(str), "Close": pa.Column(float, pa.Check.gt(-100))},
    coerce=True, strict=False,
)


def manifest_times() -> dict[str, pd.Timestamp]:
    """path -> fetched_at (UTC naive)."""
    out = {}
    m = RAW / "manifest.jsonl"
    if m.exists():
        for line in m.read_text().splitlines():
            e = json.loads(line)
            if e.get("source") == "curve" and e.get("path"):
                out[e["path"]] = pd.Timestamp(e["fetched_at"]).tz_convert("UTC").tz_localize(None)
    return out


def parse_snapshot(day_dir, times: dict) -> pd.DataFrame:
    parts = []
    cmap_path = day_dir / "curve_map.json"
    cmap = json.loads(cmap_path.read_text())["contracts"] if cmap_path.exists() else {}
    month_of = {c["symbol"]: (root, c["month"]) for root, cs in cmap.items() for c in cs}
    for f in sorted(day_dir.glob("*.NYM*.csv")):
        rel = str(f.relative_to(RAW.parent.parent))
        if rel not in times:
            log.warning("curve: %s bez wpisu w manifeście, pomijam", rel)
            continue
        known = times[rel]
        sym = f.name.split("__")[0].removesuffix(".csv")
        raw = RAW_SCHEMA.validate(pd.read_csv(f, float_precision="round_trip"))
        obs = pd.to_datetime(raw["Date"].str[:10])
        raw = raw[obs <= known]
        obs = obs[obs <= known]
        parts.append(pd.DataFrame({"series_id": f"CURVE.{sym}.close", "observed_at": obs, "known_at": known,
                                   "value": raw["Close"].astype(float)}))
        if sym in month_of and len(obs):
            root, k = month_of[sym]
            parts.append(pd.DataFrame({"series_id": [f"CURVE.{root}.M{k}"], "observed_at": [obs.max()],
                                       "known_at": [known], "value": [float(raw["Close"].iloc[obs.argmax()])]}))
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df["source"], df["license"] = SOURCE, LICENSE
    return df


def collect(con, full: bool = False) -> int:
    times = manifest_times()
    n = 0
    for day_dir in sorted(p for p in (RAW / "curve").glob("20*") if p.is_dir()):
        df = parse_snapshot(day_dir, times)
        if df.empty:
            continue
        sids = sorted(df.series_id.unique())
        db.register_series(con, SOURCE, [(s, "1d_bday", "krzywa ropy z snapshotów yfinance") for s in sids], LICENSE)
        n += write(con, df)
    return n

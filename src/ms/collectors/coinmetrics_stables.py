"""Podaż stablecoinów (Coin Metrics Community, bez klucza): USDT i USDC SplyCur dziennie, pełna historia.

known_at (reguła) = dzień + 1 (dane dnia zamykają się o 00:00 UTC). Licencja CC BY-NC (Coin Metrics Community).
"""

from __future__ import annotations

import logging

import pandas as pd

from ms import db
from ms.collectors import write
from ms.common import Http

NAME = "coinmetrics_stables"
SOURCE = "coinmetrics"
LICENSE = "cc_by_nc"
ASSETS = ("usdt", "usdc")
URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
log = logging.getLogger("collect")


def fetch(http: Http, asset: str) -> pd.DataFrame:
    rows, url, params = [], URL, {"assets": asset, "metrics": "SplyCur", "frequency": "1d", "page_size": 10000,
                                  "start_time": "2014-01-01"}
    while url:
        j = http.get(url, params=params).json()
        rows += j.get("data", [])
        url, params = j.get("next_page_url"), None
    df = pd.DataFrame(rows)
    if df.empty or "SplyCur" not in df:
        raise ValueError(f"coinmetrics {asset}: brak SplyCur")
    return df


def collect(con, full: bool = False) -> int:
    http = Http(min_interval=0.65)  # limit community: 10 req / 6 s
    n = 0
    for a in ASSETS:
        sid = f"CM.{a}.SplyCur"
        db.register_series(con, SOURCE, [(sid, "1d_all", f"Coin Metrics {a.upper()} podaż w obiegu")], LICENSE)
        df = fetch(http, a)
        obs = pd.to_datetime(df["time"].str[:10])
        out = pd.DataFrame({"source": SOURCE, "series_id": sid, "observed_at": obs, "known_at": obs + pd.Timedelta(days=1),
                            "value": pd.to_numeric(df["SplyCur"]), "license": LICENSE, "flags": "known_at_rule"})
        log.info("%s: %d dni %s..%s", sid, len(out), obs.min().date(), obs.max().date())
        n += write(con, out)
    return n

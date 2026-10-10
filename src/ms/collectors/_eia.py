"""EIA API v2 /seriesid: stronicowanie po offset; kontrola liczności względem `total`."""

from __future__ import annotations

import pandas as pd

from ms.common import Http, env

_http = Http(min_interval=0.5)
PAGE = 5000


def fetch_series(series_id: str) -> pd.DataFrame:
    key = env("EIA_API_KEY")
    rows, offset, total = [], 0, None
    while True:
        j = _http.get(f"https://api.eia.gov/v2/seriesid/{series_id}",
                      params={"api_key": key, "offset": offset, "length": PAGE}).json()
        if "response" not in j:
            raise RuntimeError(f"EIA {series_id}: {str(j)[:300]}")
        total = int(j["response"]["total"])
        page = j["response"]["data"]
        rows += page
        offset += len(page)
        if not page or offset >= total:
            break
    df = pd.DataFrame(rows)
    if len(df) != total or df["period"].duplicated().any():
        raise RuntimeError(f"EIA {series_id}: pobrano {len(df)} (unikalnych {df['period'].nunique()}) z total={total}")
    return df

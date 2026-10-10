"""Etykiety (tabela labels) — OSOBNO od cech. Wszystko z logret cen bazowych (ms.prices; metale = stitch_metals).

Na dniu obserwacji ceny D (start = zamknięcie D):
- sigma_5d = std(logret z 252 obs do D włącznie) × √5
- fwd_ret_5d = suma logret D+1..D+5; up_5d / down_5d: > +1,5σ / < −1,5σ (NaN, gdy brak danych)
- ścieżka 60 obs: fwd_ret_20d/60d, fwd_max_dd_60d (min skumulowanego logret, <= 0), fwd_trough_day (1..60; 0 gdy
  bez spadku), fwd_rebound_60d (od dołka do D+60), fwd_days_to_recover (pierwszy dzień po dołku z ceną >= cena D;
  0 gdy bez spadku; NaN gdy nie wróciła do D+60), end_5d (data D+5), path_end (data D+60).
NaN w logret (np. WTI 2020-04-20) w oknie -> etykieta NaN.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ms.prices import ASSETS, price_frame

H = 60
SIGMA_WINDOW = 252
THRESH = 1.5
LABEL_COLUMNS = ["sigma_5d", "fwd_ret_5d", "up_5d", "down_5d", "fwd_ret_20d", "fwd_ret_60d", "fwd_max_dd_60d",
                 "fwd_trough_day", "fwd_rebound_60d", "fwd_days_to_recover", "end_5d", "path_end"]


def compute(logret: pd.Series) -> pd.DataFrame:
    lr = logret.to_numpy(dtype=float)
    n = len(lr)
    idx = logret.index
    sigma = logret.rolling(SIGMA_WINDOW, min_periods=SIGMA_WINDOW).std().to_numpy() * np.sqrt(5)

    fwd = np.full((n, H), np.nan)  # fwd[i, k-1] = logret D+k
    for k in range(1, H + 1):
        fwd[: n - k, k - 1] = lr[k:]
    cum = np.cumsum(fwd, axis=1)  # NaN propaguje się dalej w ścieżce

    def cum_at(k):
        return cum[:, k - 1]

    out = pd.DataFrame(index=idx)
    out["sigma_5d"] = sigma
    out["fwd_ret_5d"] = cum_at(5)
    out["fwd_ret_20d"] = cum_at(20)
    out["fwd_ret_60d"] = cum_at(60)
    full = ~np.isnan(cum[:, -1])
    with np.errstate(invalid="ignore"):
        up = out["fwd_ret_5d"] > THRESH * out["sigma_5d"]
        down = out["fwd_ret_5d"] < -THRESH * out["sigma_5d"]
    ok5 = out["fwd_ret_5d"].notna() & out["sigma_5d"].notna()
    out["up_5d"] = up.where(ok5)
    out["down_5d"] = down.where(ok5)

    safe = np.where(np.isnan(cum), np.inf, cum)
    trough_idx = np.argmin(safe, axis=1)
    trough_val = cum[np.arange(n), trough_idx]
    dropped = trough_val < 0
    out["fwd_max_dd_60d"] = np.where(full, np.minimum(trough_val, 0.0), np.nan)
    out["fwd_trough_day"] = np.where(full, np.where(dropped, trough_idx + 1, 0), np.nan)
    out["fwd_rebound_60d"] = np.where(full, np.where(dropped, cum[:, -1] - trough_val, 0.0), np.nan)
    rec = np.full(n, np.nan)
    for i in np.where(full)[0]:
        if not dropped[i]:
            rec[i] = 0
            continue
        after = np.where(cum[i, trough_idx[i] + 1:] >= 0)[0]
        rec[i] = trough_idx[i] + 2 + after[0] if len(after) else np.nan
    out["fwd_days_to_recover"] = rec
    e5 = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    e5[: n - 5] = idx.values[5:]
    out["end_5d"] = e5  # data 5. obserwacji do przodu (koniec okna up/down) — do purge w walk-forward
    pe = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    pe[: n - H] = idx.values[H:]
    out["path_end"] = pe
    for c in ("sigma_5d", "fwd_ret_5d", "fwd_ret_20d", "fwd_ret_60d"):
        out.loc[~np.isfinite(out[c].astype(float)), c] = np.nan
    return out


def build(con, assets=tuple(ASSETS)) -> pd.DataFrame:
    parts = []
    for a in assets:
        lab = compute(price_frame(con, a)["logret"])
        lab.index.name = "date"
        parts.append(lab.reset_index().assign(asset=a))
    return pd.concat(parts, ignore_index=True)[["date", "asset", *LABEL_COLUMNS]]


def write(con, df: pd.DataFrame) -> None:
    con.register("lab_df", df)
    con.execute("DROP TABLE IF EXISTS labels")
    con.execute("CREATE TABLE labels AS SELECT CAST(date AS DATE) AS date, * EXCLUDE (date), now()::TIMESTAMP AS built_at FROM lab_df")
    con.unregister("lab_df")


def base_rates(con) -> pd.DataFrame:
    return con.execute("""SELECT asset, count(*) FILTER (WHERE up_5d IS NOT NULL) AS n,
                                 avg(up_5d::INT) AS up_rate, avg(down_5d::INT) AS down_rate
                          FROM labels GROUP BY asset ORDER BY asset""").df()

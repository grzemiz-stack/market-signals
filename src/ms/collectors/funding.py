"""Funding perpetual: Binance USDⓈ-M (od 2019-09) i Bybit linear (od 2020-03), BTCUSDT i ETHUSDT.

observed_at = okres funding (fundingTime obcięty do pełnej godziny), known_at = faktyczny fundingTime.
Wykrywanie obcięcia paginacji:
- strona pełna (== limit) -> zawsze kolejna strona; kolejna strona musi zaczynać się
  dokładnie tam, gdzie skończyła poprzednia (bez przeskoku > 1 interwału),
- na końcu porównanie z siatką 8h od pierwszego rekordu -> lista dziur w logu (test 3 pilnuje zera).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import write
from ms.common import Http

NAME = "funding"
LICENSE = "tos_restricted"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
H8 = 8 * 3600 * 1000
log = logging.getLogger("collect")

RAW = pa.DataFrameSchema(
    {"ts": pa.Column("int64", pa.Check.gt(1.5e12)), "rate": pa.Column(float, pa.Check.in_range(-0.05, 0.05))},
    unique=["ts"], coerce=True,
)


class PaginationError(Exception):
    pass


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def fetch_binance(http: Http, sym: str, start_ms: int) -> pd.DataFrame:
    out, cur, limit = [], start_ms, 1000
    while True:
        page = http.get("https://fapi.binance.com/fapi/v1/fundingRate",
                        params={"symbol": sym, "startTime": cur, "limit": limit}).json()
        if not isinstance(page, list):
            raise PaginationError(f"binance {sym}: {page}")
        if out and page and page[0]["fundingTime"] - out[-1]["fundingTime"] > H8 + 60_000:
            raise PaginationError(f"binance {sym}: przeskok między stronami przy {out[-1]['fundingTime']}")
        out += page
        if len(page) < limit:
            break
        cur = page[-1]["fundingTime"] + 1
    df = pd.DataFrame(out)
    return RAW.validate(pd.DataFrame({"ts": df["fundingTime"], "rate": df["fundingRate"]})) if out else pd.DataFrame()


def fetch_bybit(http: Http, sym: str, start_ms: int) -> pd.DataFrame:
    """Bybit zwraca malejąco, max 200; stronicujemy wstecz po endTime."""
    out, end, limit = [], _now_ms(), 200
    while True:
        j = http.get("https://api.bybit.com/v5/market/funding/history",
                     params={"category": "linear", "symbol": sym, "startTime": start_ms, "endTime": end, "limit": limit}).json()
        if j.get("retCode") != 0:
            raise PaginationError(f"bybit {sym}: {j}")
        page = [(int(x["fundingRateTimestamp"]), x["fundingRate"]) for x in j["result"]["list"]]
        if out and page and out[-1][0] - page[0][0] > H8 + 60_000:
            raise PaginationError(f"bybit {sym}: przeskok między stronami przy {out[-1][0]}")
        out += page
        if len(page) < limit:
            break
        end = page[-1][0] - 1
    return RAW.validate(pd.DataFrame(out, columns=["ts", "rate"])) if out else pd.DataFrame()


def grid_gaps(ts: pd.Series, step_ms: int = H8) -> list[pd.Timestamp]:
    """Brakujące okresy 8h między pierwszym a ostatnim rekordem."""
    per = pd.to_datetime(ts, unit="ms").dt.floor("h")
    full = pd.date_range(per.min(), per.max(), freq=pd.Timedelta(milliseconds=step_ms))
    return sorted(set(full) - set(per))


def to_long(raw: pd.DataFrame, source: str, sid: str) -> pd.DataFrame:
    known = pd.to_datetime(raw["ts"], unit="ms")
    return pd.DataFrame({"source": source, "series_id": sid, "observed_at": known.dt.floor("h"),
                         "known_at": known, "value": raw["rate"].astype(float), "license": LICENSE})


def collect(con, full: bool = False) -> int:
    n = 0
    venues = {
        "binance": (fetch_binance, Http(min_interval=0.25), int(datetime(2019, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)),
        "bybit": (fetch_bybit, Http(min_interval=0.25), int(datetime(2020, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)),
    }
    for venue, (fetch, http, start) in venues.items():
        for sym in SYMBOLS:
            sid = f"{sym}.funding.{venue}"
            db.register_series(con, venue, [(sid, "8h", f"{venue} {sym} perpetual funding rate")], LICENSE)
            since = start
            if not full:
                last = con.execute("SELECT max(known_at) FROM observations WHERE source=? AND series_id=?", [venue, sid]).fetchone()[0]
                if last is not None:
                    since = int(pd.Timestamp(last).tz_localize("UTC").timestamp() * 1000) - 3 * H8
            raw = fetch(http, sym, since)
            if raw.empty:
                continue
            gaps = grid_gaps(raw["ts"])
            if gaps:
                log.warning("%s: %d dziur w siatce 8h, np. %s", sid, len(gaps), gaps[:5])
            n += write(con, to_long(raw, venue, sid))
            log.info("%s: %d rekordów od %s", sid, len(raw), pd.to_datetime(raw.ts.min(), unit="ms"))
    return n

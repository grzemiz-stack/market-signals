"""Wspólne narzędzia kolektorów: HTTP z backoffem, cache, strefy czasowe, schemat wyjścia."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pandera.pandas as pa
import requests
from dotenv import load_dotenv
from pandas.tseries.holiday import USFederalHolidayCalendar

from ms.db import LICENSES, ROOT

load_dotenv(ROOT / ".env")

CACHE = ROOT / "data" / "cache"
RAW = ROOT / "data" / "raw"
INBOX = ROOT / "data" / "inbox"
ET = ZoneInfo("America/New_York")
WAW = ZoneInfo("Europe/Warsaw")
UA = "market-signals/0.1 (personal research)"

log = logging.getLogger("collect")


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"brak zmiennej {name} (.env)")
    return v


# --------------------------------------------------------------------------- czas


def local_to_utc(d: date | datetime, hhmm: str, tz: ZoneInfo = ET) -> datetime:
    """Data + godzina lokalna (np. 10:30 ET) -> naive UTC (z uwzględnieniem DST)."""
    h, m = map(int, hhmm.split(":"))
    d = d.date() if isinstance(d, datetime) else d
    return datetime.combine(d, dtime(h, m), tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def local_series_to_utc(dates: pd.Series, hhmm: str, tz: ZoneInfo = ET) -> pd.Series:
    h, m = map(int, hhmm.split(":"))
    ts = pd.to_datetime(dates).dt.normalize() + pd.Timedelta(hours=h, minutes=m)
    return ts.dt.tz_localize(tz).dt.tz_convert("UTC").dt.tz_localize(None)


_HOL = None


def us_holidays() -> set[date]:
    global _HOL
    if _HOL is None:
        _HOL = {d.date() for d in USFederalHolidayCalendar().holidays("1980-01-01", "2035-12-31")}
    return _HOL


def is_us_bday(d: date) -> bool:
    return d.weekday() < 5 and d not in us_holidays()


def next_us_bday(d: date) -> date:
    while not is_us_bday(d):
        d += timedelta(days=1)
    return d


# --------------------------------------------------------------------------- HTTP


class Http:
    """requests z minimalnym odstępem między zapytaniami i backoffem przy 429/5xx."""

    def __init__(self, min_interval: float = 0.0, timeout: float = 60):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0

    def get(self, url: str, retries: int = 5, **kw) -> requests.Response:
        delay = 5.0
        for attempt in range(retries + 1):
            dt = time.monotonic() - self._last
            if dt < self.min_interval:
                time.sleep(self.min_interval - dt)
            self._last = time.monotonic()
            try:
                r = self.s.get(url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                if attempt == retries:
                    raise
                log.warning("GET %s: %s; retry %.0fs", url, e, delay)
            else:
                if r.status_code < 400 or r.status_code == 404:
                    return r
                if r.status_code not in (418, 429, 500, 502, 503, 504) or attempt == retries:
                    r.raise_for_status()
                ra = r.headers.get("Retry-After", "")
                wait = float(ra) if ra.isdigit() else delay
                log.warning("GET %s: HTTP %s; retry %.0fs", url, r.status_code, wait)
                delay = max(delay, wait)
            time.sleep(delay)
            delay *= 2
        raise AssertionError("unreachable")


def cached_get(http: Http, url: str, path: Path, refresh: bool = False, **kw) -> bytes | None:
    """Plik w cache = brak zapytania. 404 -> None (bez zapisu)."""
    if path.exists() and not refresh:
        return path.read_bytes()
    r = http.get(url, **kw)
    if r.status_code == 404:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return r.content


# --------------------------------------------------------------------------- schemat wyjścia

OUTPUT_SCHEMA = pa.DataFrameSchema(
    {
        "source": pa.Column(str),
        "series_id": pa.Column(str),
        "observed_at": pa.Column("datetime64[ns]"),
        "known_at": pa.Column("datetime64[ns]"),
        "value": pa.Column(float, nullable=False),
        "license": pa.Column(str, pa.Check.isin(LICENSES)),
        "vintage": pa.Column(nullable=True, required=False),
        "flags": pa.Column(nullable=True, required=False),
    },
    checks=[pa.Check(lambda d: (d["known_at"] >= d["observed_at"]).all(), error="known_at < observed_at")],
    strict=True,
    coerce=True,
)


def validate_output(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ("observed_at", "known_at"):
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    return OUTPUT_SCHEMA.validate(df)


def long_frame(df: pd.DataFrame, source: str, license: str, value_cols: dict[str, str],
               observed: str = "observed_at", known: str = "known_at", flags: str | None = None) -> pd.DataFrame:
    """Szeroka ramka (kolumny wartości) -> długa (jeden wiersz na serię i obserwację)."""
    parts = []
    for col, sid in value_cols.items():
        p = pd.DataFrame({
            "source": source,
            "series_id": sid,
            "observed_at": df[observed].values,
            "known_at": df[known].values,
            "value": pd.to_numeric(df[col], errors="coerce").values,
            "license": license,
        })
        if flags:
            p["flags"] = df[flags].values
        parts.append(p.dropna(subset=["value"]))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# --------------------------------------------------------------------------- skrzynki ręczne


def archive_inbox(source: str, pattern: str = "*") -> int:
    """data/inbox/{source}/ -> data/raw/{source}/{dziś}/ + manifest (logika z snapshot_raw)."""
    import snapshot_raw as sr

    if not logging.getLogger("snapshot").handlers and not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    return sr.ingest_inbox(sr.Store(date.today()), source, pattern)


def latest_raw(source: str, name_glob: str) -> list[Path]:
    """Najnowszy zarchiwizowany plik każdej nazwy (foldery dat sortują się leksykalnie)."""
    best: dict[str, Path] = {}
    for p in sorted((RAW / source).glob(f"*/{name_glob}")):
        best[p.name.split("__")[0]] = p
    return sorted(best.values())

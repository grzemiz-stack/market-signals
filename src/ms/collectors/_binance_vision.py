"""Pobieranie plików z data.binance.vision z cache i weryfikacją .CHECKSUM."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date

import pandas as pd

from ms.common import CACHE, Http, cached_get

BASE = "https://data.binance.vision/"
_http = Http(min_interval=0.0)  # pliki statyczne; równoległość ograniczona w prefetch


class ChecksumError(Exception):
    pass


def fetch_zip(path: str, refresh: bool = False) -> bytes | None:
    """path np. data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2017-08.zip. 404 -> None."""
    local = CACHE / "binance_vision" / path
    content = cached_get(_http, BASE + path, local, refresh=refresh)
    if content is None:
        return None
    ck = cached_get(_http, BASE + path + ".CHECKSUM", local.with_name(local.name + ".CHECKSUM"), refresh=refresh)
    if ck is not None:
        want = ck.decode().split()[0]
        got = hashlib.sha256(content).hexdigest()
        if want != got:
            local.unlink(missing_ok=True)
            raise ChecksumError(f"{path}: sha256 {got} != {want}")
    return content


def read_csv_zip(content: bytes, names: list[str]) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(content))
    raw = z.read(z.namelist()[0])
    first = raw.split(b"\n", 1)[0]
    header = 0 if first[:1].isalpha() else None  # część plików ma nagłówek, część nie
    df = pd.read_csv(io.BytesIO(raw), header=header)
    if header is None:
        df.columns = names[: len(df.columns)]
    return df


def months(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def to_ms(ts: pd.Series) -> pd.Series:
    """Binance od 2025 zapisuje spot w mikrosekundach; normalizacja do ms."""
    ts = pd.to_numeric(ts)
    return ts.where(ts < 10**14, ts // 1000)


def list_keys(prefix: str) -> list[str]:
    """Listing S3 bucketu data.binance.vision (stronicowany po 1000)."""
    import re

    keys, marker = [], ""
    while True:
        r = _http.get("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision",
                      params={"delimiter": "/", "prefix": prefix, "marker": marker})
        page = re.findall(r"<Key>([^<]+)</Key>", r.text)
        keys += page
        if "<IsTruncated>true</IsTruncated>" not in r.text or not page:
            return keys
        marker = page[-1]

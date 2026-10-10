"""E4-hist (etap 4N, trzecia próba): pełne pliki GDELT 2.0 export + mentions dla 42 dni E4 (docs/ETAP4N-E4-PLAN.md pkt 7).

uv run src/e4hist_gdelt.py fetch    # pobranie zip-ów z okien [D−1 22:00, D 22:00] UTC (md5 z masterfilelist) + wyciąg do bazy

Zapis: data/raw/gdelt_e4/<plik>.zip (surowe, jednorazowo) i data/gdelt_e4.duckdb (tylko kolumny z planu: zdarzenie, czas,
kraje aktorów, CAMEO, NumMentions, adres; wzmianki: zdarzenie, czas, typ, adres). Bez filtra do konfliktów i bez filtra
USA–USA (plan pkt 7). Licencja GDELT: unlimited and unrestricted use (cytowanie przy redystrybucji — tu brak). Wznawialne.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db  # noqa: E402

MASTER = "https://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
RAW = db.ROOT / "data" / "raw" / "gdelt_e4"
DB = db.ROOT / "data" / "gdelt_e4.duckdb"
UA = "market-signals/0.1 (private research; GDELT E4-hist)"
EXP = dict(id=0, a1c=7, a2c=17, code=26, root=28, ment=31, added=59, url=60)
MEN = dict(id=0, time=2, mtype=3, url=5)
csv.field_size_limit(10_000_000)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ev (event_id BIGINT, dateadded TIMESTAMP, a1c VARCHAR, a2c VARCHAR, event_code VARCHAR,
    root_code VARCHAR, num_mentions INTEGER, source_url VARCHAR, file VARCHAR);
CREATE TABLE IF NOT EXISTS men (event_id BIGINT, mention_time TIMESTAMP, mention_type INTEGER, url VARCHAR, file VARCHAR);
CREATE TABLE IF NOT EXISTS files (file VARCHAR PRIMARY KEY, md5 VARCHAR, bytes BIGINT, rows BIGINT);
"""


def windows(days) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    return [(pd.Timestamp(d) - pd.Timedelta(hours=2), pd.Timestamp(d) + pd.Timedelta(hours=22)) for d in days]


def file_list(master_text: str, days) -> pd.DataFrame:
    rows = []
    for line in master_text.splitlines():
        p = line.split()
        if len(p) != 3:
            continue
        m = re.search(r"/(\d{14})\.(export|mentions)\.CSV\.zip$", p[2])
        if m:
            rows.append((pd.Timestamp(m.group(1)), m.group(2), int(p[0]), p[1], p[2]))
    f = pd.DataFrame(rows, columns=["ts", "kind", "bytes", "md5", "url"])
    keep = pd.Series(False, index=f.index)
    for lo, hi in windows(days):
        keep |= (f.ts > lo) & (f.ts <= hi)
    return f[keep].drop_duplicates("url").sort_values(["ts", "kind"])


def _ts(s: str):
    try:
        return pd.Timestamp(s[:14]) if s and len(s) >= 14 else None
    except ValueError:
        return None


def parse(kind: str, content: bytes, name: str) -> list[tuple]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    out = []
    for r in csv.reader(io.StringIO(text), delimiter="\t"):
        try:
            if kind == "export":
                out.append((int(r[EXP["id"]]), _ts(r[EXP["added"]]), r[EXP["a1c"]] or None, r[EXP["a2c"]] or None,
                            r[EXP["code"]], r[EXP["root"]], int(r[EXP["ment"]] or 0), r[EXP["url"]], name))
            else:
                out.append((int(r[MEN["id"]]), _ts(r[MEN["time"]]), int(r[MEN["mtype"]] or 0), r[MEN["url"]], name))
        except (IndexError, ValueError):
            continue
    return out


def fetch_one(sess: requests.Session, row) -> tuple:
    name = row.url.rsplit("/", 1)[1]
    path = RAW / name
    if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == row.md5:
        content = path.read_bytes()
    else:
        for attempt in range(4):
            r = sess.get(row.url, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200 and hashlib.md5(r.content).hexdigest() == row.md5:
                content = r.content
                path.write_bytes(content)
                break
        else:
            raise IOError(f"{name}: pobranie nieudane albo md5 niezgodne")
    return name, row.kind, row.md5, len(content), parse(row.kind, content, name)


def fetch(days) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute(SCHEMA)
    done = {r[0] for r in con.execute("SELECT file FROM files").fetchall()}
    master = requests.get(MASTER, headers={"User-Agent": UA}, timeout=120).text
    todo = [r for r in file_list(master, days).itertuples() if r.url.rsplit("/", 1)[1] not in done]
    stats = {"plikow": len(todo), "bajtow": 0, "wierszy": 0}
    with requests.Session() as sess, ThreadPoolExecutor(max_workers=4) as pool:
        for name, kind, md5, n, rows in pool.map(lambda r: fetch_one(sess, r), todo):
            if rows:
                con.executemany(f"INSERT INTO {'ev' if kind == 'export' else 'men'} VALUES ({','.join('?' * len(rows[0]))})", rows)
            con.execute("INSERT INTO files VALUES (?,?,?,?)", [name, md5, n, len(rows)])
            stats["bajtow"] += n
            stats["wierszy"] += len(rows)
    con.close()
    return stats


def main() -> int:
    import validate_causes as V

    m = duckdb.connect(str(db.DB_PATH), read_only=True)
    days = pd.to_datetime(V.e4_days(m)["day"]).tolist()
    m.close()
    print(fetch(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())

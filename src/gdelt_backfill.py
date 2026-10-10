"""GDELT 2.0 Events: pobieranie strumieniowe 15-min plików export, filtr w locie, zapis do data/gdelt.duckdb.

Uruchomienie (backfill, w tle):  caffeinate -i uv run src/gdelt_backfill.py
Ponowienie nieudanych:           uv run src/gdelt_backfill.py --retry-failed
Przyrost (po backfillu, launchd): ten sam skrypt — pomija pliki już przetworzone.

Filtr (decyzja etapu 1; pary USA–USA wycinamy dopiero w cechach):
  (EventRootCode ∈ {14,15,17,18,19,20} LUB EventCode = 163)
  ORAZ (Actor1CountryCode LUB Actor2CountryCode ∈ AKTORZY)
  ORAZ GoldsteinScale ≤ −5 ORAZ NumMentions ≥ 10
known_at = DATEADDED (UTC), observed_at = SQLDATE.

Wznawialność: tabela files (url, status ok|failed|missing). 404 = brak pliku u źródła (missing),
inne błędy po 4 próbach z backoffem = failed (lista do ponowienia; nie przerywa całości).
Osobna baza, bo market.duckdb ma jednego pisarza (launchd 23:30). Odczyt z market: ms.db.attach_gdelt().
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import queue
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import os

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("GDELT_DB", ROOT / "data" / "gdelt.duckdb"))  # GDELT_DB: baza robocza do prób
LOG = ROOT / "logs" / "gdelt.log"
MASTER = "https://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
UA = "market-signals/0.1 (personal research)"
WORKERS = 8
BATCH = 200
LICENSE = "cc_by"

ROOTS = {"14", "15", "17", "18", "19", "20"}
ACTORS = {"SAU", "IRN", "IRQ", "ARE", "KWT", "RUS", "VEN", "LBY", "NGA", "ISR", "UKR", "CHN", "USA"}
NCOLS = 61
# indeksy kolumn GDELT 2.0 export
C = dict(id=0, sqldate=1, a1=5, a1name=6, a1c=7, a2=15, a2name=16, a2c=17, root_ev=25, code=26, base=27, rootc=28,
         quad=29, gold=30, ment=31, nsrc=32, nart=33, tone=34, geo_cc=53, lat=56, lon=57, added=59, url=60)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id BIGINT PRIMARY KEY, observed_at DATE NOT NULL, known_at TIMESTAMP NOT NULL,
    actor1_code VARCHAR, actor1_name VARCHAR, actor1_country VARCHAR,
    actor2_code VARCHAR, actor2_name VARCHAR, actor2_country VARCHAR,
    is_root BOOLEAN, event_code VARCHAR, event_base_code VARCHAR, root_code VARCHAR, quad_class TINYINT,
    goldstein DOUBLE, num_mentions INTEGER, num_sources INTEGER, num_articles INTEGER, avg_tone DOUBLE,
    action_geo_country VARCHAR, action_geo_lat DOUBLE, action_geo_long DOUBLE,
    source_url VARCHAR, source_file VARCHAR NOT NULL, license VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    url VARCHAR PRIMARY KEY, file_ts TIMESTAMP NOT NULL, status VARCHAR NOT NULL,
    rows_total INTEGER, rows_kept INTEGER, bytes INTEGER, attempts INTEGER, error VARCHAR, processed_at TIMESTAMP NOT NULL
);
"""

log = logging.getLogger("gdelt")
_tls = threading.local()


def session() -> requests.Session:
    if not hasattr(_tls, "s"):
        _tls.s = requests.Session()
        _tls.s.headers["User-Agent"] = UA
    return _tls.s


def master_list() -> list[tuple[str, str, int]]:
    """[(url, md5, size)] plików export, od najstarszego."""
    r = session().get(MASTER, timeout=300)
    r.raise_for_status()
    out = []
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].endswith(".export.CSV.zip"):
            out.append((parts[2].replace("http://", "https://"), parts[1], int(parts[0])))
    return out


def file_ts(url: str) -> datetime:
    return datetime.strptime(url.rsplit("/", 1)[1][:14], "%Y%m%d%H%M%S")


def keep(row: list[str]) -> bool:
    try:
        return ((row[C["rootc"]] in ROOTS or row[C["code"]] == "163")
                and (row[C["a1c"]] in ACTORS or row[C["a2c"]] in ACTORS)
                and row[C["gold"]] != "" and float(row[C["gold"]]) <= -5
                and int(row[C["ment"]] or 0) >= 10)
    except ValueError:
        return False


def num(x: str, f=float):
    return f(x) if x not in ("", None) else None


def to_record(row: list[str], src: str) -> tuple:
    return (int(row[C["id"]]), datetime.strptime(row[C["sqldate"]], "%Y%m%d").date(),
            datetime.strptime(row[C["added"]], "%Y%m%d%H%M%S"),
            row[C["a1"]] or None, row[C["a1name"]] or None, row[C["a1c"]] or None,
            row[C["a2"]] or None, row[C["a2name"]] or None, row[C["a2c"]] or None,
            row[C["root_ev"]] == "1", row[C["code"]], row[C["base"]], row[C["rootc"]], num(row[C["quad"]], int),
            num(row[C["gold"]]), num(row[C["ment"]], int), num(row[C["nsrc"]], int), num(row[C["nart"]], int),
            num(row[C["tone"]]), row[C["geo_cc"]] or None, num(row[C["lat"]]), num(row[C["lon"]]),
            row[C["url"]] or None, src, LICENSE)


class FormatError(Exception):
    pass


def process(item: tuple[str, str, int]) -> dict:
    """Pobranie + md5 + filtr. Zwraca wynik; nigdy nie rzuca (błąd -> status)."""
    url, md5, size = item
    delay, err, attempts = 2.0, None, 0
    for attempts in range(1, 5):
        try:
            r = session().get(url, timeout=60)
            if r.status_code == 404:
                return dict(url=url, status="missing", attempts=attempts, error="HTTP 404")
            r.raise_for_status()
            if hashlib.md5(r.content).hexdigest() != md5:
                raise IOError("md5 niezgodne z masterfilelist")
            z = zipfile.ZipFile(io.BytesIO(r.content))
            text = z.read(z.namelist()[0]).decode("utf-8", "replace")
            total, kept = 0, []
            for row in csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE):
                if not row:
                    continue
                if len(row) != NCOLS:
                    raise FormatError(f"{len(row)} kolumn zamiast {NCOLS}")
                total += 1
                if keep(row):
                    kept.append(to_record(row, url.rsplit("/", 1)[1]))
            return dict(url=url, status="ok", total=total, kept=kept, bytes=len(r.content), attempts=attempts)
        except FormatError as e:
            return dict(url=url, status="failed", attempts=attempts, error=f"format: {e}")
        except Exception as e:  # sieć, zip, md5 -> retry
            err = f"{type(e).__name__}: {e}"
            time.sleep(delay)
            delay *= 2
    return dict(url=url, status="failed", attempts=attempts, error=err[:500] if err else "?")


def db_size_mb() -> float:
    """Plik bazy + WAL (świeże dane DuckDB trzyma w .wal do checkpointu)."""
    wal = DB.with_name(DB.name + ".wal")
    return (DB.stat().st_size + (wal.stat().st_size if wal.exists() else 0)) / 1e6


def writer(con, results: "queue.Queue[dict | None]", total_todo: int, t0: float) -> dict:
    """Jedyny wątek piszący do bazy: partie po BATCH plików w transakcji."""
    stats = dict(done=0, ok=0, failed=0, missing=0, rows=0, kept=0, bytes=0)
    buf: list[dict] = []

    def flush():
        if not buf:
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        con.execute("BEGIN")
        recs = [rec for r in buf if r["status"] == "ok" for rec in r["kept"]]
        if recs:
            con.executemany(f"INSERT INTO events VALUES ({','.join('?' * 25)}) ON CONFLICT DO NOTHING", recs)
        con.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?)",
                        [(r["url"], file_ts(r["url"]), r["status"], r.get("total"), len(r.get("kept", [])),
                          r.get("bytes"), r.get("attempts"), r.get("error"), now) for r in buf])
        con.execute("COMMIT")
        buf.clear()

    while True:
        r = results.get()
        if r is None:
            break
        buf.append(r)
        stats["done"] += 1
        stats[r["status"]] += 1
        if r["status"] == "ok":
            stats["rows"] += r["total"]
            stats["kept"] += len(r["kept"])
            stats["bytes"] += r["bytes"]
        elif r["status"] == "failed":
            log.warning("failed %s: %s", r["url"], r.get("error"))
        if len(buf) >= BATCH:
            flush()
        if stats["done"] % 1000 == 0:
            flush()
            el = time.time() - t0
            rate = stats["done"] / el
            eta = (total_todo - stats["done"]) / rate if rate else 0
            log.info("postęp %d/%d (%.1f%%) | %.1f plików/s | ETA %.1f h | przepuszczone %d/%d wierszy (%.2f%%) | "
                     "ok %d, failed %d, missing %d | %.0f MB pobrane | baza %.0f MB",
                     stats["done"], total_todo, 100 * stats["done"] / total_todo, rate, eta / 3600,
                     stats["kept"], stats["rows"], 100 * stats["kept"] / max(stats["rows"], 1),
                     stats["ok"], stats["failed"], stats["missing"], stats["bytes"] / 1e6, db_size_mb())
    flush()
    return stats


def main(argv: list[str]) -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute(SCHEMA)

    items = master_list()
    if "--retry-failed" in argv:
        failed = {u for (u,) in con.execute("SELECT url FROM files WHERE status='failed'").fetchall()}
        todo = [it for it in items if it[0] in failed]
    else:
        done = {u for (u,) in con.execute("SELECT url FROM files WHERE status IN ('ok','missing')").fetchall()}
        todo = [it for it in items if it[0] not in done]
    if "--limit" in argv:
        todo = todo[: int(argv[argv.index("--limit") + 1])]
    log.info("masterfilelist: %d plików export (%s .. %s); do zrobienia %d",
             len(items), file_ts(items[0][0]), file_ts(items[-1][0]), len(todo))
    if not todo:
        return 0

    results: queue.Queue = queue.Queue(maxsize=WORKERS * 50)
    t0 = time.time()
    out: dict = {}
    wt = threading.Thread(target=lambda: out.update(writer(con, results, len(todo), t0)))
    wt.start()
    with ThreadPoolExecutor(WORKERS) as ex:
        for i in range(0, len(todo), 2000):  # porcje: nie trzymamy 400 tys. futures w pamięci
            for r in ex.map(process, todo[i : i + 2000]):
                results.put(r)
    results.put(None)
    wt.join()
    log.info("koniec przebiegu: %s; czas %.1f h", {k: v for k, v in out.items()}, (time.time() - t0) / 3600)
    nfail = con.execute("SELECT count(*) FROM files WHERE status='failed'").fetchone()[0]
    if nfail and "--retry-failed" not in argv:
        log.info("ponawiam %d nieudanych plików", nfail)
        con.close()
        return main(argv + ["--retry-failed"])
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

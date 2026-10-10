"""Surowe dzienne snapshoty danych, których historii nie da się odtworzyć później.

Bez parsowania. Każdy plik trafia do data/raw/{source}/{YYYY-MM-DD}/{nazwa}
bez zmian treści, a każde pobranie (też nieudane) do data/raw/manifest.jsonl.

Źródła i ich ograniczenia: patrz docs/OPERACJE.md, sekcja „Snapshoty surowe”.
"""

from __future__ import annotations

import os

import calendar
import hashlib
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INBOX = ROOT / "data" / "inbox"
MANIFEST = RAW / "manifest.jsonl"
LOG_FILE = ROOT / "logs" / "snapshot.log"

UA = "market-signals/0.1 (personal research snapshot; python-requests)"
TIMEOUT = 60

log = logging.getLogger("snapshot")


# --------------------------------------------------------------------------- #
# Manifest i zapis
# --------------------------------------------------------------------------- #


class Store:
    """Zapis plików + manifest. Idempotentny względem ostatniego sha256 (source, subdir, filename).

    subdir = "" dla zwykłych folderów dziennych; "initial"/"backfill" to osobne serie,
    żeby jednorazowe pobrania nie były punktem odniesienia dla dziennych."""

    def __init__(self, today: date):
        self.today = today
        self.last_sha: dict[tuple[str, str, str], str] = {}
        if MANIFEST.exists():
            for line in MANIFEST.read_text().splitlines():
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("sha256"):
                    self.last_sha[(e["source"], self._subdir_of(e), e["filename"])] = e["sha256"]

    @staticmethod
    def _subdir_of(e: dict) -> str:
        if "subdir" in e:
            return e["subdir"]
        # wpisy sprzed pola subdir: odczyt z path
        parts = Path(e.get("path", "")).parts
        return parts[3] if len(parts) > 4 and parts[3] in ("initial", "backfill") else ""

    def _append(self, entry: dict) -> None:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _base(self, source: str, filename: str, url: str, http_status: int | None) -> dict:
        return {
            "source": source,
            "filename": filename,
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "snapshot_date": self.today.isoformat(),
            "http_status": http_status,
        }

    def save(
        self,
        source: str,
        filename: str,
        content: bytes,
        url: str,
        http_status: int | None,
        subdir: str | None = None,
        **extra,
    ) -> dict:
        sha = hashlib.sha256(content).hexdigest()
        entry = self._base(source, filename, url, http_status)
        entry.update(bytes=len(content), sha256=sha, **extra)
        key = (source, subdir or "", filename)
        if subdir:
            entry["subdir"] = subdir

        if self.last_sha.get(key) == sha:
            entry["unchanged"] = True
            log.info("%s/%s unchanged (%s)", source, filename, sha[:12])
        else:
            folder = RAW / source / (subdir or self.today.isoformat())
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / filename
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                # drugi przebieg tego samego dnia z inną treścią: nie nadpisujemy
                stamp = datetime.now().strftime("%H%M%S")
                path = folder / f"{path.stem}__{stamp}{path.suffix}"
            path.write_bytes(content)
            entry["unchanged"] = False
            entry["path"] = str(path.relative_to(ROOT))
            log.info("%s/%s saved %d B -> %s", source, filename, len(content), entry["path"])

        self.last_sha[key] = sha
        self._append(entry)
        return entry

    def fail(self, source: str, filename: str, url: str, http_status: int | None, error: str) -> None:
        entry = self._base(source, filename, url, http_status)
        entry["error"] = error[:500]
        self._append(entry)
        log.error("%s/%s FAILED status=%s: %s", source, filename, http_status, error[:200])


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


class FetchError(Exception):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


def http_get(session: requests.Session, url: str, retries: int = 4, timeout: float = TIMEOUT, **kw) -> requests.Response:
    """GET z backoffem przy 429/5xx. Inne błędy HTTP -> FetchError od razu."""
    delay = 5.0
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout, **kw)
        except requests.RequestException as e:
            if attempt == retries:
                raise FetchError(f"{type(e).__name__}: {e}") from e
            log.warning("GET %s: %s, retry in %.0fs", url, e, delay)
        else:
            if r.status_code == 200:
                return r
            if r.status_code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise FetchError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code)
            wait = float(r.headers.get("Retry-After", delay)) if r.headers.get("Retry-After", "").isdigit() else delay
            log.warning("GET %s: HTTP %s, retry in %.0fs", url, r.status_code, wait)
            delay = wait
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")


def fetch_file(store: Store, session: requests.Session, source: str, url: str, filename: str | None = None) -> None:
    filename = filename or url.rsplit("/", 1)[-1]
    try:
        r = http_get(session, url)
    except FetchError as e:
        store.fail(source, filename, url, e.status, str(e))
        raise
    store.save(source, filename, r.content, url, r.status_code)


def ingest_inbox(store: Store, source: str, pattern: str = "*") -> int:
    """Pliki pobrane ręcznie do data/inbox/{source}/ -> raw + manifest; inbox czyszczony."""
    folder = INBOX / source
    folder.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(folder.glob(pattern)):
        if not p.is_file() or p.name.startswith("."):
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        store.save(source, p.name, p.read_bytes(), f"manual-inbox:{p.name}", None, file_mtime=mtime)
        p.unlink()
        n += 1
    if n == 0:
        log.info("%s: inbox empty (%s)", source, folder.relative_to(ROOT))
    return n


# --------------------------------------------------------------------------- #
# 1. COMEX — tylko ręczna skrzynka (CME blokuje i zakazuje automatów, zob. docs/OPERACJE.md)
# --------------------------------------------------------------------------- #


def snap_comex(store: Store, session: requests.Session) -> None:
    ingest_inbox(store, "comex", "*.xls*")


# --------------------------------------------------------------------------- #
# 2. Krzywa ropy (yfinance)
# --------------------------------------------------------------------------- #

MONTH_CODES = "FGHJKMNQUVXZ"


def _prev_bday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _is_bday(d: date) -> bool:
    return d.weekday() < 5


def _add_months(y: int, m: int, k: int) -> tuple[int, int]:
    m0 = y * 12 + (m - 1) + k
    return m0 // 12, m0 % 12 + 1


def last_trade_cl(y: int, m: int) -> date:
    """NYMEX CL: 3 dni robocze przed 25. dniem miesiąca poprzedzającego (4, gdy 25. nie jest dniem roboczym)."""
    py, pm = _add_months(y, m, -1)
    d = date(py, pm, 25)
    n = 3 if _is_bday(d) else 4
    for _ in range(n):
        d = _prev_bday(d)
    return d


def last_trade_bz(y: int, m: int) -> date:
    """NYMEX BZ (Brent last day financial): ostatni dzień roboczy drugiego miesiąca przed miesiącem kontraktu."""
    py, pm = _add_months(y, m, -2)
    d = date(py, pm, calendar.monthrange(py, pm)[1])
    while not _is_bday(d):
        d -= timedelta(days=1)
    return d


def candidate_contracts(root: str, today: date, n: int) -> list[tuple[str, date]]:
    """Kolejne niewygasłe kontrakty. Święta giełdowe pominięte -> brak danych dla
    pierwszego kandydata obsługuje fetch (przejście do następnego)."""
    rule = last_trade_cl if root == "CL" else last_trade_bz
    out = []
    k = 0
    while len(out) < n:
        y, m = _add_months(today.year, today.month, k)
        ltd = rule(y, m)
        if ltd >= today:
            out.append((f"{root}{MONTH_CODES[m - 1]}{y % 100:02d}.NYM", ltd))
        k += 1
    return out


class Throttle:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self.last = 0.0

    def wait(self) -> None:
        dt = time.monotonic() - self.last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self.last = time.monotonic()


def snap_curve(store: Store, session: requests.Session) -> None:
    import yfinance as yf
    from yfinance.exceptions import YFRateLimitError

    throttle = Throttle(1.0)
    day_dir = RAW / "curve" / store.today.isoformat()
    curve: dict[str, list[dict]] = {}
    errors = []

    for root in ("CL", "BZ"):
        curve[root] = []
        for sym, ltd in candidate_contracts(root, store.today, 8):
            if len(curve[root]) == 6:
                break
            fname = f"{sym}.csv"
            # cache: dzisiejszy plik już jest -> bez zapytania
            if (day_dir / fname).exists():
                log.info("curve/%s cached, skip request", fname)
                curve[root].append({"month": len(curve[root]) + 1, "symbol": sym, "last_trade": ltd.isoformat()})
                continue

            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym} (yfinance {yf.__version__})"
            df = None
            delay = 5.0
            for attempt in range(5):
                throttle.wait()
                try:
                    df = yf.Ticker(sym).history(period="1mo", interval="1d", auto_adjust=False, actions=False)
                    break
                except YFRateLimitError:
                    log.warning("curve %s: 429, backoff %.0fs", sym, delay)
                    time.sleep(delay)
                    delay *= 2
                except Exception as e:  # yfinance rzuca różne rzeczy przy braku symbolu
                    log.warning("curve %s: %s", sym, e)
                    break
            if df is None or df.empty:
                store.fail("curve", fname, url, None, "no data (expired/unknown symbol or rate limited)")
                errors.append(sym)
                continue
            store.save("curve", fname, df.to_csv().encode(), url, 200)
            curve[root].append({"month": len(curve[root]) + 1, "symbol": sym, "last_trade": ltd.isoformat()})

    mapping = {"snapshot_date": store.today.isoformat(), "rules": "CL: 3 bday before 25th of prior month; BZ: last bday of 2nd prior month (weekends only, no holiday calendar)", "contracts": curve}
    store.save("curve", "curve_map.json", json.dumps(mapping, indent=2).encode(), "derived:contract-roll", None)

    short = [r for r in curve if len(curve[r]) < 6]
    if short:
        raise RuntimeError(f"curve incomplete for {short}; failed symbols: {errors}")


# --------------------------------------------------------------------------- #
# 3. GPR + TPU (Caldara–Iacoviello) — zawsze cały plik, ogon jest rewidowany
# --------------------------------------------------------------------------- #


def snap_gpr(store: Store, session: requests.Session) -> None:
    fetch_file(store, session, "gpr", "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls")


def snap_tpu(store: Store, session: requests.Session) -> None:
    # arkusz TPU_DAILY jest w tym samym pliku co miesięczny
    fetch_file(store, session, "tpu", "https://www.matteoiacoviello.com/tpu_files/tpu_web_latest.xlsx")


# --------------------------------------------------------------------------- #
# 4. Baker Hughes rig count — tylko ręczna skrzynka (Akamai 403/timeout dla automatów)
# --------------------------------------------------------------------------- #


def snap_bakerhughes(store: Store, session: requests.Session) -> None:
    ingest_inbox(store, "bakerhughes")


# --------------------------------------------------------------------------- #
# 5. Coin Metrics
# --------------------------------------------------------------------------- #

CM_REPO = "coinmetrics/data"
CM_API = "https://community-api.coinmetrics.io/v4"
CM_ASSETS = ("btc", "eth")
CM_LOOKBACK_DAYS = 10  # ostatnie dni bywają rewidowane


def snap_coinmetrics_initial(store: Store, session: requests.Session) -> None:
    """Jednorazowo: csv/btc.csv i csv/eth.csv z repo, przypięte do commita."""
    folder = RAW / "coinmetrics" / "initial"
    if folder.exists() and any(folder.iterdir()):
        log.info("coinmetrics/initial already present, skip")
        return
    r = http_get(session, f"https://api.github.com/repos/{CM_REPO}/commits/master")
    commit = r.json()["sha"]
    for a in CM_ASSETS:
        url = f"https://raw.githubusercontent.com/{CM_REPO}/{commit}/csv/{a}.csv"
        resp = http_get(session, url)
        store.save("coinmetrics", f"{a}.csv", resp.content, url, resp.status_code, subdir="initial", commit=commit)


CM_BACKFILL_START = date(2026, 5, 20)  # repo stoi od 2026-05-24; zakładka kilku dni


def cm_fetch(store: Store, session: requests.Session, start: date, end: date | None, subdir: str | None) -> None:
    """Community API: wszystkie metryki community 1d dla CM_ASSETS od start (do end włącznie)."""
    throttle = Throttle(0.65)  # limit community: 10 req / 6 s

    def get(url: str, **params) -> requests.Response:
        throttle.wait()
        return http_get(session, url, params=params or None)

    for a in CM_ASSETS:
        cat = get(f"{CM_API}/catalog-v2/asset-metrics", assets=a, page_size=10000).json()
        metrics = sorted(
            m["metric"]
            for d in cat["data"]
            for m in d["metrics"]
            if any(f["frequency"] == "1d" and f.get("community") for f in m["frequencies"])
        )
        log.info("coinmetrics %s: %d community 1d metrics", a, len(metrics))
        for ci in range(0, len(metrics), 40):
            chunk = metrics[ci : ci + 40]
            url = f"{CM_API}/timeseries/asset-metrics"
            params = dict(assets=a, metrics=",".join(chunk), frequency="1d", start_time=start.isoformat(),
                          page_size=10000, ignore_unsupported_errors="true")
            if end:
                params["end_time"] = end.isoformat()
            page = 1
            while True:
                r = get(url, **params) if page == 1 else get(url)
                name = f"asset-metrics_{a}_c{ci // 40 + 1:02d}_p{page:02d}.json"
                store.save("coinmetrics", name, r.content, r.url, r.status_code, subdir=subdir)
                nxt = r.json().get("next_page_url")
                if not nxt:
                    break
                url, page = nxt, page + 1


def snap_coinmetrics_daily(store: Store, session: requests.Session) -> None:
    cm_fetch(store, session, store.today - timedelta(days=CM_LOOKBACK_DAYS), None, None)


def snap_coinmetrics_backfill(store: Store, session: requests.Session) -> None:
    """Jednorazowo: luka między repo (do 2026-05-24) a dziennym przyrostem."""
    folder = RAW / "coinmetrics" / "backfill"
    if folder.exists() and any(folder.iterdir()):
        log.info("coinmetrics/backfill already present, skip")
        return
    cm_fetch(store, session, CM_BACKFILL_START, store.today, "backfill")


# --------------------------------------------------------------------------- #


SOURCES = [
    ("comex", snap_comex),
    ("curve", snap_curve),
    ("gpr", snap_gpr),
    ("tpu", snap_tpu),
    ("bakerhughes", snap_bakerhughes),
    ("coinmetrics_initial", snap_coinmetrics_initial),
    ("coinmetrics_backfill", snap_coinmetrics_backfill),
    ("coinmetrics_daily", snap_coinmetrics_daily),
]


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(fh)
    root.addHandler(sh)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def main(argv: list[str]) -> int:
    setup_logging()
    only = set(argv[1:])
    # data lokalna (uruchomienie 23:30 PL = ten sam dzień handlowy w CT); MS_SNAPSHOT_DATE = data startu joba
    today = date.fromisoformat(os.environ["MS_SNAPSHOT_DATE"]) if os.environ.get("MS_SNAPSHOT_DATE") else date.today()
    store = Store(today)
    session = requests.Session()
    session.headers["User-Agent"] = UA
    log.info("=== snapshot start %s ===", today)
    failed = []
    for name, fn in SOURCES:
        if only and name not in only:
            continue
        try:
            fn(store, session)
        except Exception as e:
            log.exception("source %s failed: %s", name, e)
            failed.append(name)
    log.info("=== snapshot end; failed: %s ===", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

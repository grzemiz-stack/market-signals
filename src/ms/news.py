"""Etap 4N-live: zbieranie wiadomości z kanałów RSS/oficjalnych API (docs/ETAP4N-LIVE-PLAN.md, DECISIONS 2026-10-07).

Zasady: tylko kanały z SOURCES (zweryfikowane: kanał, robots.txt wg RFC 9309, ToS); przed pobraniem kanału sprawdzany
robots.txt (cache 24 h) — zabronione albo 401/403 -> źródło pominięte, nigdy obejście (inny User-Agent itp.).
Zapis: tytuł, lead z kanału bez zmian, URL, published_at (UTC, NULL gdy brak — flaga), known_at = moment pierwszego
pobrania, źródło, hash. Pełnych artykułów nie pobieramy. Surowe pliki: data/raw/news/ + data/raw/news/manifest.jsonl.
Wiadomości NIE są cechą żadnego modelu (test: tests/test_news.py). Klasyfikacja LLM — dopiero po walidacji 4N.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from ms import db

load_dotenv(db.ROOT / ".env")

NEWS_DB = db.ROOT / "data" / "news.duckdb"
RAW = db.ROOT / "data" / "raw" / "news"
MANIFEST = RAW / "manifest.jsonl"
ROBOTS_CACHE = db.ROOT / "data" / "cache" / "news_robots"
UA = "market-signals/0.1 (private personal RSS reader; 1 request/hour)"
TOKEN = "market-signals"
SEC_OFF = "brak MS_CONTACT_EMAIL (SEC wymaga e-maila kontaktowego w User-Agent, bez niego 403)"


def sec_source(contact: str | None) -> dict:
    """SEC (D2): e-mail kontaktowy w User-Agent z MS_CONTACT_EMAIL (.env). Brak -> źródło wyłączone, bez zapytań."""
    src = {"name": "SEC", "url": "https://www.sec.gov/news/pressreleases.rss", "assets": ["BTC", "ETH"],
           "note": "D2: SEC wymaga kontaktu w User-Agent"}
    contact = (contact or "").strip()
    return {**src, "ua": f"market-signals/0.1 {contact}"} if contact else {**src, "enabled": False, "disabled_why": SEC_OFF}
TIMEOUT = 20

# Każdy kanał zweryfikowany 2026-10-07 (plan pkt 2). Nowy kanał -> weryfikacja + wpis tutaj + host w ms.netpolicy.
SOURCES = {
    "rigzone": {"name": "Rigzone", "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
                "assets": ["WTI", "BRENT"], "note": "RSS: private, non-commercial use; bez zmian treści; przypisanie"},
    "wgc": {"name": "World Gold Council", "url": "https://www.gold.org/rss.xml", "assets": ["XAU"],
            "note": "zapis do użytku osobistego, niekomercyjnego"},
    "silver_institute": {"name": "Silver Institute", "url": "https://www.silverinstitute.org/feed/", "assets": ["XAG"],
                         "note": "D9"},
    "theblock": {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "assets": ["BTC", "ETH"],
                 "reader_only": True, "note": "D11: tylko czytnik RSS, wyłączony z klasyfikacji/analiz"},
    "sec": sec_source(os.environ.get("MS_CONTACT_EMAIL")),
    "fed": {"name": "Federal Reserve Board", "url": "https://www.federalreserve.gov/feeds/press_all.xml",
            "assets": ["MAKRO"], "note": "domena publiczna"},
    "ecb": {"name": "EBC", "url": "https://www.ecb.europa.eu/rss/press.html", "assets": ["MAKRO"], "crawl_delay": 5,
            "note": "cytować EBC jako źródło"},
    # druga runda 2026-10-07 (plan pkt 12b): robots.txt dozwolone; ToS bez zakazu automatów
    "hellenic": {"name": "Hellenic Shipping News", "url": "https://www.hellenicshippingnews.com/feed/", "assets": ["WTI", "BRENT"],
                 "note": "strona RSS: czytnik wiadomości, z przypisaniem źródła; zakaz republikacji"},
    "gcaptain": {"name": "gCaptain", "url": "https://gcaptain.com/feed/", "assets": ["WTI", "BRENT"],
                 "note": "brak warunków korzystania (tylko polityka prywatności)"},
    "offshore_energy": {"name": "Offshore Energy", "url": "https://www.offshore-energy.biz/feed/", "assets": ["WTI", "BRENT"],
                        "note": "brak warunków korzystania (tylko polityka prywatności)"},
    "bitcoinmag": {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed", "assets": ["BTC"], "no_summary": True,
                   "note": "zakaz reprodukcji bez zgody -> tylko tytuł i link"},
    "silverseek": {"name": "SilverSeek", "url": "https://silverseek.com/rss.xml", "assets": ["XAG"], "no_summary": True,
                   "note": "zakaz kopiowania bez zgody -> tylko tytuł i link"},
    "goldseek": {"name": "GoldSeek", "url": "https://goldseek.com/rss.xml", "assets": ["XAU"], "no_summary": True,
                 "note": "jak SilverSeek: zakaz kopiowania bez zgody (stopka), disclaimer 404, robots dozwolone -> tylko tytuł i link"},
    # rozszerzenie 2026-10-07 (plan pkt 12): robots.txt dozwolone, ToS bez zakazów
    "cftc_press": {"name": "CFTC komunikaty", "url": "https://www.cftc.gov/RSS/RSSGP/rssgp.xml",
                   "assets": ["WTI", "BRENT", "XAU", "XAG", "BTC", "ETH"], "note": "rząd federalny USA (17 U.S.C. §105)"},
    "cftc_enf": {"name": "CFTC egzekucja", "url": "https://www.cftc.gov/RSS/RSSENF/rssenf.xml",
                 "assets": ["WTI", "BRENT", "XAU", "XAG", "BTC", "ETH"], "note": "rząd federalny USA"},
    "ofac": {"name": "OFAC (sankcje)", "url": "https://ofac.treasury.gov/rss.xml", "assets": ["WTI", "BRENT", "XAU", "MAKRO"],
             "note": "rząd federalny USA; sankcje"},
    "boe": {"name": "Bank of England", "url": "https://www.bankofengland.co.uk/rss/news", "assets": ["MAKRO"],
            "note": "użytek osobisty, niekomercyjny"},
    "bis": {"name": "BIS", "url": "https://www.bis.org/doclist/all_pressrels.rss", "assets": ["MAKRO"],
            "note": "niekomercyjnie, cytować BIS"},
}

# GDELT DOC 2.0 API: tytuły i linki artykułów wg tematów. Limit z odpowiedzi API: „one every 5 seconds” -> 6 s odstępu.
# published_at = seendate (moment zauważenia artykułu przez GDELT), nie czas publikacji — opis w news_sources.
GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_GAP_S = 6
GDELT_WINDOW = "75min"   # okno nakładające się na poprzednią godzinę (duplikaty odrzuca item_id)
# Wyłączone 2026-10-10 (DECISIONS): limit 429 stały — gdelt_fed i gdelt_krypto 0 udanych pobrań od startu, pozostałe
# sporadycznie. Kod zostaje; job nie wysyła zapytań, stan w news_fetch = „WYŁĄCZONE…” (health.sh: wyłączone, nie błąd).
GDELT_OFF = "decyzja 2026-10-10: stały limit 429"
GDELT_TOPICS = {
    "gdelt_ropa": {"name": "GDELT: ropa i OPEC", "query": '("crude oil" OR OPEC OR "oil prices" OR "Brent crude")',
                   "assets": ["WTI", "BRENT"], "enabled": False},
    "gdelt_metale": {"name": "GDELT: złoto i srebro", "query": '("gold price" OR "gold prices" OR "silver price" OR bullion)',
                     "assets": ["XAU", "XAG"], "enabled": False},
    "gdelt_krypto": {"name": "GDELT: bitcoin i ethereum", "query": "(bitcoin OR ethereum)", "assets": ["BTC", "ETH"],
                     "enabled": False},
    "gdelt_sankcje": {"name": "GDELT: sankcje", "query": "(sanctions OR embargo)", "assets": ["WTI", "BRENT", "XAU", "MAKRO"],
                      "enabled": False},
    "gdelt_fed": {"name": "GDELT: Fed", "query": '("Federal Reserve" OR FOMC OR Powell)', "assets": ["MAKRO", "XAU", "BTC"],
                  "enabled": False},
}
GDELT_LIMIT_MSG = "Please limit requests"

SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    item_id VARCHAR PRIMARY KEY, source VARCHAR NOT NULL, feed_url VARCHAR NOT NULL, title VARCHAR, summary VARCHAR,
    url VARCHAR, guid VARCHAR, published_at TIMESTAMP, published_at_raw VARCHAR, known_at TIMESTAMP NOT NULL,
    published_missing BOOLEAN NOT NULL, published_after_known BOOLEAN NOT NULL, raw_file VARCHAR, run_id VARCHAR);
CREATE TABLE IF NOT EXISTS news_fetch (
    source VARCHAR PRIMARY KEY, etag VARCHAR, last_modified VARCHAR, last_try TIMESTAMP, last_ok TIMESTAMP,
    last_status VARCHAR, last_ids VARCHAR);
CREATE TABLE IF NOT EXISTS news_gaps (
    source VARCHAR NOT NULL, gap_from TIMESTAMP NOT NULL, gap_to TIMESTAMP NOT NULL, note VARCHAR);
"""


def connect(path: Path | str = NEWS_DB):
    import duckdb

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("SET TimeZone = 'UTC'")
    con.execute(SCHEMA)
    con.execute("ALTER TABLE news_items ADD COLUMN IF NOT EXISTS mentions INTEGER")   # zdarzenia GDELT: num_mentions
    return con


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


# --------------------------------------------------------------------------- robots.txt wg RFC 9309


def robots_groups(txt: str) -> list[dict]:
    gs, cur, last_ua = [], None, False
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not last_ua:
                cur = {"ua": [], "rules": []}
                gs.append(cur)
            cur["ua"].append(v.lower())
            last_ua = True
        else:
            last_ua = False
            if cur is not None and k in ("allow", "disallow"):
                cur["rules"].append((k, v))
    return gs


def _rule_matches(path: str, pattern: str) -> bool:
    if pattern == "":
        return False
    rx = "^" + re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def robots_allows(txt: str, url: str, token: str = TOKEN) -> tuple[bool, tuple | None]:
    """RFC 9309: grupy naszego tokenu, a gdy ich brak — grupa „*”; wygrywa najdłuższa pasująca reguła, przy remisie allow."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + (f"?{u.query}" if u.query else "")
    gs = robots_groups(txt)
    mine = [g for g in gs if any(token in a for a in g["ua"])] or [g for g in gs if "*" in g["ua"]]
    best = None
    for k, p in (r for g in mine for r in g["rules"]):
        if _rule_matches(path, p) and (best is None or len(p) > len(best[1]) or (len(p) == len(best[1]) and k == "allow")):
            best = (k, p)
    return (best is None or best[0] == "allow"), best


def robots_check(src: dict, session: requests.Session, cache_dir: Path = ROBOTS_CACHE, max_age_h: int = 24) -> tuple[bool, str]:
    """(dozwolone, opis). 404/410 = brak ograniczeń; 401/403 lub inny błąd = NIE pobieramy (ostrożnie)."""
    u = urllib.parse.urlsplit(src["url"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"{u.netloc}.json"
    if f.exists() and time.time() - f.stat().st_mtime < max_age_h * 3600:
        c = json.loads(f.read_text())
    else:
        try:
            r = session.get(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": src.get("ua", UA)}, timeout=TIMEOUT)
            c = {"status": r.status_code, "text": r.text if r.status_code == 200 else ""}
        except requests.RequestException as e:
            c = {"status": None, "text": "", "error": str(e)[:200]}
        f.write_text(json.dumps(c))
    if c["status"] in (404, 410):
        return True, f"robots.txt {c['status']} (brak ograniczeń)"
    if c["status"] != 200:
        return False, f"robots.txt niedostępny ({c['status'] or c.get('error')}) — nie pobieramy"
    ok, rule = robots_allows(c["text"], src["url"])
    return ok, f"robots.txt: {'dozwolone' if ok else 'ZABRONIONE'} ({rule})"


# --------------------------------------------------------------------------- parsowanie


def parse_feed(content: bytes) -> list[dict]:
    """Pozycje kanału: tytuł, lead (bez zmian), url, guid, published (UTC albo None) i surowy tekst daty."""
    import feedparser

    d = feedparser.parse(content)
    out = []
    for e in d.entries:
        st = e.get("published_parsed") or e.get("updated_parsed")
        pub = pd.Timestamp(calendar.timegm(st), unit="s") if st else None
        out.append({"title": e.get("title"), "summary": e.get("summary") or e.get("description"),
                    "url": e.get("link"), "guid": e.get("id"), "published_at": pub,
                    "published_at_raw": e.get("published") or e.get("updated")})
    return out


def item_id(source: str, it: dict) -> str:
    key = (it.get("url") or it.get("guid") or it.get("title") or "").strip()
    return hashlib.sha256(f"{source}|{key}".encode()).hexdigest()[:32]


# --------------------------------------------------------------------------- pobranie jednego kanału


@dataclass
class FetchResult:
    source: str
    status: str
    new: int = 0
    items: int = 0
    gap: bool = False
    notes: list = field(default_factory=list)


def _save_raw(key: str, content: bytes, url: str, http_status: int, run_ts: pd.Timestamp, raw_dir: Path, manifest: Path) -> tuple[str, bool]:
    sha = hashlib.sha256(content).hexdigest()
    last = None
    if manifest.exists():
        for line in manifest.read_text().splitlines()[::-1]:
            e = json.loads(line)
            if e["source"] == key and e.get("sha256"):
                last = e
                break
    unchanged = last is not None and last["sha256"] == sha
    path = last["path"] if unchanged else str(raw_dir / key / f"{run_ts:%Y-%m-%d}" / f"{run_ts:%H%M%S}.xml")
    if not unchanged:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(content)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a") as f:
        f.write(json.dumps({"source": key, "url": url, "fetched_at": str(run_ts), "http_status": http_status, "sha256": sha,
                            "path": path, "unchanged": unchanged}) + "\n")
    return path, unchanged


def fetch_source(con, key: str, session: requests.Session, run_ts: pd.Timestamp, run_id: str,
                 sources: dict = SOURCES, raw_dir: Path = RAW, manifest: Path = MANIFEST, robots_dir: Path = ROBOTS_CACHE) -> FetchResult:
    src = sources[key]
    ok, why = robots_check(src, session, robots_dir)
    st = con.execute("SELECT etag, last_modified, last_ids FROM news_fetch WHERE source=?", [key]).fetchone()
    if not ok:
        _state(con, key, run_ts, None, f"POMINIĘTE: {why}", st)
        return FetchResult(key, f"POMINIĘTE: {why}")
    headers = {"User-Agent": src.get("ua", UA)}
    time.sleep(src.get("crawl_delay", 0))            # Crawl-delay hosta (EBC 5 s) — także po zapytaniu o robots.txt
    if st and st[0]:
        headers["If-None-Match"] = st[0]
    if st and st[1]:
        headers["If-Modified-Since"] = st[1]
    try:
        r = session.get(src["url"], headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        _state(con, key, run_ts, None, f"BŁĄD: {str(e)[:150]}", st)
        return FetchResult(key, f"BŁĄD: {str(e)[:150]}")
    if r.status_code == 304:
        _state(con, key, run_ts, run_ts, "304 bez zmian", st)
        return FetchResult(key, "304 bez zmian")
    if r.status_code in (401, 403, 451):
        _state(con, key, run_ts, None, f"ODMOWA {r.status_code} — źródło do listy ręcznej", st)
        return FetchResult(key, f"ODMOWA {r.status_code}")
    if r.status_code != 200:
        _state(con, key, run_ts, None, f"BŁĄD HTTP {r.status_code}", st)
        return FetchResult(key, f"BŁĄD HTTP {r.status_code}")
    path, unchanged = _save_raw(key, r.content, src["url"], r.status_code, run_ts, raw_dir, manifest)
    items = parse_feed(r.content)
    ids = [item_id(key, it) for it in items]
    res = FetchResult(key, "OK" + (" (plik bez zmian)" if unchanged else ""), items=len(items))
    prev = set(json.loads(st[2])) if st and st[2] else set()
    if prev and items and not prev & set(ids):
        last_ok = con.execute("SELECT last_ok FROM news_fetch WHERE source=?", [key]).fetchone()[0]
        con.execute("INSERT INTO news_gaps VALUES (?,?,?,?)", [key, last_ok, run_ts,
                    "brak wspólnych pozycji z poprzednim pobraniem — kanał mógł się przewinąć (luka, nie wypełniana)"])
        res.gap = True
    for it, iid in zip(items, ids):
        pub = it["published_at"]
        n = con.execute("""INSERT INTO news_items (item_id, source, feed_url, title, summary, url, guid, published_at, published_at_raw, known_at, published_missing, published_after_known, raw_file, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING RETURNING 1""",
                        [iid, key, src["url"], it["title"], None if src.get("no_summary") else it["summary"], it["url"], it["guid"],
                         None if pub is None else pub.to_pydatetime(), it["published_at_raw"], run_ts.to_pydatetime(),
                         pub is None, bool(pub is not None and pub > run_ts), path, run_id]).fetchall()
        res.new += len(n)
    _state(con, key, run_ts, run_ts, res.status, st, r.headers.get("ETag"), r.headers.get("Last-Modified"), ids)
    return res


def _state(con, key, try_ts, ok_ts, status, prev, etag=None, last_mod=None, ids=None) -> None:
    etag = etag if etag is not None else (prev[0] if prev else None)
    last_mod = last_mod if last_mod is not None else (prev[1] if prev else None)
    ids_json = json.dumps(ids) if ids is not None else (prev[2] if prev else None)
    old_ok = con.execute("SELECT last_ok FROM news_fetch WHERE source=?", [key]).fetchone()
    con.execute("INSERT OR REPLACE INTO news_fetch VALUES (?,?,?,?,?,?,?)",
                [key, etag, last_mod, try_ts.to_pydatetime(), (ok_ts.to_pydatetime() if ok_ts is not None else
                                                              (old_ok[0] if old_ok else None)), status, ids_json])


def gdelt_url(topic: dict) -> str:
    q = urllib.parse.urlencode({"query": f"{topic['query']} sourcelang:english", "mode": "ArtList", "format": "json",
                                "maxrecords": 75, "timespan": GDELT_WINDOW, "sort": "DateDesc"})
    return f"{GDELT_API}?{q}"


def fetch_gdelt(con, key: str, session: requests.Session, run_ts: pd.Timestamp, run_id: str, topics: dict = GDELT_TOPICS,
                raw_dir: Path = RAW, manifest: Path = MANIFEST, robots_dir: Path = ROBOTS_CACHE, retry_wait: float = 10) -> FetchResult:
    """Jeden temat GDELT DOC. Komunikat limitu -> jedno ponowienie po retry_wait s, potem błąd (bez przyspieszania)."""
    url = gdelt_url(topics[key])
    st = con.execute("SELECT etag, last_modified, last_ids, last_ok FROM news_fetch WHERE source=?", [key]).fetchone()
    ok, why = robots_check({"url": url}, session, robots_dir)
    if not ok:
        _state(con, key, run_ts, None, f"POMINIĘTE: {why}", st[:3] if st else None)
        return FetchResult(key, f"POMINIĘTE: {why}")
    for attempt in (0, 1):
        try:
            r = session.get(url, headers={"User-Agent": UA}, timeout=30)
        except requests.RequestException as e:
            _state(con, key, run_ts, None, f"BŁĄD: {str(e)[:150]}", st[:3] if st else None)
            return FetchResult(key, f"BŁĄD: {str(e)[:150]}")
        if r.status_code == 200 and GDELT_LIMIT_MSG in r.text[:200] and attempt == 0:
            time.sleep(retry_wait)
            continue
        break
    if r.status_code != 200 or GDELT_LIMIT_MSG in r.text[:200]:
        msg = ("LIMIT GDELT (komunikat limitu po ponowieniu)" if r.status_code == 200 else
               f"LIMIT GDELT (HTTP 429, Retry-After: {r.headers.get('Retry-After', '—')})" if r.status_code == 429 else
               f"BŁĄD HTTP {r.status_code}")
        _state(con, key, run_ts, None, msg, st[:3] if st else None)
        return FetchResult(key, msg)
    path, unchanged = _save_raw(key, r.content, url, r.status_code, run_ts, raw_dir, manifest)
    arts = (json.loads(r.text) if r.text.strip() else {}).get("articles", [])
    res = FetchResult(key, "OK", items=len(arts))
    if st and st[3] is not None and run_ts - pd.Timestamp(st[3]) > pd.Timedelta(GDELT_WINDOW):
        con.execute("INSERT INTO news_gaps VALUES (?,?,?,?)", [key, st[3], run_ts - pd.Timedelta(GDELT_WINDOW),
                    "przerwa dłuższa niż okno zapytania GDELT (luka, nie wypełniana)"])
        res.gap = True
    for a in arts:
        it = {"url": a.get("url"), "title": a.get("title")}
        seen = pd.to_datetime(a.get("seendate"), format="%Y%m%dT%H%M%SZ", errors="coerce")
        pub = None if pd.isna(seen) else seen
        n = con.execute("""INSERT INTO news_items (item_id, source, feed_url, title, summary, url, guid, published_at, published_at_raw, known_at, published_missing, published_after_known, raw_file, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING RETURNING 1""",
                        [item_id(key, it), key, GDELT_API, a.get("title"),
                         f"{a.get('domain', '')} ({a.get('sourcecountry', '')}, {a.get('language', '')})", a.get("url"), None,
                         None if pub is None else pub.to_pydatetime(), a.get("seendate"), run_ts.to_pydatetime(),
                         pub is None, bool(pub is not None and pub > run_ts), path, run_id]).fetchall()
        res.new += len(n)
    _state(con, key, run_ts, run_ts, res.status, st[:3] if st else None)
    return res


# Wpisy z ZDARZEŃ GDELT 2.0, które już zbieramy (data/gdelt.duckdb) — bez wchodzenia na strony artykułów.
# Temat -> aktywa wg mapy zależności (docs/MAPA-ZALEZNOSCI.md) i definicji z 4H (ms.hyp_events); bez par USA–USA.
GDELT_EV_FIRST_WINDOW = pd.Timedelta(days=3)     # pierwsze uruchomienie: tylko ostatnie 3 dni (nie cała historia)
GDELT_EV_TOPICS = {
    "gdelt_ev_ropa": {"name": "GDELT zdarzenia: producenci ropy / cieśniny", "assets": ["WTI", "BRENT"],
                      "basis": "O3, O4, O14 (ms.hyp_events: producers, chokepoints)"},
    "gdelt_ev_sankcje": {"name": "GDELT zdarzenia: sankcje (CAMEO 163)", "assets": ["WTI", "BRENT", "XAU", "MAKRO"],
                         "basis": "O15, G8"},
    "gdelt_ev_konflikt": {"name": "GDELT zdarzenia: konflikt zbrojny (CAMEO 18–20)", "assets": ["XAU", "BTC", "ETH"],
                          "basis": "G6, C14"},
}


def _gdelt_ev_conditions() -> dict:
    from ms.hyp_events import HORMUZ, PRODUCERS, RED_SEA

    prod = ", ".join(f"'{p}'" for p in PRODUCERS)
    choke = (f"((action_geo_lat BETWEEN {HORMUZ[0]} AND {HORMUZ[1]} AND action_geo_long BETWEEN {HORMUZ[2]} AND {HORMUZ[3]})"
             f" OR (action_geo_lat BETWEEN {RED_SEA[0]} AND {RED_SEA[1]} AND action_geo_long BETWEEN {RED_SEA[2]} AND {RED_SEA[3]}))")
    return {"gdelt_ev_ropa": f"(actor1_country IN ({prod}) OR actor2_country IN ({prod}) OR {choke})",
            "gdelt_ev_sankcje": "event_base_code = '163'",
            "gdelt_ev_konflikt": "root_code IN ('18', '19', '20')"}


NOT_USA_USA = "NOT (coalesce(actor1_country, '') = 'USA' AND coalesce(actor2_country, '') = 'USA')"


def build_gdelt_events(con, gdelt_path: Path, run_ts: pd.Timestamp, run_id: str) -> list[FetchResult]:
    """Nowe zdarzenia (DATEADDED > znacznik tematu) -> news_items: jeden wpis na (temat, adres źródła).
    published_at = DATEADDED (czas dodania przez GDELT), known_at = chwila zbudowania wpisu. Znacznik w news_fetch.last_modified."""
    import duckdb

    out = []
    try:
        g = duckdb.connect(str(gdelt_path), read_only=True)
    except duckdb.Error as e:          # baza GDELT zajęta (snapshot) -> następna godzina
        return [FetchResult(k, f"POMINIĘTE: gdelt.duckdb zajęta ({str(e)[:60]})") for k in GDELT_EV_TOPICS]
    try:
        for key, cond in _gdelt_ev_conditions().items():
            st = con.execute("SELECT etag, last_modified, last_ids FROM news_fetch WHERE source=?", [key]).fetchone()
            mark = pd.Timestamp(st[1]) if st and st[1] else run_ts - GDELT_EV_FIRST_WINDOW
            ev = g.execute(f"""SELECT event_id, known_at AS dateadded, event_code, root_code, actor1_country, actor1_name,
                                      actor2_country, actor2_name, avg_tone, goldstein, num_mentions, source_url
                               FROM events WHERE known_at > ? AND {NOT_USA_USA} AND {cond} AND source_url IS NOT NULL
                               ORDER BY known_at, event_id""", [mark.to_pydatetime()]).df()
            res = FetchResult(key, "OK", items=len(ev))
            for _, e in ev.drop_duplicates("source_url").iterrows():
                e = e.where(pd.notna(e), None)                 # NaN z pustych pól GDELT -> None (nie „nan” w tytule)
                a1 = e.actor1_country or e.actor1_name or "?"
                a2 = e.actor2_country or e.actor2_name or "?"
                title = f"{a1} → {a2}: CAMEO {e.event_code}, ton {e.avg_tone:+.1f}"
                summary = (f"CAMEO {e.event_code} (grupa {e.root_code}); aktorzy {e.actor1_name or '—'} ({e.actor1_country or '—'}) → "
                           f"{e.actor2_name or '—'} ({e.actor2_country or '—'}); ton {e.avg_tone:+.2f}; Goldstein {e.goldstein:+.1f}; "
                           f"wzmianki {e.num_mentions}; zdarzenie GDELT {e.event_id}")
                pub = pd.Timestamp(e.dateadded)
                n = con.execute("""INSERT INTO news_items (item_id, source, feed_url, title, summary, url, guid, published_at, published_at_raw, known_at, published_missing, published_after_known, raw_file, run_id, mentions) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING RETURNING 1""",
                                [item_id(key, {"url": e.source_url}), key, "gdelt.duckdb:events", title, summary, e.source_url,
                                 str(e.event_id), pub.to_pydatetime(), "DATEADDED", run_ts.to_pydatetime(), False,
                                 bool(pub > run_ts), str(gdelt_path), run_id, int(e.num_mentions or 0)]).fetchall()
                res.new += len(n)
            new_mark = pd.Timestamp(ev["dateadded"].max()) if len(ev) else mark
            _state(con, key, run_ts, run_ts, res.status, st, None, str(new_mark), [])
            out.append(res)
    finally:
        g.close()
    return out


def all_sources() -> dict:
    """Kanały RSS + tematy GDELT (do dashboardu i health): klucz -> nazwa, aktywa."""
    return {**{k: {"name": v["name"], "assets": v["assets"], "kind": "RSS"} for k, v in SOURCES.items()},
            **{k: {"name": v["name"], "assets": v["assets"], "kind": "GDELT DOC API"} for k, v in GDELT_TOPICS.items()},
            **{k: {"name": v["name"], "assets": v["assets"], "kind": "GDELT zdarzenia"} for k, v in GDELT_EV_TOPICS.items()}}


def collect(con, sources: dict = SOURCES, **kw) -> list[FetchResult]:
    run_ts = now_utc()
    run_id = f"news-{run_ts:%Y%m%dT%H%M%S}"
    out = []
    with requests.Session() as s:
        for key, src in sources.items():
            if not src.get("enabled", True):          # wyłączone decyzją/konfiguracją: bez zapytania, stan „WYŁĄCZONE”
                st = con.execute("SELECT etag, last_modified, last_ids FROM news_fetch WHERE source=?", [key]).fetchone()
                _state(con, key, run_ts, None, f"WYŁĄCZONE: {src.get('disabled_why', '')}", st)
                out.append(FetchResult(key, f"WYŁĄCZONE: {src.get('disabled_why', '')}"))
                continue
            out.append(fetch_source(con, key, s, run_ts, run_id, sources, **kw))
        if sources is SOURCES:
            out += collect_gdelt(con, s, run_ts, run_id, GDELT_TOPICS, **kw)
    return out


def collect_gdelt(con, s: requests.Session, run_ts: pd.Timestamp, run_id: str, topics: dict = GDELT_TOPICS,
                  **kw) -> list[FetchResult]:
    """Tematy GDELT DOC. enabled=False -> bez zapytania, stan „WYŁĄCZONE: …” (nie błąd, nie limit)."""
    out = []
    limited = False
    for key, topic in topics.items():
        if not topic.get("enabled", True):
            st = con.execute("SELECT etag, last_modified, last_ids FROM news_fetch WHERE source=?", [key]).fetchone()
            _state(con, key, run_ts, None, f"WYŁĄCZONE: {GDELT_OFF}", st)
            out.append(FetchResult(key, f"WYŁĄCZONE: {GDELT_OFF}"))
            continue
        if limited:                                # po limicie: reszta tematów czeka na następną godzinę
            st = con.execute("SELECT etag, last_modified, last_ids FROM news_fetch WHERE source=?", [key]).fetchone()
            _state(con, key, run_ts, None, "POMINIĘTE: limit GDELT w tym przebiegu", st)
            out.append(FetchResult(key, "POMINIĘTE: limit GDELT w tym przebiegu"))
            continue
        time.sleep(GDELT_GAP_S)                    # limit API: najwyżej 1 zapytanie na 5 s
        out.append(fetch_gdelt(con, key, s, run_ts, run_id, topics, **kw))
        limited = out[-1].status.startswith("LIMIT")
    return out

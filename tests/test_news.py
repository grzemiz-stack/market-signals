"""4N-live: parser RSS/Atom, robots.txt wg RFC 9309, pobranie kanału (lokalny serwer 127.0.0.1): idempotencja,
known_at = pierwsze pobranie, warunkowe GET, robots/403 -> pominięcie bez obejścia, luka; wiadomości nie są cechą."""

import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
import pytest
import requests

from ms import netpolicy, news

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "news"


def test_parse_rss_and_atom():
    rss = news.parse_feed((FIX / "rss.xml").read_bytes())
    assert [i["title"] for i in rss] == ["Oil rises 3% on supply cut", "No date item"]
    assert rss[0]["published_at"] == pd.Timestamp("2026-10-07 08:33:52")          # -0500 -> UTC
    assert rss[0]["summary"] == "<p>Lead <b>one</b>.</p>"                          # lead bez zmian
    assert rss[1]["published_at"] is None
    atom = news.parse_feed((FIX / "atom.xml").read_bytes())
    assert atom[0]["published_at"] == pd.Timestamp("2026-10-06 09:49:18") and atom[0]["url"] == "https://example.test/b1"


def test_robots_rfc9309_longest_match():
    eia = "User-agent: *\nAllow: /\nDisallow: /rss\n"
    assert news.robots_allows(eia, "https://www.eia.gov/rss/todayinenergy.xml")[0] is False   # pierwsza reguła by przepuściła
    assert news.robots_allows(eia, "https://www.eia.gov/todayinenergy/")[0] is True
    assert news.robots_allows("User-agent: *\nDisallow: /feed\nAllow: /feed/main\n", "https://x.test/feed/main")[0] is True
    assert news.robots_allows("User-agent: *\nDisallow: /*.xml$\n", "https://x.test/a/rss.xml")[0] is False
    assert news.robots_allows("User-agent: *\nDisallow: /*.xml$\n", "https://x.test/a/rss.xml?x=1")[0] is True
    own = "User-agent: *\nDisallow: /\n\nUser-agent: market-signals\nAllow: /rss\n"
    assert news.robots_allows(own, "https://x.test/rss")[0] is True                 # grupa naszego tokenu ma pierwszeństwo
    assert news.robots_allows("User-agent: GPTBot\nDisallow: /\n", "https://x.test/rss")[0] is True


class _Srv(BaseHTTPRequestHandler):
    state = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        st = _Srv.state
        st.setdefault("hits", []).append((self.path, self.headers.get("User-Agent"), self.headers.get("If-None-Match")))
        if self.path == "/robots.txt":
            body, code = st.get("robots", "User-agent: *\nAllow: /\n").encode(), st.get("robots_code", 200)
        elif self.headers.get("If-None-Match") == st.get("etag") and st.get("etag"):
            self.send_response(304)
            self.end_headers()
            return
        else:
            body, code = st["feed"], st.get("feed_code", 200)
        self.send_response(code)
        if st.get("etag"):
            self.send_header("ETag", st["etag"])
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def srv(tmp_path):
    s = HTTPServer(("127.0.0.1", 0), _Srv)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    _Srv.state = {"feed": (FIX / "rss.xml").read_bytes()}
    base = f"http://127.0.0.1:{s.server_port}"
    kw = dict(raw_dir=tmp_path / "raw", manifest=tmp_path / "raw" / "manifest.jsonl", robots_dir=tmp_path / "robots")
    sources = {"t": {"name": "T", "url": f"{base}/feed.xml", "assets": ["WTI"]}}
    yield _Srv.state, news.connect(tmp_path / "n.duckdb"), sources, kw, tmp_path
    s.shutdown()


def _run(con, sources, kw, ts):
    with requests.Session() as sess:
        return news.fetch_source(con, "t", sess, pd.Timestamp(ts), "r", sources, **kw)


def test_fetch_idempotent_known_at_first_seen_and_conditional_get(srv):
    st, con, sources, kw, _ = srv
    r1 = _run(con, sources, kw, "2026-10-07 10:07:00")
    assert r1.status == "OK" and r1.new == 2
    r2 = _run(con, sources, kw, "2026-10-07 11:07:00")
    assert r2.new == 0 and "bez zmian" in r2.status                                  # ten sam plik: zero nowych
    rows = con.execute("SELECT title, known_at, published_missing, published_after_known FROM news_items ORDER BY title").fetchall()
    assert {r[1] for r in rows} == {pd.Timestamp("2026-10-07 10:07:00").to_pydatetime()}   # known_at = pierwsze pobranie
    assert [r[2] for r in rows] == [True, False] and not any(r[3] for r in rows)
    st["etag"] = '"v1"'
    _run(con, sources, kw, "2026-10-07 12:07:00")
    r4 = _run(con, sources, kw, "2026-10-07 13:07:00")
    assert r4.status == "304 bez zmian" and st["hits"][-1][2] == '"v1"'               # warunkowe GET
    assert all(ua == news.UA for _, ua, _ in st["hits"])                              # zawsze ten sam, jawny User-Agent


def test_robots_disallow_or_403_skips_without_workaround(srv):
    st, con, sources, kw, tmp = srv
    st["robots"] = "User-agent: *\nDisallow: /feed.xml\n"
    r = _run(con, sources, kw, "2026-10-07 10:07:00")
    assert r.status.startswith("POMINIĘTE") and [h[0] for h in st["hits"]] == ["/robots.txt"]   # kanału nie dotknięto
    assert con.execute("SELECT count(*) FROM news_items").fetchone()[0] == 0
    st.update(robots="User-agent: *\nAllow: /\n", feed_code=403, hits=[])
    for f in (tmp / "robots").glob("*"):
        f.unlink()
    r = _run(con, sources, kw, "2026-10-07 11:07:00")
    assert r.status.startswith("ODMOWA 403") and len([h for h in st["hits"] if h[0] == "/feed.xml"]) == 1   # bez ponowień
    st.update(robots_code=403, feed_code=200, hits=[])
    for f in (tmp / "robots").glob("*"):
        f.unlink()
    assert _run(con, sources, kw, "2026-10-07 12:07:00").status.startswith("POMINIĘTE")   # robots 403 = nie pobieramy


def test_gap_marked_when_feed_rolled_over(srv):
    st, con, sources, kw, _ = srv
    _run(con, sources, kw, "2026-10-07 10:07:00")
    st["feed"] = (FIX / "atom.xml").read_bytes()                                     # zero wspólnych pozycji
    r = _run(con, sources, kw, "2026-10-08 09:07:00")
    assert r.gap and con.execute("SELECT count(*) FROM news_gaps").fetchone()[0] == 1


def test_sources_hosts_in_netpolicy_and_reader_only_flag():
    for k, s in news.SOURCES.items():
        assert netpolicy.is_allowed(s["url"]), k
    assert news.SOURCES["theblock"].get("reader_only") is True                       # D11
    assert all("@" not in s.get("ua", "") for k, s in news.SOURCES.items() if k != "sec")


def test_sec_contact_from_env_or_disabled(tmp_path, monkeypatch):
    """SEC: e-mail kontaktowy tylko z MS_CONTACT_EMAIL; bez niego źródło wyłączone (zero zapytań), nie błąd."""
    on = news.sec_source("me@example.test")
    assert on["ua"] == "market-signals/0.1 me@example.test" and on.get("enabled", True)
    off = news.sec_source(None)
    assert off["enabled"] is False and "ua" not in off and news.sec_source("  ")["enabled"] is False

    def no_fetch(*a, **k):
        raise AssertionError("zapytanie do wyłączonego źródła")
    monkeypatch.setattr(news, "fetch_source", no_fetch)
    con = news.connect(tmp_path / "n.duckdb")
    res = news.collect(con, {"sec": off}, raw_dir=tmp_path / "raw", manifest=tmp_path / "m.jsonl", robots_dir=tmp_path / "rb")
    assert [r.status for r in res] == [f"WYŁĄCZONE: {news.SEC_OFF}"]


def test_news_never_read_by_forecast_code():
    allowed = {"ms/news.py", "collect_news.py", "ms/views.py", "publish_view.py"}  # + dashboard/ (wyświetlanie)   # publish_view tylko kopiuje plik
    bad = []
    for p in (ROOT / "src").rglob("*.py"):
        rel = p.relative_to(ROOT / "src").as_posix()
        if rel in allowed or rel.startswith("dashboard/"):
            continue
        t = p.read_text(encoding="utf-8")
        if re.search(r"\bnews_(items|fetch|gaps|class)\b|news_view|news\.duckdb", t) or re.search(r"from ms import[^\n]*\bnews\b|import ms\.news", t):
            bad.append(rel)
    assert bad == [], f"wiadomości czytane poza zbieraniem/wyświetlaniem: {bad}"


class _Gdelt(BaseHTTPRequestHandler):
    state = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        st = _Gdelt.state
        st.setdefault("hits", []).append(self.path)
        if self.path == "/robots.txt":
            self.send_response(404)
            self.end_headers()
            return
        body = st["bodies"].pop(0) if st["bodies"] else st["last"]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body.encode())


ARTS = '{"articles": [{"url": "https://e.test/x1", "title": "OPEC cuts", "seendate": "20261007T100000Z", "domain": "e.test", "language": "English", "sourcecountry": "US"}, {"url": "https://e.test/x2", "title": "Oil up", "seendate": "20261007T101500Z", "domain": "e.test", "language": "English", "sourcecountry": "US"}]}'
LIMIT = "Please limit requests to one every 5 seconds or contact ..."


@pytest.fixture
def gsrv(tmp_path, monkeypatch):
    s = HTTPServer(("127.0.0.1", 0), _Gdelt)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    monkeypatch.setattr(news, "GDELT_API", f"http://127.0.0.1:{s.server_port}/api/v2/doc/doc")
    kw = dict(raw_dir=tmp_path / "raw", manifest=tmp_path / "raw" / "m.jsonl", robots_dir=tmp_path / "rb", retry_wait=0)
    yield news.connect(tmp_path / "n.duckdb"), kw
    s.shutdown()


def _g(con, kw, ts):
    with requests.Session() as sess:
        return news.fetch_gdelt(con, "gdelt_ropa", sess, pd.Timestamp(ts), "r", **kw)


def test_gdelt_articles_dedup_and_seendate(gsrv):
    con, kw = gsrv
    _Gdelt.state = {"bodies": [ARTS, ARTS], "last": ARTS}
    r = _g(con, kw, "2026-10-07 10:30:00")
    assert r.status == "OK" and r.new == 2 and "sourcelang%3Aenglish" in _Gdelt.state["hits"][-1]
    assert _g(con, kw, "2026-10-07 11:30:00").new == 0                               # okno nakłada się: bez duplikatów
    row = con.execute("SELECT published_at, published_at_raw, summary FROM news_items WHERE title='OPEC cuts'").fetchone()
    assert row[0] == pd.Timestamp("2026-10-07 10:00:00").to_pydatetime() and row[1] == "20261007T100000Z"


def test_gdelt_limit_message_retried_once_then_error(gsrv):
    con, kw = gsrv
    _Gdelt.state = {"bodies": [LIMIT, ARTS], "last": ARTS}
    assert _g(con, kw, "2026-10-07 10:30:00").status == "OK"                         # jedno ponowienie
    _Gdelt.state = {"bodies": [LIMIT, LIMIT], "last": LIMIT}
    r = _g(con, kw, "2026-10-07 11:30:00")
    assert r.status.startswith("LIMIT") and len([h for h in _Gdelt.state["hits"] if "doc" in h]) == 2   # bez zalewania API
    assert con.execute("SELECT count(*) FROM news_items").fetchone()[0] == 2         # komunikat limitu nie jest daną


def test_gdelt_gap_when_pause_longer_than_window(gsrv):
    con, kw = gsrv
    _Gdelt.state = {"bodies": [], "last": ARTS}
    _g(con, kw, "2026-10-07 10:30:00")
    assert not _g(con, kw, "2026-10-07 11:30:00").gap
    assert _g(con, kw, "2026-10-07 16:30:00").gap                                     # Mac wyłączony 5 h


def test_gdelt_rate_spacing_constant():
    assert news.GDELT_GAP_S >= 5                                                      # limit z odpowiedzi API


def test_gdelt_doc_topics_disabled_no_requests(gsrv, monkeypatch):
    """DECISIONS 2026-10-10: wszystkie 5 tematów GDELT DOC wyłączone (enabled=False) — zero zapytań, stan „WYŁĄCZONE”,
    ostatni udany bez zmian; kod zostaje (temat z enabled=True nadal pobiera)."""
    con, kw = gsrv
    monkeypatch.setattr(news.time, "sleep", lambda s: None)
    assert set(news.GDELT_TOPICS) == {"gdelt_ropa", "gdelt_metale", "gdelt_krypto", "gdelt_sankcje", "gdelt_fed"}
    assert all(t["enabled"] is False for t in news.GDELT_TOPICS.values())
    _Gdelt.state = {"bodies": [], "last": ARTS}
    _g(con, kw, "2026-10-07 10:30:00")                                                # wcześniejsze udane pobranie
    _Gdelt.state = {"bodies": [], "last": ARTS}
    with requests.Session() as sess:
        res = news.collect_gdelt(con, sess, pd.Timestamp("2026-10-10 12:07:00"), "r", **kw)
    assert "hits" not in _Gdelt.state                                                 # żadnego zapytania
    assert [r.status for r in res] == [f"WYŁĄCZONE: {news.GDELT_OFF}"] * 5
    st = dict(con.execute("SELECT source, last_status FROM news_fetch").fetchall())
    assert all(st[k].startswith("WYŁĄCZONE") and "429" in st[k][:48] for k in news.GDELT_TOPICS)   # health: 48 znaków
    assert con.execute("SELECT last_ok FROM news_fetch WHERE source='gdelt_ropa'").fetchone()[0] == pd.Timestamp("2026-10-07 10:30:00")
    on = {"gdelt_ropa": {**news.GDELT_TOPICS["gdelt_ropa"], "enabled": True}}
    with requests.Session() as sess:
        assert news.collect_gdelt(con, sess, pd.Timestamp("2026-10-10 13:07:00"), "r", on, **kw)[0].status == "OK"


def test_disabled_topics_not_a_job_failure(tmp_path, monkeypatch):
    import collect_news as cn

    off = news.FetchResult("gdelt_fed", f"WYŁĄCZONE: {news.GDELT_OFF}")
    monkeypatch.setattr(cn.logging, "basicConfig", lambda **k: None)
    real_connect = news.connect
    monkeypatch.setattr(cn.news, "connect", lambda: real_connect(tmp_path / "n.duckdb"))
    monkeypatch.setattr(cn.news, "build_gdelt_events", lambda *a: [])
    monkeypatch.setattr(cn, "publish", lambda *a: None)
    monkeypatch.setattr(cn.news, "collect", lambda con: [news.FetchResult("fed", "OK"), off])
    assert cn.main() == 0
    monkeypatch.setattr(cn.news, "collect", lambda con: [off, news.FetchResult("fed", "BŁĄD HTTP 404")])
    assert cn.main() == 1                                                             # kontrola: prawdziwy błąd nadal pada


def _gdelt_db(path):
    import duckdb
    import sys as _s
    _s.path.insert(0, str(ROOT / "src"))
    import gdelt_backfill as gb

    g = duckdb.connect(str(path))
    g.execute(gb.SCHEMA)
    rows = [  # id, dateadded, a1c, a2c, code, base, root, lat, lon, url
        (1, "2026-10-07 08:00", "USA", "USA", "190", "190", "19", 40.0, -100.0, "https://n.test/usa-usa"),   # USA–USA: pomijane
        (2, "2026-10-07 08:15", "USA", "IRN", "163", "163", "16", 35.0, 51.0, "https://n.test/sankcje"),
        (3, "2026-10-07 08:15", "SAU", "YEM", "190", "190", "19", 15.0, 44.0, "https://n.test/saudi"),      # ropa + konflikt
        (4, "2026-10-07 08:30", "GBR", "FRA", "141", "141", "14", 26.0, 56.0, "https://n.test/ormuz"),     # cieśnina
        (5, "2026-10-07 08:30", "RUS", "UKR", "195", "195", "19", 50.0, 30.0, "https://n.test/wojna"),
        (6, "2026-10-07 08:30", "RUS", "UKR", "190", "190", "19", 50.0, 30.0, "https://n.test/wojna"),      # ten sam adres
        (7, "2026-10-07 08:30", "DEU", "FRA", "141", "141", "14", 50.0, 8.0, "https://n.test/protest"),    # poza tematami
        (8, "2026-09-01 08:00", "RUS", "UKR", "190", "190", "19", 50.0, 30.0, "https://n.test/stare"),     # sprzed okna 3 dni
    ]
    for r in rows:
        g.execute("""INSERT INTO events VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, ?, TRUE, ?, ?, ?, 4, -8.0, 20, 5, 10, -4.2,
                     NULL, ?, ?, ?, 'f', 'GDELT')""", [r[0], r[1][:10], r[1], r[2], r[2], r[3], r[3], r[4], r[5], r[6], r[7], r[8], r[9]])
    g.close()


def test_gdelt_events_topics_assets_and_pit(tmp_path):
    _gdelt_db(tmp_path / "g.duckdb")
    con = news.connect(tmp_path / "n.duckdb")
    run = pd.Timestamp("2026-10-07 09:07:00")
    res = {r.source: r for r in news.build_gdelt_events(con, tmp_path / "g.duckdb", run, "r")}
    got = {k: sorted(u for (u,) in con.execute("SELECT url FROM news_items WHERE source=?", [k]).fetchall()) for k in res}
    assert got["gdelt_ev_sankcje"] == ["https://n.test/sankcje"]
    # producenci ropy wg 4H obejmują też IRN i RUS (ms.hyp_events.PRODUCERS) + cieśnina Ormuz
    assert got["gdelt_ev_ropa"] == ["https://n.test/ormuz", "https://n.test/sankcje", "https://n.test/saudi", "https://n.test/wojna"]
    assert got["gdelt_ev_konflikt"] == ["https://n.test/saudi", "https://n.test/wojna"]      # bez USA–USA, bez duplikatu, bez starych
    row = con.execute("SELECT published_at, known_at, title FROM news_items WHERE url='https://n.test/sankcje'").fetchone()
    assert row[0] == pd.Timestamp("2026-10-07 08:15").to_pydatetime() and row[1] == run.to_pydatetime()   # DATEADDED / pobranie
    assert row[2].startswith("USA → IRN: CAMEO 163")
    again = news.build_gdelt_events(con, tmp_path / "g.duckdb", run + pd.Timedelta(hours=1), "r2")
    assert sum(r.new for r in again) == 0                                                    # znacznik: tylko nowsze zdarzenia
    src = news.all_sources()
    assert src["gdelt_ev_ropa"]["assets"] == ["WTI", "BRENT"] and "XAG" not in str([v["assets"] for v in src.values() if v["kind"] == "GDELT zdarzenia"])


def test_no_summary_sources_store_title_and_link_only(srv):
    st, con, sources, kw, _ = srv
    sources["t"]["no_summary"] = True
    _run(con, sources, kw, "2026-10-07 10:07:00")
    assert con.execute("SELECT count(*) FROM news_items WHERE summary IS NOT NULL").fetchone()[0] == 0
    assert all(news.SOURCES[k]["no_summary"] for k in ("bitcoinmag", "silverseek", "goldseek"))


def test_gdelt_event_title_without_nan(tmp_path):
    import duckdb
    _gdelt_db(tmp_path / "g.duckdb")
    g = duckdb.connect(str(tmp_path / "g.duckdb"))
    g.execute("UPDATE events SET actor1_country = NULL, actor1_name = 'HAMAS' WHERE event_id = 2")
    g.close()
    con = news.connect(tmp_path / "n.duckdb")
    news.build_gdelt_events(con, tmp_path / "g.duckdb", pd.Timestamp("2026-10-07 09:07:00"), "r")
    titles = [t for (t,) in con.execute("SELECT title FROM news_items").fetchall()]
    assert not any("nan" in t for t in titles) and any(t.startswith("HAMAS → IRN") for t in titles)


def test_gdelt_entries_sorted_by_mentions_last_24h(tmp_path, monkeypatch):
    from ms import views
    con = news.connect(tmp_path / "n.duckdb")
    cols = "(item_id, source, feed_url, title, url, published_at, known_at, published_missing, published_after_known, mentions)"
    rows = [("a", "gdelt_ev_ropa", "x", "mało, świeże", "u1", "2026-10-07 09:00", 5), ("b", "gdelt_ev_ropa", "x", "dużo", "u2", "2026-10-07 01:00", 90),
            ("c", "gdelt_ev_ropa", "x", "stare, dużo", "u3", "2026-10-05 09:00", 999), ("d", "rigzone", "x", "rss nowe", "u4", "2026-10-07 09:30", None),
            ("e", "rigzone", "x", "rss stare", "u5", "2026-10-06 09:30", None)]
    for i, s_, f, t, u, p, m in rows:
        con.execute(f"INSERT INTO news_items {cols} VALUES (?,?,?,?,?,?,?,FALSE,FALSE,?)", [i, s_, f, t, u, p, p, m])
    con.close()
    monkeypatch.setenv("MS_NEWS_VIEW_DB", str(tmp_path / "n.duckdb"))
    nw = views.news_for_asset("WTI", now="2026-10-07 10:00")
    assert nw["gdelt"]["title"].tolist() == ["dużo", "mało, świeże"]                 # wzmianki malejąco, tylko 24 h
    assert nw["own"]["title"].tolist() == ["rss nowe", "rss stare"]                  # RSS po czasie, bez zmian

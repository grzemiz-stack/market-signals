"""Etap 4C: dashboard — każda liczba z ms.views (te same funkcje co paper.py status), tylko odczyt kopii bazy,
formularz = ms.paper.order, zero obcych komponentów. Lokalność serwera i brak CDN: test_dashboard_server.py."""

import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from provenance import foreign_numbers  # noqa: E402
from ms import paper as pp, views  # noqa: E402
from ms.trading import GAME_ASSETS  # noqa: E402

pytestmark = pytest.mark.data
PAGES = ROOT / "src" / "dashboard" / "pages"
DASH = [p for p in (ROOT / "src" / "dashboard").rglob("*.py")]
# stałe etykiety na stronach (nie dane): okresy etapu 5, „1000 zł” kapitału startowego backtestu
LABELS = ["2016-10 … 2024-10", "2024-10 … 2026-10", "1000 zł", "2026-10-07", "5. percentyl", "20 dni", "2–4×"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    shutil.copy(pp.PAPER_DB, tmp_path / "p.duckdb")
    monkeypatch.setenv("MS_PAPER_DB", str(tmp_path / "p.duckdb"))
    assert views.view_db().exists(), "brak kopii bazy — uv run src/publish_view.py"
    return tmp_path / "p.duckdb"


def run(page: str) -> AppTest:
    at = AppTest.from_file(str(PAGES / f"{page}.py"), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def screen_text(at: AppTest) -> str:
    parts = []
    for kind in ("title", "header", "subheader", "markdown", "caption", "info", "success", "warning", "error", "code"):
        parts += [str(e.value) for e in getattr(at, kind)]
    for m in at.metric:
        parts += [m.label, str(m.value), str(m.delta or "")]
    return "\n".join(parts)     # stałe etykiety (LABELS) idą do foreign_numbers jako teksty — od najdłuższego


def test_dashboard_never_opens_working_db_nor_embeds_foreign_code():
    for p in DASH:
        s = p.read_text()
        assert "market.duckdb" not in s and "db.connect(" not in s and "duckdb.connect(" not in s, p.name
        assert "components" not in s and "unsafe_allow_html" not in s and "st.html" not in s, p.name


def test_view_connection_is_read_only():
    import duckdb

    con = views.open_market_view()
    with pytest.raises(duckdb.Error):
        con.execute("CREATE TABLE x (a INT)")
    con.close()


def test_account_page_numbers_from_views(env):
    at = run("konto")
    pcon = pp.connect(env)
    mcon = views.open_market_view()
    b = views.load_book(mcon)
    acc = pp.account(pcon, 1)
    v = views.account_view(pcon, mcon, b, acc)
    j = views.journal_view(pcon, acc, executed=v["executed"])
    bad = foreign_numbers(screen_text(at), v, j, views.view_meta(), LABELS)
    assert not bad, f"liczby spoza ms.views: {bad}"


@pytest.mark.parametrize("page,assets", [("aktywa", GAME_ASSETS), ("pozostale", ("XAU", "BRENT"))])
def test_asset_pages_numbers_from_views(env, page, assets):
    at = run(page)
    mcon = views.open_market_view()
    b = views.load_book(mcon)
    t = pp.now_utc()
    cards = [views.asset_card(mcon, b, a, t) for a in assets]
    bw = [dict(zip(("loss", "q"), pp.bad_week_loss(b, a, 1000.0, t))) for a in assets]
    bw = [{"loss": x["loss"], "q": x["q"] / 100, "amount": 1000.0} for x in bw]
    nw = [views.news_for_asset(a) for a in assets]
    bad = foreign_numbers(screen_text(at), *cards, *bw, *nw, views.view_meta(), LABELS)
    assert not bad, f"liczby spoza ms.views: {bad}"


def test_recommendations_page_numbers_from_views(env):
    at = run("zalecenia")
    assert any("D11" in e.value for e in at.error)                        # ramka D11 zawsze widoczna
    mcon = views.open_market_view()
    pcon = pp.connect(env)
    rv = views.recommendations_view(mcon, pcon)
    bs = views.backtest_summary(mcon)
    bad = foreign_numbers(screen_text(at), rv, bs, views.view_meta(), LABELS)
    assert not bad, f"liczby spoza ms.views: {bad}"


def test_order_form_uses_paper_order(env):
    at = run("zlecenie")
    assert "system" not in at.selectbox[0].options                         # konta „system”: tylko reguły
    at.text_area[0].input("   ")
    at.button[0].click().run()
    assert any("powód" in e.value for e in at.error)                       # bez powodu: odmowa (ta sama walidacja)
    at.selectbox[1].select("XAG")
    at.text_area[0].input("test formularza")
    at.button[0].click().run()
    assert at.success, [e.value for e in at.error]
    pcon = pp.connect(env)
    row = pcon.execute("SELECT side, asset, amount_pln, reason FROM paper_orders ORDER BY id DESC LIMIT 1").fetchone()
    assert row == ("buy", "XAG", 100.0, "test formularza")


def test_dashboard_does_not_change_paper_db(env):
    """Wyświetlanie stron nie zmienia bazy gry (hash pliku przed/po), także gdy zlecenie ma już cenę wykonania
    (status executed zapisze nocny job, nie dashboard)."""
    import hashlib

    pcon = pp.connect(env)
    mcon = views.open_market_view()
    b = views.load_book(mcon)
    acc = pp.account(pcon, 1)
    oid, _ = pp.place(pcon, mcon, b, 1, "buy", "XAG", "test hash", amount_pln=50, D=str(acc["start_date"])[:10])
    assert oid in [int(o.id) for o, _ in pp.replay(pcon, b, acc).executed]   # cena wykonania jest: stary kod by zapisał
    pcon.close()
    mcon.close()
    h0 = hashlib.sha256(env.read_bytes()).hexdigest()
    for page in ("konto", "zalecenia", "zlecenie"):
        run(page)
    assert hashlib.sha256(env.read_bytes()).hexdigest() == h0
    pcon = pp.connect(env, read_only=True)
    assert pcon.execute("SELECT status FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "pending"


def _vega_specs(at: AppTest) -> list[dict]:
    import json

    def walk(n, acc):
        ch = getattr(n, "children", None)
        for c in (ch.values() if isinstance(ch, dict) else []):
            acc.append(c)
            walk(c, acc)
        return acc
    return [json.loads(e.proto.spec) for e in walk(at._tree, []) if getattr(e, "type", "") == "vega_lite_chart"]


def _vega_spec(at: AppTest) -> dict:
    specs = _vega_specs(at)
    assert len(specs) == 1, "na stronie konta jeden wykres"
    return specs[0]


def test_account_chart_axes_fit_daily_values(env):
    """Wykres „Wartość na tle porównań”: oś Y dopasowana do wartości (~1000 zł, nie od zera — inaczej serie leżą
    płasko na krawędzi i wykres wygląda na pusty), oś X dzienna (podziałka co dzień, format daty, bez godzin)."""
    at = run("konto")
    spec = _vega_spec(at)
    enc = (spec.get("layer") or [spec])[0]["encoding"]
    assert enc["y"].get("scale", {}).get("zero") is False, enc["y"]
    assert enc["x"]["type"] == "temporal" and enc["x"].get("timeUnit") == "yearmonthdate", enc["x"]
    ax = enc["x"].get("axis", {})
    assert ax.get("tickCount") == {"interval": "day", "step": 1} and ax.get("format") == "%Y-%m-%d", ax


def test_journal_status_matches_execution_before_nightly_job(env):
    """Zlecenie z ceną wykonania, którego nocny job jeszcze nie zapisał (w bazie 'pending'): dziennik pokazuje je jako
    wykonane, „Zlecenia oczekujące” go nie zawierają — oba z jednego replay; baza bez zmian (zapis tylko job)."""
    pcon = pp.connect(env)
    mcon = views.open_market_view()
    b = views.load_book(mcon)
    acc = pp.account(pcon, 1)
    oid, _ = pp.place(pcon, mcon, b, 1, "buy", "XAG", "test dziennika", amount_pln=50, D=str(acc["start_date"])[:10])
    pcon.close()
    at = run("konto")
    md = [str(m.value) for m in at.markdown]
    k = next(i for i, t in enumerate(md) if t.startswith("|") and "status" in t.splitlines()[0])   # dziennik zleceń
    rows = lambda t: [[c.strip() for c in ln.strip("|").split("|")] for ln in t.splitlines()[2:] if ln.startswith("|")]  # noqa: E731
    row = next(r for r in rows(md[k]) if r[0] == str(oid))
    assert "pending" not in row and any(c.startswith("wykonane") for c in row), row
    assert not any(r[0] == str(oid) for r in rows(md[k - 1]))      # tabela tuż przed dziennikiem = zlecenia oczekujące
    pcon = pp.connect(env, read_only=True)
    v = views.account_view(pcon, mcon, b, acc)
    j = views.journal_view(pcon, acc, executed=v["executed"])
    st_view = j["orders"].set_index("id").loc[oid, "status"]
    assert oid not in set(v["pending"]["id"]) and st_view.startswith("wykonane"), st_view
    assert pcon.execute("SELECT status FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "pending"   # bez zapisu


@pytest.mark.parametrize("page,n", [("aktywa", len(GAME_ASSETS)), ("pozostale", 2)])
def test_asset_price_charts_fit_and_ticks_by_range(env, page, n):
    """Wykresy cen na kartach aktywów: oś Y dopasowana do cen (nie od zera), oś X dzienna jednostka czasu, podziałka
    dobrana do zakresu (2 lata historii -> co 3 miesiące, format RRRR-MM)."""
    specs = _vega_specs(run(page))
    assert len(specs) == n
    for spec in specs:
        enc = (spec.get("layer") or [spec])[0]["encoding"]
        assert enc["y"].get("scale", {}).get("zero") is False, enc["y"]
        assert enc["x"].get("timeUnit") == "yearmonthdate", enc["x"]
        ax = enc["x"].get("axis", {})
        assert ax.get("tickCount") == {"interval": "month", "step": 3} and ax.get("format") == "%Y-%m", ax

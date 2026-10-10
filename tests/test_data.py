"""Testy na prawdziwej bazie data/market.duckdb (PIT, kalendarze, licencje, kompletność)."""

import pandas as pd
import pytest

from ms import db

pytestmark = pytest.mark.data


def q(con, sql, *params):
    return con.execute(sql, list(params)).df()


# ----------------------------------------------------------------- 1. PIT ogólnie

def test_known_at_not_before_observed(real):
    bad = q(real, "SELECT source, series_id, count(*) n FROM observations WHERE known_at < observed_at GROUP BY ALL")
    assert bad.empty, bad


@pytest.mark.parametrize("ts", ["2019-06-01", "2021-03-15 12:00", "2024-07-04"])
def test_as_of_never_returns_future_knowledge(real, ts):
    v = db.as_of(real, ts)
    assert (v["known_at"] <= pd.Timestamp(ts)).all()


# ----------------------------------------------------------------- 7. licencje

def test_every_row_has_license(real):
    assert q(real, "SELECT count(*) n FROM observations WHERE license IS NULL")["n"].item() == 0
    lic = q(real, "SELECT DISTINCT license FROM observations")["license"]
    assert set(lic) <= set(db.LICENSES)


def test_every_series_registered(real):
    orphan = q(real, """SELECT DISTINCT o.source, o.series_id FROM observations o
                        ANTI JOIN series s USING (source, series_id)""")
    assert orphan.empty, orphan


# ----------------------------------------------------------------- 4. kalendarze

def _dates(con, source, series_id):
    return pd.to_datetime(q(con, "SELECT observed_at FROM as_of(now()::TIMESTAMP) WHERE source=? AND series_id=? ORDER BY 1",
                            source, series_id)["observed_at"])


@pytest.mark.parametrize("sym", ["BTCUSDT", "ETHUSDT"])
def test_crypto_daily_every_day_no_gaps(real, sym):
    d = _dates(real, "binance", f"{sym}.close")
    assert len(d) > 3000
    assert (d.diff().dropna() == pd.Timedelta(days=1)).all()
    assert (d.dt.weekday >= 5).any()  # weekendy są


def test_business_day_series_have_no_weekends(real):
    """Brak forward-fill: serie dni roboczych nie mają sobót/niedziel."""
    s = q(real, """SELECT source, series_id FROM series WHERE frequency = '1d_bday'""")
    if s.empty:
        pytest.skip("brak serii 1d_bday w bazie")
    bad = q(real, """SELECT o.source, o.series_id, count(*) n FROM observations o JOIN series s USING (source, series_id)
                     WHERE s.frequency = '1d_bday' AND dayofweek(o.observed_at) IN (0, 6)
                       AND NOT contains(coalesce(o.flags, ''), 'sparse_history') GROUP BY ALL""")
    assert bad.empty, bad


def test_no_forward_fill_runs_in_crypto(real):
    """Ten sam close przez >3 dni z rzędu = podejrzenie ffill."""
    for sym in ("BTCUSDT", "ETHUSDT"):
        v = q(real, "SELECT value FROM as_of(now()::TIMESTAMP) WHERE series_id=? ORDER BY observed_at", f"{sym}.close")["value"]
        runs = (v != v.shift()).cumsum().value_counts().max()
        assert runs <= 3, (sym, runs)


# ----------------------------------------------------------------- 3. funding

@pytest.mark.parametrize("sid,source", [(f"{s}.funding.{v}", v) for v in ("binance", "bybit") for s in ("BTCUSDT", "ETHUSDT")])
def test_funding_count_equals_8h_periods(real, sid, source):
    d = _dates(real, source, sid)
    assert len(d) > 6000
    expected = int((d.max() - d.min()) / pd.Timedelta(hours=8)) + 1
    assert len(d) == expected, f"{sid}: {len(d)} != {expected}"
    assert (d.diff().dropna() == pd.Timedelta(hours=8)).all()


# ----------------------------------------------------------------- 1. PIT: przypadki FRED/ALFRED

def _first_known(con, sid, obs):
    return q(con, "SELECT min(known_at) k FROM observations WHERE series_id=? AND observed_at=?", sid, obs)["k"].item()


def test_dfii10_published_next_business_day(real):
    # 2024-07-03 (śr) -> 4 lipca święto -> publikacja pt 2024-07-05 16:15 ET
    assert _first_known(real, "FRED.DFII10", "2024-07-03") == pd.Timestamp("2024-07-05 20:15")
    v = db.as_of(real, "2024-07-05 12:00", ["FRED.DFII10"])
    assert v["observed_at"].max() == pd.Timestamp("2024-07-02")


def test_walcl_thursday_for_wednesday(real):
    k = _first_known(real, "FRED.WALCL", "2024-12-04")
    assert k.date() == pd.Timestamp("2024-12-05").date() and k.day_name() == "Thursday"
    assert db.as_of(real, "2024-12-05 12:00", ["FRED.WALCL"])["observed_at"].max() == pd.Timestamp("2024-11-27")


def test_cpi_first_release_differs_from_current(real):
    first = db.as_of(real, "2023-02-15", ["FRED.CPIAUCSL"])
    now = db.as_of(real, pd.Timestamp.now(), ["FRED.CPIAUCSL"])
    f = first.loc[first.observed_at == "2023-01-01", "value"].item()
    c = now.loc[now.observed_at == "2023-01-01", "value"].item()
    assert f == 300.536 and f != c
    assert first["observed_at"].max() == pd.Timestamp("2023-01-01")  # luty jeszcze nieznany


def test_panel_asof_uses_known_at(real):
    p = db.panel_asof(real, ["FRED.CPIAUCSL"], ["2023-02-14 13:29", "2023-02-14 13:30"])
    assert list(p["observed_at"]) == [pd.Timestamp("2022-12-01"), pd.Timestamp("2023-01-01")]


# ----------------------------------------------------------------- 5. WTI ujemne 2020-04-20

def test_wti_negative_flagged_and_no_log_return(real):
    from ms.transforms import log_returns

    v = q(real, """SELECT observed_at, value, flags FROM as_of(now()::TIMESTAMP)
                   WHERE series_id='EIA.RWTC' AND observed_at BETWEEN '2020-04-15' AND '2020-04-24' ORDER BY 1""")
    row = v[v.observed_at == "2020-04-20"].iloc[0]
    assert row["value"] < 0 and "nonpositive" in row["flags"]
    lr = log_returns(v.set_index("observed_at")["value"])
    for d in ("2020-04-20", "2020-04-21"):  # dzień ujemny i następny
        assert pd.isna(lr.loc[d, "logret"]) and lr.loc[d, "flag"] == "nonpositive_input"
    assert lr.loc["2020-04-17", "flag"] is None and pd.notna(lr.loc["2020-04-17", "logret"])
    # flaga istnieje tylko tam, gdzie wartość <= 0
    bad = q(real, "SELECT count(*) n FROM observations WHERE contains(flags, 'nonpositive') AND value > 0")["n"].item()
    assert bad == 0


# ----------------------------------------------------------------- 6. idempotencja na prawdziwych danych

def test_reingest_every_source_adds_nothing(real, tmp_path):
    """Ponowny ingest wszystkich wersji każdego źródła (offline) -> 0 nowych wierszy."""
    con = db.connect(tmp_path / "copy.duckdb")
    con.execute(f"ATTACH '{db.DB_PATH}' AS src (READ_ONLY)")
    con.execute("INSERT INTO observations SELECT * FROM src.observations")
    before = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    for (source,) in con.execute("SELECT DISTINCT source FROM observations").fetchall():
        df = con.execute("SELECT source, series_id, observed_at, known_at, value, vintage, license, flags "
                         "FROM observations WHERE source=? AND NOT contains(coalesce(flags,''), 'revised')", [source]).df()
        assert db.ingest(con, df) == 0, source
    assert con.execute("SELECT count(*) FROM observations").fetchone()[0] == before


def test_offline_collectors_rerun_add_nothing(real, tmp_path, monkeypatch):
    """Kolektory czytające pliki lokalne (snapshoty), uruchomione ponownie w trybie full na kopii bazy."""
    import shutil

    from ms.collectors import coinmetrics, curve, gpr_tpu

    copy = tmp_path / "copy.duckdb"
    shutil.copy(db.DB_PATH, copy)
    con = db.connect(copy)
    before = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    for mod in (curve, gpr_tpu, coinmetrics):
        assert mod.collect(con, full=True) == 0, mod.NAME
    assert con.execute("SELECT count(*) FROM observations").fetchone()[0] == before


# ----------------------------------------------------------------- metale: Stooq -> yfinance bez dziur

def _metal_trading_days(start, end):
    from pandas.tseries.holiday import GoodFriday

    from ms.common import us_holidays
    hol = set(pd.Timestamp(d) for d in us_holidays()) | set(GoodFriday.dates(start, end))
    return [d for d in pd.bdate_range(start, end) if d not in hol]


@pytest.mark.parametrize("stooq,yf", [("XAUUSD.close", "YF.GC=F.close"), ("XAGUSD.close", "YF.SI=F.close")])
def test_metals_no_gap_between_stooq_and_yfinance(real, stooq, yf):
    s = _dates(real, "stooq", stooq)
    y = _dates(real, "yahoo", yf)
    assert len(s) > 10000 and len(y) > 0
    # yfinance zaczyna się nie później niż pierwszy dzień handlowy po końcu Stooq
    after = _metal_trading_days(s.max() + pd.Timedelta(days=1), s.max() + pd.Timedelta(days=10))
    assert y.min() <= after[0], (s.max(), y.min())
    # od końca Stooq do końca yfinance każdy dzień handlowy jest w którejś z serii
    union = set(s) | set(y)
    missing = [d for d in _metal_trading_days(s.max(), y.max()) if d not in union]
    assert not missing, missing[:10]
    # yfinance aktualne (ostatnia świeca max 4 dni temu — weekend + święto)
    assert pd.Timestamp.now().normalize() - y.max() <= pd.Timedelta(days=4)


def test_stooq_daily_start_and_sparse_flag(real):
    for sid, start in (("XAUUSD.close", "1970-01-05"), ("XAGUSD.close", "1964-01-02")):
        r = q(real, """SELECT min(observed_at) FILTER (WHERE NOT contains(flags, 'sparse_history')) AS d,
                              max(observed_at) FILTER (WHERE contains(flags, 'sparse_history')) AS last_sparse
                       FROM as_of(now()::TIMESTAMP) WHERE series_id = ?""", sid)
        assert r["d"].item() == pd.Timestamp(start) and r["last_sparse"].item() < pd.Timestamp(start)


@pytest.mark.parametrize("stooq,yf", [("XAUUSD.close", "YF.GC=F.close"), ("XAGUSD.close", "YF.SI=F.close")])
def test_stitch_seam_has_no_source_jump_on_real_data(real, stooq, yf):
    """Sztuczne szwy w ostatnich ~60 dniach: zwrot w dniu szwu minus czysty zwrot YF (ruch rynku) < 1%."""
    import numpy as np

    from ms.transforms import stitch_metals

    def series(sid):
        v = q(real, "SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id=? ORDER BY 1", sid)
        return v.set_index("observed_at")["value"]

    s, y = series(stooq), series(yf)
    common = s.index.intersection(y.index)
    assert len(common) >= 60
    for cut in common[-60::10]:
        st = stitch_metals(s[s.index <= cut], y)
        after = y.index[y.index > cut]
        seam_day, prev_yf = after[0], y[y.index <= cut].iloc[-1]
        market = np.log(y[seam_day] / prev_yf)
        assert st.loc[seam_day, "flag"] == "seam_chained"
        assert abs(st.loc[seam_day, "logret"] - market) < 0.01, (cut, st.loc[seam_day, "logret"], market)


# ----------------------------------------------------------------- ceny rynkowe: znane w dniu notowania

@pytest.mark.parametrize("sid,d", [("EIA.RWTC", "2024-03-14"), ("EIA.RWTC", "2024-07-10"), ("EIA.RWTC", "2025-01-15"),
                                   ("EIA.RBRTE", "2024-03-14"), ("XAUUSD.close", "2024-01-05"), ("XAUUSD.close", "2024-07-10")])
def test_market_price_of_d_visible_at_d_2200(real, sid, d):
    """Decyzja 2026-10-06: cena rynkowa z D jest publiczna w D (zamknięcie sesji), więc as_of(D 22:00) ją zawiera —
    zimą i latem (czas letni)."""
    v = db.as_of(real, f"{d} 22:00", [sid])
    assert v["observed_at"].max() == pd.Timestamp(d)
    row = v[v.observed_at == d].iloc[0]
    assert "known_at_market_close" in row["flags"]


def test_wti_close_known_before_decision_in_wf(real):
    """W ramie walk-forward luka g (D vs ostatnie znane zamknięcie) dla WTI jest 0 poza wyjątkami."""
    from ms import wf
    t = wf.load(real, "WTI").table
    assert (t.loc["2010":, "g"] == 0).mean() > 0.99

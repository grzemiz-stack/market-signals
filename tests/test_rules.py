"""Etap 5 (ms.rules): brak zaglądania w przyszłość, sufit krypto, filtr trendu, wyzwalacze rebalansu, σ ropy z OVX,
blokada danych odłożonych, zgodność hasha definicji z prerejestracją w runs."""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from ms import rules as R

pytestmark = pytest.mark.data
DAYS = [pd.Timestamp(d) for d in ("2017-03-31", "2018-12-31", "2020-03-31", "2022-06-30", "2024-09-30")]


@pytest.fixture(scope="module")
def data(real):
    return R.RuleData.load(real)


def _perturbed(data: R.RuleData, t: pd.Timestamp) -> R.RuleData:
    rng = np.random.default_rng(0)
    b2 = copy.copy(data.book)
    b2.frames = {}
    for a, f in data.book.frames.items():
        f = f.copy()
        fut = f["known_at"] > t
        f.loc[fut, "value"] = rng.uniform(1, 1e5, int(fut.sum()))
        f.loc[fut, "logret"] = rng.normal(0, 0.5, int(fut.sum()))
        b2.frames[a] = f
    o = data.ovx.copy()
    o.loc[o["known_at"] > t, "value"] = rng.uniform(1, 300, int((o["known_at"] > t).sum()))
    return R.RuleData(b2, o, data.ovx_champion, data.champion_id)


@pytest.mark.parametrize("D", DAYS)
def test_decision_does_not_see_future(data, D):
    d2 = _perturbed(data, D + R.DECISION)
    for v in R.VARIANTS:
        w0, s0 = R.target_weights(data, D, v)
        w1, s1 = R.target_weights(d2, D, v)
        assert w0 == w1 and s0 == s1, v
        assert w0, f"{v} {D.date()}: brak wag"


def test_crypto_cap_and_weights_sum(data):
    for D in pd.date_range("2018-09-30", "2024-09-30", freq="QE"):
        for v in R.VARIANTS:
            w, _ = R.target_weights(data, D, v)
            assert sum(w.get(a, 0) for a in R.DEFINITION["crypto"]) <= R.DEFINITION["crypto_cap"] + 1e-12, (v, D)
            assert sum(w.values()) <= 1 + 1e-12 and all(x >= 0 for x in w.values())


def test_inverse_vol_and_trend_scaling(data):
    D = pd.Timestamp("2022-06-30")
    w1, s1 = R.target_weights(data, D, "iv_bez_filtra")
    w2, s2 = R.target_weights(data, D, "iv_filtr")
    assert set(w1) == set(R.DEFINITION["assets"]) and sum(w1.values()) == pytest.approx(1)
    # krypto ucięte do 25% -> XAG/WTI zachowują proporcję 1/σ
    assert w1["XAG"] / w1["WTI"] == pytest.approx(s1["sigma"]["WTI"] / s1["sigma"]["XAG"])
    assert set(s2["exposure"].values()) <= {0.0, 0.25, 0.5, 0.75, 1.0}
    for a in w2:
        assert w2[a] == pytest.approx(w1[a] * s2["exposure"][a])


def test_sigma_hist_definition(data):
    t = pd.Timestamp("2021-03-31") + R.DECISION
    f = data.book.frames["XAG"]
    r = f.loc[f["known_at"] <= t, "logret"].dropna()
    expected = (r.iloc[-60:].std() + r.iloc[-250:].std()) / 2 * np.sqrt(252)
    assert R.sigma_hist(data, "XAG", t) == pytest.approx(expected)
    assert R.sigma_hist(data, "BTC", pd.Timestamp("2018-01-31") + R.DECISION) is None   # < 250 notowań od 2017-08-17


def test_oil_sigma_source(data):
    D = pd.Timestamp("2020-03-31")
    _, s = R.target_weights(data, D, "iv_filtr_ovx")
    assert data.ovx_champion and s["sigma_src"]["WTI"] == "ovx"
    assert s["sigma"]["WTI"] == pytest.approx(R.sigma_ovx(data, D + R.DECISION))
    off = R.RuleData(data.book, data.ovx, False, "base_rate")
    w_off, s_off = R.target_weights(off, D, "iv_filtr_ovx")
    assert s_off["sigma_src"]["WTI"] == "hist" and w_off == R.target_weights(data, D, "iv_filtr")[0]


def test_ovx_k_only_from_finished_windows(data):
    t = pd.Timestamp("2019-06-28") + R.DECISION
    rv = data.rv_ratio()
    used = rv[rv["known_at"] <= t].iloc[-R.DEFINITION["ovx"]["k_days"]:]
    assert used.index.max() < t.normalize() - pd.Timedelta(days=20)   # okno 21 notowań po s musi się skończyć
    k = used["ratio"].median()
    assert 0.5 < k < 1.5


def test_rebalance_triggers():
    trig = R.rebalance_triggers
    D_q, D_m = pd.Timestamp("2022-06-30"), pd.Timestamp("2022-07-29")
    w = {"XAG": 0.4, "WTI": 0.3}
    assert trig(D_m, w, w, {"XAG": 1.0}, {"XAG": 1.0}) == []
    assert trig(D_q, w, w, {}, {}) == ["koniec kwartału"]
    assert trig(D_m, {"XAG": 0.51, "WTI": 0.3}, w, {}, {}) == ["odchylenie XAG"]        # +27,5%
    assert trig(D_m, {"XAG": 0.49, "WTI": 0.3}, w, {}, {}) == []                        # +22,5%
    assert trig(D_m, {"XAG": 0.4, "WTI": 0.3, "BTC": 0.01}, w, {}, {}) == ["odchylenie BTC"]  # wyjście do zera
    assert trig(D_m, w, w, {"XAG": 0.75}, {"XAG": 1.0}) == ["zmiana trendu"]


def test_holdout_locked(data):
    with pytest.raises(PermissionError):
        R.run_rules(data, "iv_filtr", "2023-01-01", "2024-10-31")
    with pytest.raises(PermissionError):
        R.HoldoutKey(object())


def test_backtest_runs_and_exits_fully(data):
    res, log = R.run_rules(data, "iv_filtr", "2019-01-01", "2021-12-31")
    assert res.switches == log["traded"].sum() > 0 and res.final > 0
    last = log[log["traded"]].iloc[-1]
    for a in R.DEFINITION["assets"]:
        if last[f"w_{a}"] == 0:
            assert a not in res.acc.pos, f"{a}: docelowo 0, a pozycja została"


def test_costs_x2():
    c, c2 = R.Costs(), R.costs_x2()
    assert c2.fx_pct == 2 * c.fx_pct and c2.spread_pct == 2 * c.spread_pct
    assert c2.crypto_commission_pct == 2 * c.crypto_commission_pct and c2.belka == c.belka
    assert c2.deposit_spread_pp == c.deposit_spread_pp


def test_definitions_match_preregistration(real):
    row = real.execute("SELECT params FROM runs WHERE stage='5-prereg' ORDER BY started_at DESC LIMIT 1").fetchone()
    assert row, "brak prerejestracji etapu 5 w runs (uv run src/backtest_rules.py prereg)"
    assert json.loads(row[0])["hash"] == R.definitions_hash(), \
        "reguły etapu 5 zmienione po prerejestracji — zmiana = nowa próba (DECISIONS), nie cicha edycja"


def test_trend_exposure_is_graded_fraction(data):
    book = data.book
    seen = set()
    for D in pd.date_range("2018-09-30", "2024-09-30", freq="ME"):
        D = D if D.weekday() < 5 else D - pd.offsets.BDay(1)
        t = D + R.DECISION
        for a in R.DEFINITION["assets"]:
            e = R.trend_exposure(data, a, D)
            if e is None:
                continue
            p1, d1 = book.known_close(a, t)
            ups = [p1 > book.known_close_before(a, t, d1 - pd.DateOffset(months=m)) for m in (3, 6, 9, 12)]
            assert e == sum(ups) / 4, (a, D)
            seen.add(e)
    assert seen & {0.25, 0.5, 0.75}, "ekspozycja stopniowana (D4), nie 0/1"


def test_dev_results_consistent_with_runs_and_rule_d7(real):
    from ms import rules_eval as E

    dev = real.execute("SELECT * FROM backtest_rules_dev").df()
    assert set(dev["hash"]) == {R.definitions_hash()}
    x1, x2 = (dev[dev.koszty_wersja == k].set_index("wariant") for k in ("x1", "x2"))
    assert E.select_winner(x1, x2)[0] == "rowny_podzial_4"          # wynik kroku 3 (raport etap5-rozwoj)
    runs = real.execute("SELECT params FROM runs WHERE stage='5'").fetchall()
    ps = [json.loads(p[0]) for p in runs]
    assert len(ps) == 14 and all(p["okres"] == ["2016-10-06", "2024-10-05"] for p in ps)   # nic z danych odłożonych
    assert all(p["hash"] == R.definitions_hash() for p in ps if p["wariant"] in R.VARIANTS)


def test_open_holdout_only_once(mem):
    mem.execute("""CREATE TABLE IF NOT EXISTS runs (run_id VARCHAR, started_at TIMESTAMP, asset VARCHAR, stage VARCHAR,
                   params VARCHAR, n_eval INTEGER, bss DOUBLE, bss_lo DOUBLE, bss_hi DOUBLE,
                   bss_vs_baseline DOUBLE, vs_lo DOUBLE, vs_hi DOUBLE, baseline_model VARCHAR, note VARCHAR)""")
    key = R.open_holdout(mem, "rowny_podzial_4")
    assert isinstance(key, R.HoldoutKey)
    assert mem.execute("SELECT count(*) FROM runs WHERE stage='5-holdout'").fetchone()[0] == 1
    assert isinstance(R.open_holdout(mem, "rowny_podzial_4"), R.HoldoutKey)       # dokończenie przerwanego: ta sama definicja
    with pytest.raises(PermissionError):
        R.open_holdout(mem, "iv_filtr")                                            # inny zwycięzca po przerwaniu
    R.close_holdout(mem, {"miesiace": 24})
    with pytest.raises(PermissionError, match="drugie otwarcie"):
        R.open_holdout(mem, "rowny_podzial_4")
    assert mem.execute("SELECT count(*) FROM runs WHERE stage='5-holdout'").fetchone()[0] == 1

import importlib.util

import numpy as np
import pandas as pd
import pytest

from ms import hypotheses as hp


def test_bh_known_example():
    p = [0.01, 0.04, 0.03, 0.005, np.nan]
    adj = hp.bh(p)
    assert np.allclose(adj[:4], [0.02, 0.04, 0.04, 0.02]) and np.isnan(adj[4])


def test_ols_matches_statsmodels():
    import statsmodels.api as sm
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    y = 0.3 * x + rng.normal(size=300)
    b, se, p, n = hp.ols_uni(x, y)
    m = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HC1")
    assert abs(b - m.params[1]) < 1e-12 and abs(se - m.bse[1]) < 1e-9
    b2, se2, _, _ = hp.ols_uni(x, y, lags=4)
    m2 = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    assert abs(se2 - m2.bse[1]) < 1e-9


def _res(sign=-1, beta=-1.0, p_bh=0.01, share52=0.8, earlier=0.0, kind="B"):
    r = hp.Result(hp.Spec("X", "XAU", kind, sign, "f"))
    r.n_last, r.beta_last, r.p_last, r.p_bh = 156, beta, 0.001, p_bh
    r.share = {"52_3lata_znak": share52, "156_wczesniej_istotne": earlier}
    return r


@pytest.mark.parametrize("kw,status", [
    ({}, "potwierdzona"),
    ({"beta": 1.0}, "odwrócona"),
    ({"p_bh": 0.5, "earlier": 0.8}, "osłabła"),
    ({"p_bh": 0.5}, "niepotwierdzona"),
    ({"share52": 0.5}, "niepotwierdzona"),   # istotna, ale niestabilna
])
def test_status_rules(kw, status):
    r = _res(**kw)
    hp.classify(r)
    assert r.status == status


def test_too_little_data():
    r = _res()
    r.n_last = 50
    hp.classify(r)
    assert r.status == "brak danych"


def test_map_block_keeps_literature_text(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("th", hp.__file__.replace("ms/hypotheses.py", "test_hypotheses.py"))
    th = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(th)
    chk = importlib.util.spec_from_file_location("cm", str(th.db.ROOT / "tools" / "check_mapa.py"))
    cm = importlib.util.module_from_spec(chk)
    chk.loader.exec_module(cm)
    copy = tmp_path / "mapa.md"
    copy.write_text(th.MAPA.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(th, "MAPA", copy)
    monkeypatch.setattr(cm, "MAPA", copy)
    before = cm.text_hash()
    rows = [("G1", "XAU", "osłabła", "B", -0.01, 0.01, 0.5, 0.6, -0.05, 0.01, None, "x", None, "r", None, False, None)]
    th.write_map_block(rows, [], pd.Timestamp("2026-10-06").date())
    th.write_map_block(rows, [], pd.Timestamp("2026-10-07").date())  # drugie uruchomienie zastępuje blok
    text = copy.read_text(encoding="utf-8")
    assert text.count("<!-- STATUS:START -->") == 1 and "osłabła" in text
    assert cm.text_hash() == before


def test_car_uses_first_close_known_after_event():
    from ms import hyp_events as he
    idx = pd.bdate_range("2024-01-01", periods=10)
    pf = pd.DataFrame({"value": np.exp(np.arange(10) * 0.01), "known_at": idx + pd.Timedelta(hours=20)}, index=idx)
    # zdarzenie 2024-01-03 12:00 -> dzień 0 = zamknięcie 01-03 (znane 20:00), start = zamknięcie 01-02
    car = he.car_table(pf, pd.Series([pd.Timestamp("2024-01-03 12:00")]), k=2)
    assert abs(car[0] - 0.03) < 1e-12  # log(P[01-05]/P[01-02])
    # zdarzenie po zamknięciu -> dzień 0 = następny dzień
    car2 = he.car_table(pf, pd.Series([pd.Timestamp("2024-01-03 21:00")]), k=0)
    assert abs(car2[0] - 0.01) < 1e-12


def test_decluster_min_gap():
    from ms import hyp_events as he
    t = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-05", "2024-01-25", "2024-02-20"]))
    assert list(he.decluster(t, 20)) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-25"), pd.Timestamp("2024-02-20")]


def test_candidate_use():
    assert hp.candidate_use(hp.Spec("X", "WTI", "P", 1, "f")) == "prognoza"
    assert hp.candidate_use(hp.Spec("X", "WTI", "ZR", 1, "x", freq="E", start_offset=0)) == "prognoza"
    assert hp.candidate_use(hp.Spec("X", "XAU", "B", -1, "f")) == "dekompozycja"
    assert hp.candidate_use(hp.Spec("X", "XAU", "ZR", 0, "x", freq="E", start_offset=-1)) == "dekompozycja"


def test_event_status_rules():
    r = hp.Result(hp.Spec("E", "WTI", "Z", +1, "", freq="E"))
    r.n_full, r.beta_full, r.p_full, r.p_bh, r.n_last, r.beta_last = 50, 0.02, 0.001, 0.01, 10, 0.01
    hp.classify(r)
    assert r.status == "potwierdzona"
    r.beta_last = -0.01
    hp.classify(r)
    assert r.status == "osłabła"
    r.n_full = 3
    hp.classify(r)
    assert r.status == "brak danych"


def test_constructive_registry_entry():
    assert "C13" in hp.CONSTRUCTIVE


def _runner_and_check(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("th", hp.__file__.replace("ms/hypotheses.py", "test_hypotheses.py"))
    th = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(th)
    copy = tmp_path / "mapa.md"
    copy.write_text(th.MAPA.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(th, "MAPA", copy)
    return th, copy


def test_map_block_each_pair_exactly_once(tmp_path, monkeypatch):
    th, copy = _runner_and_check(tmp_path, monkeypatch)
    ids = th.ids_in_map()
    assert len(ids) == len(set(ids)) and "G1" in ids
    rows = [("G6", "XAU", "niepotwierdzona", "B", None, None, None, None, None, None, None, "x", None, "r", None, False, None),
            ("G6", "XAU", "niepotwierdzona", "Z", None, None, None, None, None, None, None, "y", None, "r", None, False, None),
            ("G7", "XAU", "brak danych", "-", None, None, None, None, None, None, None, "z", None, "r", None, False, None)]
    for _ in range(3):  # wielokrotne przebiegi nie mogą dublować wierszy
        th.write_map_block(rows, [], pd.Timestamp("2026-10-06").date())
        assert th.ids_in_map() == ids
    block = copy.read_text(encoding="utf-8").split("<!-- STATUS:START -->")[1]
    labels = [ln.split("|")[1].strip() + "|" + ln.split("|")[2].strip() for ln in block.splitlines() if ln.startswith("| G")]
    assert len(labels) == len(set(labels)) == 3 and "G6 [B]|XAU" in labels and "G6 [Z]|XAU" in labels

"""Etap 3A: walk-forward bez przecieku (purge/embargo, częstość bazowa z przeszłości, prognozy tylko z danych do L(D))."""

import copy

import numpy as np
import pandas as pd
import pytest

from ms import baselines, wf

pytestmark = pytest.mark.data
CASES = [("XAU", "2021-06-16"), ("WTI", "2022-03-09"), ("BTC", "2023-05-17")]


@pytest.fixture(scope="module")
def data(real):
    return {a: wf.load(real, a) for a, _ in CASES}


def _perturb_after(d, D):
    """Zmień wszystko, czego prognoza dnia D nie może znać: zwroty po L(D) i etykiety niezakończone przed D."""
    d2 = copy.deepcopy(d)
    pl = int(d.table.loc[D, "pos_l"])
    rng = np.random.default_rng(1)
    d2.r[pl + 1:] = rng.normal(0, 0.05, len(d2.r) - pl - 1)
    hide = ~(d2.table["end_5d"] < D)
    d2.table.loc[hide, ["y_up", "y_down"]] = 1 - d2.table.loc[hide, ["y_up", "y_down"]].fillna(0)
    d2.table.loc[hide, "sigma_5d"] = d2.table.loc[hide, "sigma_5d"] * 3
    return d2


@pytest.mark.parametrize("asset,D", CASES)
@pytest.mark.parametrize("model", ["rv_ratio", "har_rv"])
def test_prediction_unchanged_by_future(data, asset, D, model):
    d = data[asset]
    D = pd.Timestamp(D)
    fn = {"rv_ratio": baselines.model_rv_ratio, "har_rv": baselines.model_har}[model]
    p0 = fn(d).loc[D]
    assert p0.notna().all()
    pd.testing.assert_series_equal(p0, fn(_perturb_after(d, D)).loc[D])


@pytest.mark.parametrize("asset,D", CASES)
def test_garch_unchanged_by_future(data, asset, D):
    d = data[asset]
    D = pd.Timestamp(D)
    month = d.table.index[(d.table.index.year == D.year) & (d.table.index.month == D.month)]
    one = copy.deepcopy(d)
    one.table = d.table.loc[month]
    p0 = baselines.model_garch(one, sims=500).loc[D]
    pert = _perturb_after(d, D)
    pert.table = pert.table.loc[month]
    assert p0.notna().all()
    pd.testing.assert_series_equal(p0, baselines.model_garch(pert, sims=500).loc[D])


@pytest.mark.parametrize("asset", [a for a, _ in CASES])
def test_purge_and_embargo(data, asset):
    t = data[asset].table
    for start, _ in wf.folds(t):
        tr = wf.train_mask(t, start)
        assert (t.loc[tr, "end_5d"] < start).all()
        assert (t.index[tr] <= start - wf.EMBARGO).all()


@pytest.mark.parametrize("asset,D", CASES)
def test_base_rate_uses_only_finished_labels(data, asset, D):
    d = data[asset]
    D = pd.Timestamp(D)
    b0 = wf.base_rate(d.table).loc[D]
    assert pd.testing.assert_series_equal(b0, wf.base_rate(_perturb_after(d, D).table).loc[D]) is None

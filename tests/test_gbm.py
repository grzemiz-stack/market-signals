"""Etap 3B: perturbacja przyszłości, purge/embargo treningu, kalibracja tylko z przeszłych foldów, wagi unikalności."""

import copy

import numpy as np
import pandas as pd
import pytest

from ms import gbm, wf

CASES = [("XAU", "up", "2024-06-12"), ("BTC", "down", "2025-03-19")]


@pytest.fixture(scope="module")
def loaded(real):
    out = {}
    for asset, _, _ in CASES:
        d = wf.load(real, asset)
        out[asset] = (d, gbm.load_inputs(real, d))
    return out


def _perturb(d, inputs, D):
    """Wszystko, czego prognoza dnia D nie może znać: cechy i prognozy punktów odniesienia po D, etykiety niezakończone przed D."""
    d2 = copy.deepcopy(d)
    X0, groups, bases = copy.deepcopy(inputs)
    after = X0.index > D
    rng = np.random.default_rng(3)
    X0.loc[after] = rng.normal(size=(int(after.sum()), X0.shape[1]))
    for p in bases.values():
        p.loc[p.index > D] = rng.uniform(0, 1, size=(int((p.index > D).sum()), 2))
    hide = ~(d2.table["end_5d"] < D)
    d2.table.loc[hide, ["y_up", "y_down"]] = 1 - d2.table.loc[hide, ["y_up", "y_down"]].fillna(0)
    return d2, (X0, groups, bases)


@pytest.mark.data
@pytest.mark.parametrize("asset,direction,D", CASES)
def test_future_perturbation_does_not_change_prediction(real, loaded, asset, direction, D):
    d, inputs = loaded[asset]
    D = pd.Timestamp(D)
    kw = dict(folds_from=D.year - 4, until=D)
    p0, _, _ = gbm.run(real, d, direction, inputs=inputs, **kw)
    d2, in2 = _perturb(d, inputs, D)
    p1, _, _ = gbm.run(real, d2, direction, inputs=in2, **kw)
    assert np.isfinite(p0.loc[D, "raw"]) and np.isfinite(p0.loc[D, "p"])
    assert p0.loc[D, "raw"] == p1.loc[D, "raw"] and p0.loc[D, "p"] == p1.loc[D, "p"]
    # kontrola: zaburzenie przeszłości ZMIENIA prognozę (test coś sprawdza)
    d3 = copy.deepcopy(d)
    past = d3.table["end_5d"] < pd.Timestamp(f"{D.year}-01-01") - wf.EMBARGO
    d3.table.loc[past, "y_" + direction] = 1 - d3.table.loc[past, "y_" + direction]
    p3, _, _ = gbm.run(real, d3, direction, inputs=inputs, **kw)
    assert p3.loc[D, "raw"] != p0.loc[D, "raw"]


@pytest.mark.data
@pytest.mark.parametrize("asset,direction,D", CASES)
def test_train_purge_and_calibration_from_past_folds(real, loaded, asset, direction, D):
    d, inputs = loaded[asset]
    _, meta, _ = gbm.run(real, d, direction, inputs=inputs)
    for m in meta.itertuples():
        start = pd.Timestamp(f"{m.fold}-01-01")
        assert m.train_max_end_5d < start                       # żadna etykieta treningowa nie kończy się w foldzie
        if m.calibrated:
            assert m.cal_max_date <= start - wf.EMBARGO           # kalibracja tylko na OOS z poprzednich foldów
    assert meta["calibrated"].any()


def test_uniqueness_weights():
    t = pd.DataFrame({"pos_d": [0, 1, 2, 10]}, index=pd.bdate_range("2020-01-01", periods=4))
    w = gbm.uniqueness_weights(t)
    assert w.iloc[3] > w.iloc[1]          # etykieta bez nakładania ma większą wagę
    assert abs(w.mean() - 1) < 1e-12

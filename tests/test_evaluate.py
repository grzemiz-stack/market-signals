import copy

import numpy as np
import pandas as pd
import pytest

from ms import analogs, evaluate


def _perturb(d, mask):
    d2 = copy.deepcopy(d)
    lab = d2.lab
    for c in ("up_5d", "down_5d"):
        lab.loc[mask, c] = lab.loc[mask, c].map(lambda v: (not v) if pd.notna(v) else True)
    for c in ("fwd_ret_5d", "fwd_ret_20d", "fwd_ret_60d", "fwd_max_dd_60d"):
        lab.loc[mask, c] = lab.loc[mask, c].fillna(0) * -3 + 0.5
    return d2


@pytest.mark.data
@pytest.mark.parametrize("asset,q", [("XAU", "2019-03-12"), ("WTI", "2022-05-10"), ("BTC", "2023-11-20")])
def test_query_does_not_see_labels_with_path_end_at_or_after_query(real, asset, q):
    d = analogs.load(real, asset)
    qd = d.z.index[d.z.index <= pd.Timestamp(q)].max()
    base = evaluate.evaluate_query(d, qd)
    hidden = ~(d.lab["path_end"] < qd)  # path_end >= qd albo brak (ostatnie 60 obs)
    assert hidden.sum() > 60
    assert evaluate.evaluate_query(_perturb(d, hidden), qd) == base
    # kontrola: zaburzenie etykiet widocznych zmienia wynik (test coś sprawdza)
    assert evaluate.evaluate_query(_perturb(d, ~hidden), qd) != base


def test_brier_and_bss():
    df = pd.DataFrame({"p_up": [1.0, 0.0], "p_down": [0.0, 0.0], "p_up_base": [0.5, 0.5], "p_down_base": [0.5, 0.5],
                       "p_up_rand": [0.5, 0.5], "p_down_rand": [0.5, 0.5], "y_up": [1.0, 0.0], "y_down": [0.0, 0.0],
                       "med_ret_20d": [0.1, -0.1], "fwd_ret_20d": [0.2, -0.2], "med_ret_60d": [0.0, 0.0], "fwd_ret_60d": [0.0, 0.0],
                       "med_ret_20d_rand": [0.0, 0.0], "med_ret_60d_rand": [0.0, 0.0]})
    m = evaluate.metrics(df)
    assert m["brier_analog"] == 0 and m["brier_base"] == 0.25 and m["bss_analog"] == 1


def test_verdict_requires_ci_above_zero():
    ci = pd.DataFrame({"lo": [-0.01, -0.1], "hi": [0.2, 0.1]}, index=["bss_analog", "bss_analog_minus_random"])
    assert "nie lepsze od bazowej" in evaluate.verdict({"bss_analog": 0.1}, ci)
    ci.loc["bss_analog", "lo"] = 0.01
    assert "analogie lepsze od bazowej" in evaluate.verdict({"bss_analog": 0.1}, ci)


def test_bootstrap_blocks_keep_order_and_size():
    rng = np.random.default_rng(1)
    n = 30
    df = pd.DataFrame({"query": pd.bdate_range("2020-01-01", periods=n), "p_up": rng.random(n), "p_down": rng.random(n),
                       "p_up_base": 0.06, "p_down_base": 0.06, "p_up_rand": 0.06, "p_down_rand": 0.06,
                       "y_up": rng.integers(0, 2, n).astype(float), "y_down": 0.0,
                       "med_ret_20d": rng.normal(size=n), "fwd_ret_20d": rng.normal(size=n), "med_ret_60d": rng.normal(size=n),
                       "fwd_ret_60d": rng.normal(size=n), "med_ret_20d_rand": rng.normal(size=n), "med_ret_60d_rand": rng.normal(size=n)})
    ci = evaluate.bootstrap(df, n=200)
    assert (ci["lo"] <= ci["hi"]).all()

"""Dekompozycja: betas tygodnia t niezależne od tygodnia t i późniejszych; wkłady + niewyjaśnione = zwrot."""

import numpy as np
import pandas as pd
import pytest

from ms import decompose as dc


def _synthetic(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq="W-FRI")
    W = pd.DataFrame({"dfii10_chg": rng.normal(size=n), "vix_chg": rng.normal(size=n), "mom_4w": rng.normal(size=n)}, index=idx)
    W.insert(0, "ret", 0.5 * W["dfii10_chg"] - 0.2 * W["vix_chg"] + rng.normal(0, 0.5, n))
    return W


def test_sum_of_contributions_plus_unexplained_equals_return():
    out, _ = dc.rolling_decompose(_synthetic())
    g = out[[c for c in out.columns if c.startswith("g:")]].sum(axis=1)
    assert np.allclose(g + out["unexplained"], out["ret"], atol=1e-9, rtol=0)


def test_betas_at_t_do_not_depend_on_t_and_later_synthetic():
    W = _synthetic()
    t = W.index[300]
    _, b0 = dc.rolling_decompose(W)
    W2 = W.copy()
    W2.loc[W2.index >= t] = np.random.default_rng(9).normal(size=W2.loc[W2.index >= t].shape) * 10
    _, b1 = dc.rolling_decompose(W2)
    pd.testing.assert_frame_equal(b0[b0.week == t].reset_index(drop=True), b1[b1.week == t].reset_index(drop=True))


@pytest.mark.data
@pytest.mark.parametrize("asset,week", [("XAU", "2023-06-16"), ("BTC", "2024-03-10")])
def test_betas_real_data_perturbation(real, asset, week):
    W = dc.factors(real, asset)
    t = pd.Timestamp(week)
    _, b0 = dc.rolling_decompose(W)
    W2 = W.copy()
    W2.loc[W2.index >= t, "ret"] = W2.loc[W2.index >= t, "ret"] * -5 + 0.1  # zwroty z t i później
    _, b1 = dc.rolling_decompose(W2)
    x0, x1 = b0[b0.week == t].reset_index(drop=True), b1[b1.week == t].reset_index(drop=True)
    assert len(x0) >= 5
    pd.testing.assert_frame_equal(x0, x1)
    # kontrola: tydzień później betas się zmieniają (zaburzony zwrot z t wszedł do okna)
    later = W.index[W.index.get_loc(t) + 1]
    assert not b0[b0.week == later]["beta"].reset_index(drop=True).equals(b1[b1.week == later]["beta"].reset_index(drop=True))


@pytest.mark.data
def test_weekly_identity_in_table(real):
    d = real.execute("""SELECT week, asset, sum(contribution) s, any_value(unexplained) u, any_value(ret) r
                        FROM decomp_weekly GROUP BY week, asset""").df()
    assert len(d) > 5000 and (abs(d["s"] + d["u"] - d["r"]) < 1e-9).all()

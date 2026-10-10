"""Perturbacja dnia D+1 (decyzja 2026-10-06): zmiana WARTOŚCI obserwacji z dniem obserwacji > D nie może wpłynąć na
nic liczonego dla D — cechy, czynniki tygodniowe (dekompozycja, hipotezy), prognozy modeli zmienności.
Uzupełnia test perturbacji po known_at: łapie błędnie wczesne known_at (np. dzień notowania ustawiony za wcześnie)."""

import shutil

import pandas as pd
import pytest

from ms import baselines, db, decompose as dc, features, hypotheses as hp, wf

pytestmark = pytest.mark.data
D = pd.Timestamp("2024-03-15")  # piątek: koniec tygodnia dla metali i ropy


@pytest.fixture(scope="module")
def perturbed(tmp_path_factory):
    copy = tmp_path_factory.mktemp("d1") / "m.duckdb"
    shutil.copy(db.DB_PATH, copy)
    con = db.connect(copy)
    # wszystkie obserwacje z dnia D+1 i późniejszych (dni obserwacji > D; 5-min z samego D zostają)
    n = con.execute("UPDATE observations SET value = value * 1.5 + 3 WHERE observed_at >= ?", [D + pd.Timedelta(days=1)]).fetchone()[0]
    assert n > 100_000
    yield con
    con.close()


@pytest.mark.parametrize("asset", ["XAU", "WTI", "BTC"])
def test_features_for_d(real, perturbed, asset):
    a, b = features.compute_asset(real, asset, D), features.compute_asset(perturbed, asset, D)
    pd.testing.assert_series_equal(a.loc[D], b.loc[D])
    pd.testing.assert_series_equal(features.zscore(a, asset).loc[D], features.zscore(b, asset).loc[D])
    later = D + pd.Timedelta(days=7)  # kontrola: tydzień później perturbacja musi być widoczna
    assert not features.compute_asset(real, asset, later).loc[later].equals(features.compute_asset(perturbed, asset, later).loc[later])


@pytest.mark.parametrize("asset", ["XAU", "XAG", "WTI"])
def test_weekly_factors_for_week_ending_d(real, perturbed, asset):
    end = D + pd.Timedelta(days=2)
    w0, w1 = dc.factors(real, asset, end), dc.factors(perturbed, asset, end)
    pd.testing.assert_series_equal(w0.loc[D], w1.loc[D])
    h0, h1 = hp.weekly(real, asset, end), hp.weekly(perturbed, asset, end)
    cols = [c for c in h0.columns if not c.startswith("fwd_")]  # fwd_* to z definicji przyszłość (etykiety)
    pd.testing.assert_series_equal(h0.loc[D, cols], h1.loc[D, cols])


@pytest.mark.parametrize("asset", ["XAU", "WTI"])
def test_volatility_models_for_d(real, perturbed, asset):
    d0, d1 = wf.load(real, asset), wf.load(perturbed, asset)
    for fn in (baselines.model_rv_ratio, baselines.model_har):
        pd.testing.assert_series_equal(fn(d0).loc[D], fn(d1).loc[D])
    pd.testing.assert_series_equal(baselines.model_iv_raw(real, d0).loc[D], baselines.model_iv_raw(perturbed, d1).loc[D])

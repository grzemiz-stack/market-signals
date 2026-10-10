"""Cechy: brak przecieku z przyszłości (perturbacja), z-score tylko z przeszłości, brak kolumn etykiet."""

import shutil

import numpy as np
import pandas as pd
import pytest

from ms import db, features

pytestmark = pytest.mark.data
D = pd.Timestamp("2023-06-14")  # środa; dzień roboczy USA
ASSETS = ("XAU", "WTI", "BTC")


@pytest.fixture(scope="module")
def perturbed(tmp_path_factory):
    """Kopia bazy, w której KAŻDA wartość z known_at > D 22:00 jest zmieniona."""
    if not db.DB_PATH.exists():
        pytest.fail("brak bazy")
    copy = tmp_path_factory.mktemp("pert") / "copy.duckdb"
    shutil.copy(db.DB_PATH, copy)
    con = db.connect(copy)
    n = con.execute("UPDATE observations SET value = value * 1.37 + 11 WHERE known_at > ?",
                    [D + pd.Timedelta(hours=22)]).fetchone()[0]
    assert n > 100_000  # perturbacja naprawdę coś zmieniła
    yield con
    con.close()


def _row(con, asset, end):
    raw = features.compute_asset(con, asset, end)
    return raw, features.zscore(raw, asset)


@pytest.mark.parametrize("asset", ASSETS)
def test_perturbation_future_values_do_not_change_features(real, perturbed, asset):
    raw0, z0 = _row(real, asset, D)
    raw1, z1 = _row(perturbed, asset, D)
    pd.testing.assert_series_equal(raw0.loc[D], raw1.loc[D])
    pd.testing.assert_series_equal(z0.loc[D], z1.loc[D])
    assert raw0.loc[D].notna().sum() >= 15  # test nie przechodzi „na pustych” cechach


@pytest.mark.parametrize("asset", ASSETS)
def test_perturbation_is_detectable_after_d(real, perturbed, asset):
    """Kontrola testu: dzień po D (dane zmienione) MUSI się różnić — inaczej perturbacja nic nie sprawdza."""
    later = D + pd.Timedelta(days=30)
    raw0, _ = _row(real, asset, later)
    raw1, _ = _row(perturbed, asset, later)
    assert not raw0.loc[later].equals(raw1.loc[later])


@pytest.mark.parametrize("asset", ASSETS)
def test_zscore_at_d_independent_of_later_data(real, asset):
    raw_d, z_d = _row(real, asset, D)
    raw_all, z_all = _row(real, asset, pd.Timestamp.now().normalize())
    pd.testing.assert_series_equal(raw_d.loc[D], raw_all.loc[D])
    pd.testing.assert_series_equal(z_d.loc[D], z_all.loc[D])


def test_zscore_needs_one_year():
    raw = pd.DataFrame({"x": np.arange(300.0)}, index=pd.bdate_range("2020-01-01", periods=300))
    raw.attrs["groups"] = {"x": "ryzyko"}
    z = features.zscore(raw, "XAU")
    assert z["x"].iloc[:251].isna().all() and z["x"].iloc[251:].notna().all()

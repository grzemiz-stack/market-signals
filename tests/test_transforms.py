import numpy as np
import pandas as pd

from ms.transforms import log_returns


def test_nonpositive_gives_flag_not_exception():
    r = log_returns(pd.Series([10.0, -5.0, 8.0, 9.0]))
    assert r["logret"].isna().tolist() == [True, True, True, False]
    assert r["flag"].tolist() == [None, "nonpositive_input", "nonpositive_input", None]


def _series(dates, values):
    return pd.Series(values, index=pd.to_datetime(dates))


def test_stitch_removes_basis_jump():
    d = pd.bdate_range("2026-01-01", periods=12)
    spot = pd.Series(range(100, 112), index=d, dtype=float)
    fut = spot * 1.02  # baza 2%: bez skalowania szew dałby ~2% fałszywego zwrotu
    from ms.transforms import stitch_metals
    s = stitch_metals(spot.iloc[:8], fut)
    seam_day = d[8]
    true_ret = float(np.log(spot.iloc[8] / spot.iloc[7]))
    assert abs(s.loc[seam_day, "logret"] - true_ret) < 1e-12
    assert s.loc[seam_day, "flag"] == "seam_chained" and s.loc[seam_day, "source"] == "yahoo"
    assert abs(s.loc[seam_day, "basis_factor"] - 1 / 1.02) < 1e-12


def test_stitch_flat_market_no_return_from_source_change():
    d = pd.bdate_range("2026-01-01", periods=10)
    spot = pd.Series(2000.0, index=d)
    from ms.transforms import stitch_metals
    s = stitch_metals(spot.iloc[:6], spot * 1.005)
    assert (s["logret"].dropna().abs() <= 0.01).all() and abs(s.loc[d[6], "logret"]) < 1e-12


def test_stitch_without_common_days_gives_nan_seam():
    from ms.transforms import stitch_metals
    s = stitch_metals(_series(["2026-01-01", "2026-01-02"], [100.0, 101.0]),
                      _series(["2026-01-05", "2026-01-06"], [103.0, 104.0]))
    assert pd.isna(s.loc["2026-01-05", "logret"]) and s.loc["2026-01-05", "flag"] == "seam"
    assert pd.notna(s.loc["2026-01-06", "logret"])


def test_stitch_nonsynchronous_closes_seam_is_market_move():
    """Spot i futures z różnymi godzinami zamknięcia: stosunek skacze, zwrot w dniu szwu = ruch futures."""
    from ms.transforms import stitch_metals
    d = pd.bdate_range("2026-01-01", periods=10)
    fut = pd.Series([30, 30.3, 29.9, 30.5, 30.1, 30.8, 30.2, 31.0, 30.6, 31.2], index=d)
    spot = fut * pd.Series([1.0, 0.985, 1.015, 0.99, 1.01, 0.98, 1.02, 0.99, 1.0, 1.0], index=d)
    s = stitch_metals(spot.iloc[:7], fut)
    assert abs(s.loc[d[7], "logret"] - np.log(31.0 / 30.2)) < 1e-12


def test_stitch_seam_day_missing_in_yf_falls_back_to_scaled():
    from ms.transforms import stitch_metals
    spot = _series(["2026-01-01", "2026-01-02", "2026-01-05"], [100.0, 101.0, 102.0])
    fut = _series(["2026-01-01", "2026-01-02", "2026-01-06"], [100.5, 101.5, 103.0])
    s = stitch_metals(spot, fut)
    assert s.loc["2026-01-06", "flag"] == "seam_scaled" and pd.notna(s.loc["2026-01-06", "logret"])

import numpy as np
import pandas as pd
import pytest

from ms import labels


def test_path_metrics_on_known_path():
    # 252 dni historii ze zmiennością, potem: spadek -3%, -2%, potem +1% dziennie
    rng = np.random.default_rng(0)
    hist = list(rng.normal(0, 0.01, 252))
    path = [-0.03, -0.02] + [0.01] * 70
    lr = pd.Series(hist + path, index=pd.bdate_range("2020-01-01", periods=252 + len(path)))
    lab = labels.compute(lr)
    d = lr.index[251]  # ostatni dzień historii
    r = lab.loc[d]
    assert abs(r["fwd_ret_5d"] - (-0.05 + 0.03)) < 1e-12
    assert abs(r["fwd_max_dd_60d"] - (-0.05)) < 1e-12 and r["fwd_trough_day"] == 2
    assert r["fwd_days_to_recover"] == 7  # -0.05 + 5×0.01 = 0 w dniu 7
    assert abs(r["fwd_rebound_60d"] - 58 * 0.01) < 1e-9
    assert r["path_end"] == lr.index[251 + 60] and r["end_5d"] == lr.index[251 + 5]
    assert abs(r["sigma_5d"] - lr.iloc[:252].std() * np.sqrt(5)) < 1e-12


def test_not_recovered_is_nan_and_no_drop_is_zero():
    lr = pd.Series([0.0] * 252 + [-0.01] * 61, index=pd.bdate_range("2020-01-01", periods=313))
    r = labels.compute(lr).loc[lr.index[251]]
    assert np.isnan(r["fwd_days_to_recover"]) and r["fwd_trough_day"] == 60
    lr2 = pd.Series([0.001] * 313, index=lr.index)
    r2 = labels.compute(lr2).loc[lr.index[251]]
    assert r2["fwd_days_to_recover"] == 0 and r2["fwd_trough_day"] == 0 and r2["fwd_max_dd_60d"] == 0


def test_nan_in_window_gives_nan_label():
    lr = pd.Series([0.01] * 260 + [np.nan] + [0.01] * 70, index=pd.bdate_range("2020-01-01", periods=331))
    lab = labels.compute(lr)
    assert np.isnan(lab.loc[lr.index[257], "fwd_ret_5d"]) and pd.isna(lab.loc[lr.index[257], "up_5d"])


@pytest.mark.data
@pytest.mark.parametrize("asset", ["XAU", "XAG"])
def test_metal_labels_from_stitch_metals(real, asset):
    from ms.pit import first_release
    from ms.prices import ASSETS
    from ms.transforms import stitch_metals
    fr = first_release(real, list(ASSETS[asset]))
    fr = fr[~fr["flags"].fillna("").str.contains("sparse_history")]
    s = stitch_metals(*(fr[fr.series_id == sid].set_index("observed_at")["value"] for sid in ASSETS[asset]))
    expected = s["logret"].rolling(5).sum().shift(-5)
    got = real.execute("SELECT date, fwd_ret_5d FROM labels WHERE asset=? ORDER BY date", [asset]).df().set_index("date")["fwd_ret_5d"]
    got.index = pd.to_datetime(got.index)
    both = pd.concat([expected.rename("e"), got.rename("g")], axis=1).dropna()
    assert len(both) > 10000 and np.allclose(both["e"], both["g"], atol=1e-12)


@pytest.mark.data
def test_wti_negative_window_labels_nan(real):
    v = real.execute("SELECT date, fwd_ret_5d FROM labels WHERE asset='WTI' AND date BETWEEN '2020-04-13' AND '2020-04-20' ORDER BY 1").df()
    assert len(v) == 6  # D+1..D+5 zawiera 04-20 lub 04-21 (logret NaN)
    assert v["fwd_ret_5d"].isna().all()


@pytest.mark.data
def test_features_table_has_no_label_columns(real):
    cols = {c for (c,) in real.execute("SELECT column_name FROM information_schema.columns WHERE table_name='features_daily'").fetchall()}
    assert cols, "brak tabeli features_daily"
    feats = {f for (f,) in real.execute("SELECT DISTINCT feature FROM features_daily").fetchall()}
    names = cols | feats
    assert not names & set(labels.LABEL_COLUMNS)
    assert not [n for n in names if any(w in n for w in ("fwd", "future", "label", "up_5d", "down_5d", "path_end", "end_5d"))]
    nxt = real.execute("SELECT fwd_ret_5d FROM labels WHERE asset='WTI' AND date = '2020-04-21'").fetchone()[0]
    assert nxt is not None and not np.isnan(nxt)  # okno 04-22..04-28 już bez ujemnych cen

import numpy as np
import pandas as pd
import pytest

from ms import analogs


def test_group_weighting_independent_of_feature_count():
    """Grupa z 10 cechami i grupa z 1 cechą ważą tyle samo."""
    idx = pd.to_datetime(["2020-01-01", "2020-02-01"])
    cols = [f"a{i}" for i in range(10)] + ["b0", "c0"]
    groups = {**{f"a{i}": "A" for i in range(10)}, "b0": "B", "c0": "C"}
    z = pd.DataFrame(0.0, index=idx, columns=cols)
    z.loc["2020-01-01", [f"a{i}" for i in range(10)]] = 1.0  # różnica 1 w każdej z 10 cech grupy A
    z.loc["2020-02-01", "b0"] = 1.0                          # różnica 1 w jedynej cesze grupy B
    d = analogs.distances(z, pd.Series(0.0, index=cols), groups)
    assert np.isclose(d.loc["2020-01-01", "distance"], d.loc["2020-02-01", "distance"])


def test_nan_features_skipped_and_group_count():
    z = pd.DataFrame({"a": [0.5, np.nan], "b": [0.5, np.nan], "c": [0.5, 0.1]}, index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    d = analogs.distances(z, pd.Series({"a": 0.0, "b": 0.0, "c": 0.0}), {"a": "A", "b": "B", "c": "C"})
    assert d.loc["2020-01-01", "n_groups"] == 3 and d.loc["2020-01-02", "n_groups"] == 1


def test_pick_spaced():
    # kolejność = ranking; 01-15 za blisko 01-10, 01-31 za blisko 02-05 (5 dni)
    d = pd.DatetimeIndex(pd.to_datetime(["2020-01-10", "2020-01-15", "2020-02-05", "2020-01-31"]))
    assert analogs.pick_spaced(d, 3) == [pd.Timestamp("2020-01-10"), pd.Timestamp("2020-02-05")]


@pytest.mark.data
@pytest.mark.parametrize("asset,query", [("XAU", "2026-10-06"), ("WTI", "2026-10-06"), ("WTI", "2020-03-16"), ("BTC", "2024-08-05")])
def test_analog_exclusions_and_spacing(real, asset, query):
    r = analogs.find(real, asset, query)
    d = r.analogs.index
    assert len(d) == analogs.K
    assert (d <= r.query - pd.Timedelta(days=60)).all()          # żadna data w 60 dniach przed zapytaniem
    assert (r.analogs["path_end"] < r.query).all()                # ścieżka do przodu nie zachodzi na zapytanie
    assert all(abs((a - b).days) >= 20 for i, a in enumerate(d) for b in d[i + 1:])
    assert (r.analogs["n_groups"] == len(r.groups_used)).all()
    nq = int(analogs.load(real, asset).z.loc[r.query].notna().sum())
    assert (r.analogs["n_features"] >= 0.7 * nq).all()
    assert r.oldest_candidate is not None and r.analogs.index.min() >= r.oldest_candidate
    assert r.analogs["up_5d"].notna().all() and r.analogs["fwd_ret_60d"].notna().all()
    rd = r.random.index
    assert all(abs((a - b).days) >= 20 for i, a in enumerate(rd) for b in rd[i + 1:])
    assert (rd <= r.query - pd.Timedelta(days=60)).all()

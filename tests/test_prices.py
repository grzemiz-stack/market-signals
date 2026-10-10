import numpy as np
import pandas as pd
import pytest

from ms.prices import ASSETS, price_frame
from ms.transforms import stitch_metals

pytestmark = pytest.mark.data


@pytest.mark.parametrize("asset", list(ASSETS))
def test_price_frame_sane(real, asset):
    f = price_frame(real, asset)
    assert f.index.is_monotonic_increasing and not f.index.duplicated().any()
    assert (f["known_at"] >= f.index).all()
    assert f["known_at"].notna().all()


def test_wti_nonpositive_is_nan_with_flag(real):
    f = price_frame(real, "WTI")
    for d in ("2020-04-20", "2020-04-21"):
        assert np.isnan(f.loc[d, "logret"]) and f.loc[d, "flag"] == "nonpositive_input"


@pytest.mark.parametrize("asset,pair", [("XAU", ("XAUUSD.close", "YF.GC=F.close")), ("XAG", ("XAGUSD.close", "YF.SI=F.close"))])
def test_metals_logret_is_stitch_metals(real, asset, pair):
    from ms.pit import first_release
    fr = first_release(real, list(pair))
    fr = fr[~fr["flags"].fillna("").str.contains("sparse_history")]
    s = stitch_metals(fr[fr.series_id == pair[0]].set_index("observed_at")["value"],
                      fr[fr.series_id == pair[1]].set_index("observed_at")["value"])
    pd.testing.assert_series_equal(price_frame(real, asset)["logret"], s["logret"], check_names=False)

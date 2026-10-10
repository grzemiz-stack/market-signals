import pytest

from ms.collectors import funding

H = 3600 * 1000


class FakeHttp:
    def __init__(self, pages):
        self.pages = list(pages)

    def get(self, url, params=None):
        page = self.pages.pop(0)

        class R:
            def json(self_inner):
                return page
        return R()


def rec(t):
    return {"fundingTime": t, "fundingRate": "0.0001"}


def test_binance_page_jump_is_detected(monkeypatch):
    t0 = 1_600_000_000_000 - (1_600_000_000_000 % (8 * H))
    first = [rec(t0 + i * 8 * H) for i in range(1000)]
    jump = [rec(t0 + 1000 * 8 * H + 24 * H)]  # brakuje 3 okresów między stronami
    with pytest.raises(funding.PaginationError):
        funding.fetch_binance(FakeHttp([first, jump]), "BTCUSDT", t0)


def test_grid_gaps():
    t0 = 1_600_000_000_000 - (1_600_000_000_000 % (8 * H))
    import pandas as pd
    ts = pd.Series([t0, t0 + 8 * H + 3, t0 + 24 * H])
    assert len(funding.grid_gaps(ts)) == 1

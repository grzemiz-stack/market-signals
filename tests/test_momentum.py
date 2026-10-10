"""Backtest momentum: brak zaglądania w przyszłość, koszty zmniejszają wynik, konto bez transakcji = lokata."""

import copy

import numpy as np
import pandas as pd
import pytest

from ms import momentum as mm
from ms.trading import Account, Costs, PriceBook

pytestmark = pytest.mark.data
END = pd.Timestamp("2026-09-30")


@pytest.fixture(scope="module")
def book(real):
    return PriceBook(real)


@pytest.mark.parametrize("D,lb", [("2018-01-31", "1m"), ("2020-03-27", "4w"), ("2024-06-28", "3m")])
def test_signal_does_not_see_future(book, D, lb):
    D = pd.Timestamp(D)
    w0, r0 = mm.signal(book, D, lb)
    b2 = copy.copy(book)
    b2.frames = {}
    t = D + mm.DECISION
    for a, f in book.frames.items():
        f = f.copy()
        f.loc[f["known_at"] > t, "value"] = np.random.default_rng(0).uniform(1, 1e5, int((f["known_at"] > t).sum()))
        b2.frames[a] = f
    w1, r1 = mm.signal(b2, D, lb)
    assert w0 == w1 and r0 == r1 and w0 is not None


def test_costs_reduce_result(book):
    start = END - pd.DateOffset(years=3)
    with_c = mm.run_momentum(book, "1m", False, start, END)
    no_c = mm.run_momentum(book, "1m", False, start, END, costs=Costs.zero())
    assert with_c.switches > 0
    assert with_c.final_liq < no_c.final_liq and with_c.costs > 0 and no_c.costs == 0


def test_account_without_trades_is_cash_plus_interest(book):
    start, end = pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31")
    r = mm.run_deposit(book, start, end)
    c = Costs()
    expected = 1000.0
    for d in pd.date_range(start, end - pd.Timedelta(days=1)):
        expected *= 1 + book.deposit_rate(d, c) * (1 - c.belka) / 365
    assert abs(r.values.iloc[-1] - expected) < 1e-9 * expected
    assert r.tax == 0 and r.costs == 0 and expected > 1000


def _book_until(book, last):
    b = copy.copy(book)
    b.frames = {a: f[f.index <= pd.Timestamp(last)] for a, f in book.frames.items()}
    return b


def test_trade_without_price_raises(book):
    b = _book_until(book, "2026-10-05")
    acc = Account(1000.0, Costs(), last_accrual=pd.Timestamp("2026-10-06"))
    with pytest.raises(ValueError, match="brak zamknięcia"):
        acc.buy("XAU", 500.0, pd.Timestamp("2026-10-06"), b)
    assert acc.cash == 1000.0 and not acc.pos and not acc.trades       # nic nie zabrane, nic nie zapisane


def test_benchmarks_wait_for_price_instead_of_nan(book):
    """paper.py status 2026-10-06: kup_i_trzymaj_XAU = nan zł, bo kupno w dniu startu bez ceny z tego dnia w bazie."""
    from ms import paper

    b = _book_until(book, "2026-10-05")
    acc_row = pd.Series({"start_date": pd.Timestamp("2026-10-06"), "start_cash": 1000.0, "momentum_variant": "momentum_1m"})
    bm = paper.benchmarks(b, acc_row, pd.Timestamp("2026-10-07"))
    assert all(np.isfinite(v) for v in bm.values()), bm
    assert bm["kup_i_trzymaj_XAU"] == pytest.approx(bm["lokata"])          # czeka na cenę: gotówka jak lokata
    r = mm.run_buy_hold(b, "XAU", "2026-10-06", "2026-10-07")
    assert r.acc.trades == [] and r.values.notna().all()
    # gdy cena trafi do bazy, kupno wykonuje się w pierwszym dniu z ceną
    r2 = mm.run_buy_hold(_book_until(book, "2026-10-06"), "XAU", "2026-10-06", "2026-10-07")
    assert len(r2.acc.trades) == 1 and r2.acc.trades[0].date == pd.Timestamp("2026-10-06")


def test_rebalance_without_price_is_deferred_not_nan(book):
    b = _book_until(book, "2026-09-30")               # decyzja 30.09, wykonanie 1.10 — ceny z 1.10 jeszcze brak
    for r in (mm.run_momentum(b, "1m", False, "2026-08-01", "2026-10-02"),
              mm.run_equal_weight(b, "2026-08-01", "2026-10-02")):
        assert r.values.notna().all(), r.name
        assert all(t.date <= pd.Timestamp("2026-09-30") for t in r.acc.trades), r.name

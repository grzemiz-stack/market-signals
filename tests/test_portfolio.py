import numpy as np
import pandas as pd
import pytest

from ms import portfolio as pf


def test_crypto_pool_cost_carries_unused_costs(tmp_path):
    pcon = pf.connect(tmp_path / "p.duckdb")
    a = pf.add(pcon, asset="BTC", form="krypto_gielda", quantity=1, unit="jednostki", buy_price=3000, currency="PLN",
               buy_date=pd.Timestamp("2024-05-01").date())
    pf.add(pcon, asset="ETH", form="krypto_gielda", quantity=1, unit="jednostki", buy_price=1000, currency="PLN",
           buy_date=pd.Timestamp("2025-02-01").date())
    pf.close(pcon, a, "2024-09-01", 1000, "PLN")               # 2024: przychód 1000, koszty 3000 -> 2000 przechodzi
    assert pf.crypto_pool_cost(pcon, None, "2025-06-01") == 2000 + 1000


def test_close_requires_open_position(tmp_path):
    pcon = pf.connect(tmp_path / "p.duckdb")
    i = pf.add(pcon, asset="XAU", form="sztabka", quantity=1, unit="szt", buy_price=10000, currency="PLN",
               buy_date=pd.Timestamp("2025-01-10").date())
    pf.close(pcon, i, "2025-12-01", 12000, "PLN")
    with pytest.raises(LookupError):
        pf.close(pcon, i, "2025-12-02", 12000, "PLN")
    assert pf.positions(pcon).empty and len(pf.positions(pcon, open_only=False)) == 1


@pytest.fixture(scope="module")
def example(real):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rp", pf.ROOT / "src" / "report_portfolio.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    pcon = rp.build_example(real)
    return pcon, pf.valuate(pcon, real, "2026-10-05")


@pytest.mark.data
def test_price_fx_decomposition_sums(example):
    _, val = example
    assert np.allclose(val["price_effect"] + val["fx_effect"], val["market_pln"] - val["market0_pln"], atol=1e-9, rtol=0)
    parts = val["price_effect"] + val["fx_effect"] + val["entry_costs"] + val["exit_costs"] + val["storage"]
    assert np.allclose(parts, val["result_pln"], atol=1e-9, rtol=0)


@pytest.mark.data
def test_swap_cost_nonnegative(real, example):
    pcon, _ = example
    for pid in pf.positions(pcon)["id"]:
        for target in pf.FORMS:
            s = pf.swap_cost(pcon, real, int(pid), target, "2026-10-05")
            assert s.total >= 0 and min(s.exit_costs, s.tax, s.entry_costs) >= 0 and s.threshold_pct >= 0


@pytest.mark.data
def test_zero_shock_no_change(example):
    pcon, val = example
    s = pf.shock(val, pf.positions(pcon), {"XAU": 0.0, "BTC": 0.0}, 0.0)
    assert (s["change"] == 0).all()


@pytest.mark.data
def test_gold_bars_exemption_date_in_valuation(example):
    _, val = example
    bars = val[val.form == "sztabka"]
    assert (bars["exempt_from"] == pd.Timestamp("2025-10-01")).all() and (bars["tax_pln"] == 0).all()

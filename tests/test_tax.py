import pandas as pd
import pytest

from ms import tax


@pytest.mark.parametrize("buy,exempt", [("2025-03-15", "2025-10-01"), ("2025-03-01", "2025-10-01"), ("2025-03-31", "2025-10-01"),
                                        ("2025-04-01", "2025-11-01"), ("2025-12-20", "2026-07-01")])
def test_gold_exempt_from(buy, exempt):
    assert tax.gold_exempt_from(buy) == pd.Timestamp(exempt)


def test_gold_sale_boundary():
    early = tax.tax_on_sale("sztabka", 20000, 15000, "2025-03-15", "2025-09-30")
    late = tax.tax_on_sale("sztabka", 20000, 15000, "2025-03-15", "2025-10-01")
    assert early.tax_pln > 0 and late.tax_pln == 0


def test_crypto_year_carry_forward():
    inc, t, carry = tax.crypto_year(proceeds_pln=1000, costs_year_pln=3000, carry_in_pln=0)
    assert inc == 0 and t == 0 and carry == 2000
    inc, t, carry = tax.crypto_year(proceeds_pln=5000, costs_year_pln=1000, carry_in_pln=carry)
    assert inc == 2000 and abs(t - 380) < 1e-9 and carry == 0


@pytest.mark.data
@pytest.mark.parametrize("tx,table", [("2024-11-12", "2024-11-08"),   # 11.11 święto (pn), weekend przed
                                      ("2025-01-02", "2024-12-31"),   # 1.01 święto
                                      ("2024-11-18", "2024-11-15"),   # poniedziałek -> piątek
                                      ("2024-11-14", "2024-11-13")])  # zwykły dzień -> dzień wcześniej
def test_nbp_rate_previous_working_day(real, tx, table):
    rate, d = tax.nbp_rate_for_tax(real, "USD", tx)
    assert d == pd.Timestamp(table) and rate > 0
    assert tax.nbp_rate_for_tax(real, "PLN", tx)[0] == 1.0

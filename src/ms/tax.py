"""Zasady podatkowe (PL) — WSZYSTKIE w tym jednym module.

╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║  DO POTWIERDZENIA U DORADCY PODATKOWEGO. To nie jest porada podatkowa — uproszczony model     ║
║  zasad zapisany tak, jak rozumie je autor; przepisy i ich interpretacje się zmieniają.         ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

Zasady (stan wiedzy autora, 2026-10-06):
1. Kurs do przeliczeń: średni kurs NBP (tabela A) z ostatniego dnia roboczego PRZED dniem transakcji
   (= ostatnia opublikowana tabela przed tą datą; święta i weekendy wynikają z kalendarza publikacji NBP).
2. Krypto: 19% od nadwyżki przychodów nad kosztami w roku; koszty = wydatki na nabycie poniesione w roku
   + nadwyżka kosztów z lat poprzednich (przechodzi dalej); bez przypisywania kosztów do partii.
3. ETF (papiery wartościowe): 19% od dochodu (przychód − koszt nabycia z prowizjami); straty i zyski
   z tego źródła sumowane w roku (uproszczenie: bez odliczania strat z lat poprzednich).
4. Złoto fizyczne (sztabki, monety): sprzedaż zwolniona, gdy nastąpiła po upływie 6 miesięcy licząc od końca
   miesiąca nabycia (zakup 2025-03-15 -> zwolnienie od 2025-10-01). Sprzedaż wcześniej: dochód opodatkowany
   skalą podatkową — ZAŁOŻENIE: stawka GOLD_EARLY_RATE (12%, pierwszy próg), do potwierdzenia.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

DISCLAIMER = "Zasady podatkowe: do potwierdzenia u doradcy (to nie jest porada podatkowa)."
RATE_CAPITAL = 0.19           # krypto, ETF
GOLD_EARLY_RATE = 0.12        # ZAŁOŻENIE: złoto sprzedane przed zwolnieniem — skala podatkowa, pierwszy próg
PHYSICAL = ("sztabka", "moneta")
CRYPTO = ("krypto_gielda", "krypto_portfel")
SECURITIES = ("etf",)


def nbp_rate_for_tax(con, currency: str, tx_date) -> tuple[float, pd.Timestamp]:
    """Średni kurs NBP z ostatniego dnia roboczego przed transakcją: (kurs, data tabeli). PLN -> 1."""
    if currency.upper() == "PLN":
        return 1.0, pd.Timestamp(tx_date)
    sid = f"NBP.{currency.upper()}PLN"
    row = con.execute("""SELECT observed_at, value FROM as_of(now()::TIMESTAMP)
                         WHERE series_id = ? AND observed_at < ? ORDER BY observed_at DESC LIMIT 1""",
                      [sid, pd.Timestamp(tx_date)]).fetchone()
    if row is None:
        raise LookupError(f"brak kursu {sid} przed {tx_date}")
    return float(row[1]), pd.Timestamp(row[0])


def gold_exempt_from(buy_date) -> pd.Timestamp:
    """Pierwszy dzień, w którym sprzedaż złota fizycznego jest zwolniona:
    koniec miesiąca nabycia + 6 miesięcy -> następny dzień = 1. dzień 7. miesiąca po miesiącu nabycia."""
    d = pd.Timestamp(buy_date)
    return (d.replace(day=1) + pd.DateOffset(months=7)).normalize()


@dataclass
class TaxResult:
    tax_pln: float
    taxable_income_pln: float
    rule: str


def tax_on_sale(form: str, proceeds_pln: float, cost_pln: float, buy_date, sell_date,
                crypto_carry_pln: float = 0.0) -> TaxResult:
    """Podatek od pojedynczej (hipotetycznej) sprzedaży. Dla krypto: crypto_carry_pln = niewykorzystane koszty
    (z lat poprzednich i bieżącego roku poza tą pozycją) — dolicza się do kosztów."""
    if form in PHYSICAL:
        if pd.Timestamp(sell_date) >= gold_exempt_from(buy_date):
            return TaxResult(0.0, 0.0, f"złoto fizyczne: zwolnione od {gold_exempt_from(buy_date).date()}")
        inc = max(0.0, proceeds_pln - cost_pln)
        return TaxResult(GOLD_EARLY_RATE * inc, inc, f"złoto fizyczne przed zwolnieniem: skala, założenie {GOLD_EARLY_RATE:.0%}")
    if form in CRYPTO:
        inc = max(0.0, proceeds_pln - cost_pln - crypto_carry_pln)
        return TaxResult(RATE_CAPITAL * inc, inc, "krypto: 19% od nadwyżki przychodów nad kosztami (z przeniesieniem)")
    if form in SECURITIES:
        inc = max(0.0, proceeds_pln - cost_pln)
        return TaxResult(RATE_CAPITAL * inc, inc, "ETF: 19% od dochodu")
    raise ValueError(f"nieznana forma: {form}")


def crypto_year(proceeds_pln: float, costs_year_pln: float, carry_in_pln: float) -> tuple[float, float, float]:
    """Rozliczenie roku krypto: (dochód, podatek, nadwyżka kosztów przechodząca na kolejny rok)."""
    costs = costs_year_pln + carry_in_pln
    income = max(0.0, proceeds_pln - costs)
    return income, RATE_CAPITAL * income, max(0.0, costs - proceeds_pln)

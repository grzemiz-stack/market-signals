"""Raport portfela na PORTFELU PRZYKŁADOWYM (fikcyjnym): reports/portfolio-{data}.md.

uv run src/report_portfolio.py
Portfel przykładowy jest tworzony od nowa w data/portfolio_example.duckdb (nigdy w data/portfolio.duckdb).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, portfolio as pf, tax  # noqa: E402


def build_example(mcon) -> object:
    pf.EXAMPLE_DB.unlink(missing_ok=True)
    pcon = pf.connect(pf.EXAMPLE_DB)
    m = pf.Market(mcon)
    gold_pln = m.spot("XAU", "2025-03-15") * m.fx("2025-03-15")
    pf.add(pcon, asset="XAU", form="sztabka", quantity=2, unit="szt", oz_per_unit=1.0, buy_price=round(gold_pln * 1.04, 2),
           currency="PLN", buy_date=pd.Timestamp("2025-03-15").date(), premium_pct=4.0, buyback_discount_pct=3.0,
           note="PRZYKŁAD (fikcyjny): 2 sztabki 1 oz, cena = spot × kurs × 1,04")
    pf.add(pcon, asset="XAU", form="etf", ticker="ETF-ZŁOTO (przykład)", quantity=50, unit="jednostki", buy_price=30.0,
           currency="USD", buy_date=pd.Timestamp("2025-03-17").date(), buy_fee=5.0,
           note="PRZYKŁAD (fikcyjny): ETF na złoto, wycena przybliżona ruchem spot")
    btc = m.spot("BTC", "2025-03-15")
    pf.add(pcon, asset="BTC", form="krypto_gielda", quantity=0.1, unit="jednostki", buy_price=round(btc * 1.002, 2),
           currency="USD", buy_date=pd.Timestamp("2025-03-15").date(), buy_fee=2.0, note="PRZYKŁAD (fikcyjny): 0,1 BTC")
    return pcon


def fmt(x, d=0):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x + 0.0:,.{d}f}".replace(",", " ").replace(".", ",").replace("-0", "0") if round(x, d) == 0 else \
        f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x):
    return f"{x:+.1%}".replace(".", ",")


def main() -> int:
    mcon = db.connect(db.DB_PATH, read_only=True)
    pcon = build_example(mcon)
    m = pf.Market(mcon)
    today = min(m.usdpln.index.max(), pd.Timestamp(date.today()))
    val = pf.valuate(pcon, mcon, today)
    pos = pf.positions(pcon)
    out = [f"# Portfel — PRZYKŁAD (fikcyjny) — {today.date()}", "",
           "> **To jest portfel przykładowy, fikcyjny** — pozycje i ceny zakupu wymyślone na potrzeby raportu.",
           f"> {tax.DISCLAIMER} Zasady: src/ms/tax.py.", "",
           "Wycena: spot USD (ms.prices) × USD/PLN (NBP, ostatnia tabela <= dzień wyceny). Złoto fizyczne „na rękę” = "
           "spot × (1 − dyskonto skupu). ETF: brak notowań w bazie — przybliżenie ruchem spot złota od dnia zakupu.", "",
           "## Pozycje", "", pos[["id", "asset", "form", "ticker", "quantity", "unit", "buy_price", "currency", "buy_date",
                                  "buyback_discount_pct", "note"]].to_markdown(index=False), "",
           "## Wycena i rozbicie wyniku (PLN)", "",
           "| id | forma | rynkowa | na rękę | koszt | cena USD | kurs USD/PLN | koszty wejścia | koszty wyjścia | przechowanie | wynik | podatek | po podatku |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in val.itertuples():
        out.append(f"| {v.id} | {v.form} {v.asset} | {fmt(v.market_pln)} | {fmt(v.net_pln)} | {fmt(v.cost_pln)} | {fmt(v.price_effect)} | "
                   f"{fmt(v.fx_effect)} | {fmt(v.entry_costs)} | {fmt(v.exit_costs)} | {fmt(v.storage)} | {fmt(v.result_pln)} | "
                   f"{fmt(v.tax_pln)} | {fmt(v.after_tax_pln)} |")
    t = val.sum(numeric_only=True)
    out.append(f"| **razem** | | {fmt(t.market_pln)} | {fmt(t.net_pln)} | {fmt(t.cost_pln)} | {fmt(t.price_effect)} | {fmt(t.fx_effect)} | "
               f"{fmt(t.entry_costs)} | {fmt(t.exit_costs)} | {fmt(t.storage)} | {fmt(t.result_pln)} | {fmt(t.tax_pln)} | {fmt(t.after_tax_pln)} |")
    out += ["", "Wynik = cena USD + kurs USD/PLN + koszty wejścia + koszty wyjścia + przechowanie (suma dokładna). "
            "„Po podatku” = wynik przy hipotetycznej sprzedaży dziś.", "", "## Podatek per pozycja (do potwierdzenia u doradcy)", ""]
    for v in val.itertuples():
        out.append(f"- id {v.id} ({v.form} {v.asset}): {v.tax_rule}; podatek przy sprzedaży dziś: {fmt(v.tax_pln)} PLN")
    out += ["", "## Koszt zamiany (przykłady)", ""]
    for pid, target in ((1, "etf"), (1, "krypto_gielda"), (3, "sztabka")):
        out.append(f"- {pf.swap_cost(pcon, mcon, pid, target, today).text}")
    out += ["", "Założenia kosztów: prowizje/premie domyślne w ms.portfolio (EXIT_FEE_PCT, ENTRY_PREMIUM_PCT); próg liczony "
            "względem wartości rynkowej A (pełne tarcie zamiany).", "", "## Szoki ręczne (na rękę, przed podatkiem)", "",
            "| scenariusz | zmiana PLN | zmiana % |", "|---|---|---|"]
    base = val["net_pln"].sum()
    for name, sh, fx in (("złoto −10%", {"XAU": -10}, 0), ("USD/PLN −5%", {}, -5), ("BTC −30%", {"BTC": -30}, 0),
                         ("razem: złoto −10%, USD/PLN −5%, BTC −30%", {"XAU": -10, "BTC": -30}, -5)):
        s = pf.shock(val, pos, sh, fx)
        out.append(f"| {name} | {fmt(s['change'].sum())} | {pct(s['change'].sum() / base)} |")
    out += ["", "## Scenariusze historyczne (faktyczne łączne ruchy zastosowane do obecnego portfela)", "",
            "| okres | ruchy aktywów (USD) | USD/PLN | zmiana PLN | zmiana % | uwagi |", "|---|---|---|---|---|---|"]
    for name, (a, b) in pf.SCENARIOS.items():
        moves, fx = pf.historical_moves(m, a, b, sorted(val["asset"].unique()))
        missing = [k for k, x in moves.items() if x is None]
        s = pf.shock(val, pos, {k: x for k, x in moves.items() if x is not None}, fx)
        mv = ", ".join(f"{k} {pct(x / 100)}" if x is not None else f"{k} brak" for k, x in moves.items())
        note = (f"brak historii: {', '.join(missing)} — przyjęto 0% zmiany ceny w USD (kurs USD/PLN nadal działa)"
                if missing else "")
        out.append(f"| {name} | {mv} | {pct(fx / 100)} | {fmt(s['change'].sum())} | {pct(s['change'].sum() / base)} | {note} |")
    corr, contrib = pf.concentration(m, val, today)
    out += ["", "## Skupienie ryzyka (dzienne zwroty w PLN, 1 rok)", "", "Korelacje:", "", corr.round(2).to_markdown(), "",
            "Udział w wariancji portfela:", "", contrib.rename("udział").round(3).to_frame().to_markdown(), "",
            f"Największe ryzyko: **{contrib.idxmax()}** — {contrib.max():.0%} wariancji portfela przy "
            f"{val['net_pln'].to_numpy()[list(contrib.index).index(contrib.idxmax())] / base:.0%} wartości portfela."]
    p = db.ROOT / "reports" / f"portfolio-{date.today()}.md"
    p.write_text("\n".join(out) + "\n")
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Backtest reguły momentum (8 wariantów) vs lokata, kup-i-trzymaj złoto, równy podział 4 aktywów.

uv run src/backtest_momentum.py  ->  reports/momentum-{data}.md + tabela backtest_momentum (market.duckdb)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, momentum as mm  # noqa: E402
from ms.trading import INSTRUMENT_NAME, Costs, PriceBook  # noqa: E402

YEARS = 10


def run_all(con, end=None) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    book = PriceBook(con)
    end = pd.Timestamp(end or min(book.usdpln.index.max(), max(f.index.max() for f in book.frames.values())))
    start = end - pd.DateOffset(years=YEARS)
    res = [mm.run_momentum(book, lb, prot, start, end) for lb, prot in mm.VARIANTS]
    res += [mm.run_deposit(book, start, end), mm.run_buy_hold(book, "XAU", start, end), mm.run_equal_weight(book, start, end)]
    return pd.DataFrame([mm.metrics(r) for r in res]), start, end


def main() -> int:
    con = db.connect()
    m, start, end = run_all(con)
    con.register("bm", m.assign(start=start, end=end, built_at=pd.Timestamp.now(tz="UTC").tz_localize(None)))
    con.execute("DROP TABLE IF EXISTS backtest_momentum")
    con.execute("CREATE TABLE backtest_momentum AS SELECT * FROM bm")
    con.unregister("bm")
    c = Costs()
    mom = m[m.wariant.str.startswith("momentum")]
    best = mom.loc[mom["na_rękę_po_likwidacji"].idxmax()]
    t = m.copy()
    for col in ("kapitał_końcowy", "na_rękę_po_likwidacji", "koszty", "podatek"):
        t[col] = t[col].map(lambda x: f"{x:,.0f}".replace(",", " "))
    for col in ("zwrot_roczny", "max_obsunięcie"):
        t[col] = t[col].map(lambda x: f"{x:+.1%}".replace(".", ","))
    out = [f"# Momentum — backtest {start.date()} … {end.date()} (1000 zł)", "",
           f"> **Uwaga: 8 wariantów = 8 prób.** Najlepszy wariant ({best.wariant}) jest zawyżony przez sam wybór "
           "spośród ośmiu — jego przewaga nad resztą to częściowo szczęście. Nie traktuj go jako odkrycia.", "",
           f"Aktywa: {', '.join(INSTRUMENT_NAME[a] for a in ('BTC', 'ETH', 'XAG', 'WTI'))}; krypto wchodzi do gry, gdy ma "
           "historię na całe okno. Decyzja z danych znanych w D 22:00 UTC, wykonanie po zamknięciu następnego dnia roboczego USA. "
           f"Koszty: krypto {c.crypto_commission_pct}%, ETF/ETC 0% (do 100 tys. EUR/mies.), przewalutowanie {c.fx_pct}% "
           f"przy każdej konwersji, spread {c.spread_pct}%. Gotówka: stopa ref. NBP − {c.deposit_spread_pp} pp po Belce. "
           "Podatek 19% rozliczany 31.12 (krypto osobną pulą); „na rękę po likwidacji” = sprzedaż wszystkiego na koniec "
           "i podatek za ostatni rok. Szczegóły i uproszczenia: src/ms/trading.py, src/ms/momentum.py.", "",
           t.to_markdown(index=False), "",
           "Kolumny: kapitał końcowy przed likwidacją; zwrot roczny liczony z wartości po likwidacji; max obsunięcie i "
           "najdłuższy okres pod kreską z dziennej wyceny; zmiany = liczba zmian pozycji (równy podział: rebalanse); "
           "koszty i podatek łącznie z likwidacją."]
    p = db.ROOT / "reports" / f"momentum-{date.today()}.md"
    p.write_text("\n".join(out) + "\n")
    print(m[["wariant", "na_rękę_po_likwidacji", "zwrot_roczny", "max_obsunięcie", "zmiany", "koszty", "podatek"]].round(3).to_string())
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

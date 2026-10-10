"""Portfel — CLI (pozycje tylko przez to CLI, bez ręcznej edycji SQL). Baza: data/portfolio.duckdb (dane osobiste).

uv run src/portfolio.py add --asset XAU --form sztabka --qty 2 --unit szt --oz-per-unit 1 --price 13500 --currency PLN \\
    --date 2025-03-15 [--fee 0] [--premium 4] [--storage 0] [--discount 3] [--ticker ...] [--note ...]
uv run src/portfolio.py list [--all]
uv run src/portfolio.py close --id 1 --date 2026-10-06 --price 15000 --currency PLN [--fee 0] [--discount 3]
uv run src/portfolio.py value [--date 2026-10-06]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, portfolio as pf, tax  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(pf.PORTFOLIO_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--asset", required=True)
    a.add_argument("--form", required=True, choices=pf.FORMS)
    a.add_argument("--qty", type=float, required=True)
    a.add_argument("--unit", required=True, choices=pf.UNITS)
    a.add_argument("--oz-per-unit", type=float, default=1.0)
    a.add_argument("--price", type=float, required=True, help="cena za jednostkę (szt/oz/jednostkę)")
    a.add_argument("--currency", default="PLN")
    a.add_argument("--date", required=True)
    a.add_argument("--fee", type=float, default=0.0)
    a.add_argument("--premium", type=float)
    a.add_argument("--storage", type=float, default=0.0, help="koszt przechowania PLN/rok")
    a.add_argument("--discount", type=float, default=pf.DEFAULT_DISCOUNT_PCT, help="dyskonto skupu %% (złoto fizyczne)")
    a.add_argument("--ticker")
    a.add_argument("--note")
    lst = sub.add_parser("list")
    lst.add_argument("--all", action="store_true")
    c = sub.add_parser("close")
    c.add_argument("--id", type=int, required=True)
    c.add_argument("--date", required=True)
    c.add_argument("--price", type=float, required=True)
    c.add_argument("--currency", default="PLN")
    c.add_argument("--fee", type=float, default=0.0)
    c.add_argument("--discount", type=float)
    v = sub.add_parser("value")
    v.add_argument("--date", default=str(date.today()))
    args = ap.parse_args()

    pcon = pf.connect(args.db)
    if args.cmd == "add":
        i = pf.add(pcon, asset=args.asset, form=args.form, ticker=args.ticker, quantity=args.qty, unit=args.unit,
                   oz_per_unit=args.oz_per_unit, buy_price=args.price, currency=args.currency,
                   buy_date=pd.Timestamp(args.date).date(), buy_fee=args.fee, premium_pct=args.premium,
                   storage_cost_pln_year=args.storage, buyback_discount_pct=args.discount, note=args.note)
        print(f"dodano pozycję {i}")
    elif args.cmd == "list":
        print(pf.positions(pcon, open_only=not args.all).to_string())
    elif args.cmd == "close":
        pf.close(pcon, args.id, args.date, args.price, args.currency, args.fee, args.discount)
        print(f"zamknięto pozycję {args.id}")
    else:
        mcon = db.connect(db.DB_PATH, read_only=True)
        val = pf.valuate(pcon, mcon, args.date)
        cols = ["id", "asset", "form", "market_pln", "net_pln", "result_pln", "tax_pln", "after_tax_pln", "exempt_from"]
        out = val[cols].copy()
        num = out.select_dtypes("number").columns
        out[num] = out[num].round(0)
        print(out.to_string(index=False))
        print(tax.DISCLAIMER)
    return 0


if __name__ == "__main__":
    sys.exit(main())

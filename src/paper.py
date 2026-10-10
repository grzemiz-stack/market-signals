"""Gra na sucho — CLI. Baza data/paper.duckdb (NIE portfolio.duckdb).

uv run src/paper.py new --name "moja gra" [--cash 1000] [--date YYYY-MM-DD]
uv run src/paper.py status [--account ID]
uv run src/paper.py buy BTC 300 --reason "..." [--date YYYY-MM-DD]
uv run src/paper.py sell BTC (--all | --units 0.001) --reason "..."
uv run src/paper.py report [--account ID]
uv run src/paper.py cancel ID [--reason "..."]       # tylko przed wykonaniem; nic nie kasuje
uv run src/paper.py note ID --reason "..."            # poprawiony powód jako nowy wpis; pierwotny zostaje
uv run src/paper.py sync                              # krok joba „system”: wykonane zlecenia -> status executed w bazie
Zlecenie z dnia D wykonuje się po zamknięciu D+1 (krypto) / następnego dnia roboczego USA (ETF/ETC).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, paper as pp, views  # noqa: E402
from ms.fmt import GROUP_PL, pct, zl  # noqa: E402,F401  (GROUP_PL, zl, pct: dawne nazwy tego modułu)
from ms import fmt  # noqa: E402
from ms.trading import GAME_ASSETS, INSTRUMENT_NAME, PriceBook  # noqa: E402,F401


def asset_block(s: dict) -> list[str]:
    out = [f"### {s['asset']} — {s['instrument']} (ostatnie znane zamknięcie {s['last_close_date']})", "",
           f"- {s['prob_text']}"]
    for q, lbl in (("prob_up_5d", "w górę"), ("prob_down_5d", "w dół")):
        out.append(f"- Model {lbl}: **{s['models'][q]['edge']}**.")
    if views.decomp_text(s):
        out.append(f"- {views.decomp_text(s)}")
    out.append(f"- {views.vol_text(s)}")
    return out


def status(pcon, mcon, book, acc_row, today=None, t=None) -> str:
    v = views.account_view(pcon, mcon, book, acc_row, today)
    out = [f"# Konto „{v['name']}” (id {acc_row['id']}) — {v['today'].date()}", "",
           f"Wartość konta: **{zl(v['value'])}** (start {zl(v['start_cash'])} {v['start_date']}; "
           f"wynik {zl(v['result_pln'])}, {pct(v['result_pct'])}). Gotówka {zl(v['cash'])}; "
           f"koszty łącznie {zl(v['costs'])}, podatek {zl(v['tax'])}, odsetki {zl(v['interest'])}.", ""]
    if v["positions"]:
        out += ["| aktywo | jednostki | wartość | koszt | wynik |", "|---|---|---|---|---|"]
        for p in v["positions"]:
            out.append(f"| {p['instrument']} | {fmt.units(p['units'])} | {zl(p['value'])} | {zl(p['cost'])} | {zl(p['pnl'])} |")
        out.append("")
    if len(v["pending"]):
        out += ["Zlecenia oczekujące (wykonanie po zamknięciu D+1, gdy cena trafi do bazy):", "",
                v["pending"].to_markdown(index=False), ""]
    out += ["## Porównanie od startu konta", "", "| | wartość |", "|---|---|", f"| moje konto | {zl(v['value'])} |"]
    out += [f"| {k} | {zl(x)} |" for k, x in v["benchmarks"].items()]
    out += ["", "## Co pokazuje system (dane znane teraz)", ""]
    for a in GAME_ASSETS:
        out += asset_block(views.asset_card(mcon, book, a, t)) + [""]
    return "\n".join(out)


def report(pcon, mcon, book, acc_row) -> Path:
    today = pd.Timestamp(date.today())
    st = pp.replay(pcon, book, acc_row, today)   # status executed zapisuje nocny job (paper.py sync), nie raport
    val = st.values.iloc[-1] if len(st.values) else float(acc_row["start_cash"])
    liq, lc, lt = st.acc.liquidation_value(today, book)
    orders = pcon.execute("SELECT * FROM paper_orders WHERE account_id=? AND status <> 'cancelled' ORDER BY id",
                          [int(acc_row["id"])]).df()
    rows = []
    for o in orders.itertuples():
        snap = json.loads(o.snapshot) if o.snapshot else {}
        r5 = np.nan
        if o.status == "executed" and pd.notna(o.exec_date):
            f = book.frames[o.asset]["value"]
            after = f[f.index >= pd.Timestamp(o.exec_date)]
            if len(after) > 5:
                p0 = after.iloc[0] * book.fx(after.index[0])
                p5 = after.iloc[5] * book.fx(after.index[5])
                r5 = p5 / p0 - 1
        sign = 1 if o.side == "buy" else -1
        agree = (snap.get("p_up", np.nan) > snap.get("p_down", np.nan)) == (o.side == "buy")
        rows.append({"id": o.id, "aktywo": o.asset, "strona": o.side, "zwrot_5d": r5,
                     "trafiony": (np.sign(r5) == sign) if np.isfinite(r5) else np.nan, "wynik_kierunku": sign * r5,
                     "zgodny_z_sygnałem": agree, "powód": o.reason,
                     "poprawki": " | ".join(f"{str(j.logged_at)[:10]}: {j.text}" for j in pp.journal(pcon, o.id).itertuples()
                                            if j.kind == "note")})
    d = pd.DataFrame(rows)
    n = int(d["trafiony"].notna().sum()) if len(d) else 0
    bm = pp.benchmarks(book, acc_row, today)

    def block(sub, label):
        k = int(sub["trafiony"].notna().sum())
        if k == 0:
            return f"- {label}: brak ocenionych decyzji."
        hit, res = sub["trafiony"].dropna().astype(float).mean(), sub["wynik_kierunku"].dropna().mean()
        tail = "" if k >= pp.MIN_N_CONCLUSIONS else f" — **N = {k} < {pp.MIN_N_CONCLUSIONS}: bez wniosków.**"
        return f"- {label}: N = {k}, trafność kierunku {hit:.0%}, średni wynik w kierunku decyzji {pct(res)} (5 dni){tail}"

    out = [f"# Raport gry — konto „{acc_row['name']}”, {len(orders)} decyzji ({today.date()})", "",
           f"Wartość {zl(val)}; po likwidacji i podatku {zl(liq)} (koszty łącznie {zl(st.acc.costs_total + lc)}, "
           f"podatek {zl(st.acc.tax_total + lt)}).", "", "| | wartość |", "|---|---|", f"| moje konto | {zl(val)} |"]
    out += [f"| {k} | {zl(v)} |" for k, v in bm.items()]
    out += ["", f"## Decyzje (ocenione po 5 obserwacjach od wykonania: {n})", ""]
    if len(d):
        out += [block(d, "wszystkie"),
                block(d[d.aktywo == "WTI"], "ropa (system MA przewagę: OVX)"),
                block(d[d.aktywo.isin(["BTC", "ETH"])], "krypto (system NIE MA przewagi)"),
                block(d[d.aktywo == "XAG"], "srebro"),
                block(d[d["zgodny_z_sygnałem"] == True], "zgodne z sygnałem (kupno przy p_up > p_down / sprzedaż odwrotnie)"),  # noqa: E712
                block(d[d["zgodny_z_sygnałem"] == False], "niezgodne z sygnałem"),  # noqa: E712
                "", d.to_markdown(index=False)]
    if n < pp.MIN_N_CONCLUSIONS:
        out += ["", f"**Za mało ocenionych decyzji (N = {n} < {pp.MIN_N_CONCLUSIONS}) — liczby powyżej to opis, nie wniosek.**"]
    p = db.ROOT / "reports" / f"paper-{acc_row['id']}-{len(orders)}.md"
    p.write_text("\n".join(out) + "\n")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(pp.PAPER_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--name", required=True)
    n.add_argument("--cash", type=float, default=1000.0)
    n.add_argument("--date")
    sub.add_parser("sync")
    for c in ("status", "report"):
        sub.add_parser(c).add_argument("--account", type=int)
    b = sub.add_parser("buy")
    b.add_argument("asset", choices=GAME_ASSETS)
    b.add_argument("amount", type=float, help="kwota PLN")
    s = sub.add_parser("sell")
    s.add_argument("asset", choices=GAME_ASSETS)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--units", type=float)
    for x in (b, s):
        x.add_argument("--reason", required=True, help="powód decyzji (wymagany)")
        x.add_argument("--account", type=int)
        x.add_argument("--date", help="dzień decyzji D (domyślnie dziś)")
    cn = sub.add_parser("cancel")
    cn.add_argument("id", type=int)
    cn.add_argument("--reason", default="anulowane przez użytkownika")
    nt = sub.add_parser("note")
    nt.add_argument("id", type=int)
    nt.add_argument("--reason", required=True, help="poprawiony powód (dopisywany, nie nadpisuje)")
    a = ap.parse_args()

    pcon = pp.connect(a.db)
    if a.cmd == "note":
        pp.add_note(pcon, a.id, a.reason)
        print(f"Dopisano poprawkę powodu do zlecenia {a.id} (pierwotny powód bez zmian).")
        return 0
    mcon = db.connect(db.DB_PATH, read_only=True)
    if a.cmd == "new":
        print(f"utworzono konto {pp.new_account(pcon, mcon, a.name, a.cash, a.date)} (porównanie z: {pp.best_momentum(mcon)})")
        return 0
    book = PriceBook(mcon)
    if a.cmd == "sync":
        print(f"paper sync: nowe wykonania {pp.sync_all(pcon, book)}")
        return 0
    if a.cmd == "cancel":
        try:
            pp.cancel(pcon, book, a.id, a.reason)
        except ValueError as e:
            print(f"BŁĄD: {e}", file=sys.stderr)
            return 1
        print(f"Zlecenie {a.id} anulowane (status cancelled, wpis w dzienniku).")
        return 0
    acc_row = pp.account(pcon, a.account)
    if a.cmd == "status":
        print(status(pcon, mcon, book, acc_row))
    elif a.cmd == "report":
        print(report(pcon, mcon, book, acc_row))
    else:
        try:
            r = pp.order(pcon, mcon, book, acc_row, a.cmd, a.asset, a.reason, amount_pln=getattr(a, "amount", None),
                         units=None if a.cmd == "buy" or a.all else a.units, D=a.date)
        except (PermissionError, ValueError) as e:
            print(f"BŁĄD: {e}", file=sys.stderr)
            return 1
        snap = r["snapshot"]
        if a.cmd == "buy":
            q = f"{snap['bad_week_pct']:+.1f}".replace(".", ",")
            print(f"Przy typowym złym tygodniu (5. percentyl zwrotów 5-dniowych z roku: {q}%) "
                  f"stracisz {zl(snap['bad_week_loss_pln'])} z {zl(a.amount)}.")
        print(f"Zlecenie {r['id']} przyjęte: {a.cmd} {a.asset}, wykonanie po zamknięciu "
              f"{r['exec_date'].date()}. Powód zapisany w dzienniku.")
        if r["n_decisions"] % 10 == 0:
            print(f"{r['n_decisions']} decyzji — raport: {report(pcon, mcon, book, acc_row)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

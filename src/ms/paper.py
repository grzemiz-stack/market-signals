"""Gra na sucho: fikcyjne 1000 zł, prawdziwe ceny od startu konta do przodu. Baza data/paper.duckdb.

Zasady:
- Zlecenie złożone w D wykonuje się po zamknięciu D+1 (krypto: D+1 kalendarzowo; ETF/ETC: następny dzień roboczy USA).
- Stan konta NIE jest przechowywany — odtwarzany z dziennika zleceń + cen (ms.trading: koszty, odsetki, podatek 31.12).
- Każde zlecenie ma wymagany „powód” i migawkę tego, co system pokazywał — liczoną wyłącznie z danych znanych
  w chwili decyzji (D 22:00 UTC albo wcześniej, gdy składane teraz).
- Porównanie: najlepszy wariant momentum z backtestu (liczony od startu konta), kup-i-trzymaj złoto, lokata.
Uwaga: model w migawce wskazuje BIEŻĄCY stan rejestru (role od 2026-10-06; przy zleceniach z datą wsteczną rejestr
nie jest cofany). Ceny, prognozy, dekompozycja i zmienność — wyłącznie z danych znanych w chwili decyzji.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ms import momentum as mm
from ms.db import ROOT
from ms.trading import GAME_ASSETS, INSTRUMENT_NAME, Account, Costs, PriceBook

PAPER_DB = ROOT / "data" / "paper.duckdb"
DECISION = pd.Timedelta(hours=22)
MIN_N_CONCLUSIONS = 20

SCHEMA = """
CREATE SEQUENCE IF NOT EXISTS acc_id START 1;
CREATE SEQUENCE IF NOT EXISTS ord_id START 1;
CREATE TABLE IF NOT EXISTS paper_accounts (
    id INTEGER PRIMARY KEY DEFAULT nextval('acc_id'), name VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL,
    start_date DATE NOT NULL, start_cash DOUBLE NOT NULL, momentum_variant VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS paper_orders (
    id INTEGER PRIMARY KEY DEFAULT nextval('ord_id'), account_id INTEGER NOT NULL, placed_at TIMESTAMP NOT NULL,
    decision_date DATE NOT NULL, side VARCHAR NOT NULL CHECK (side IN ('buy', 'sell')), asset VARCHAR NOT NULL,
    amount_pln DOUBLE, units DOUBLE, reason VARCHAR NOT NULL CHECK (length(trim(reason)) > 0), snapshot JSON,
    status VARCHAR NOT NULL DEFAULT 'pending', exec_date DATE, exec_price_usd DOUBLE, exec_fx DOUBLE,
    exec_units DOUBLE, exec_value_pln DOUBLE, costs_pln DOUBLE);
CREATE SEQUENCE IF NOT EXISTS jrn_id START 1;
CREATE TABLE IF NOT EXISTS paper_journal (   -- tylko dopisywanie: anulowania i poprawki powodu
    id INTEGER PRIMARY KEY DEFAULT nextval('jrn_id'), order_id INTEGER NOT NULL, logged_at TIMESTAMP NOT NULL,
    kind VARCHAR NOT NULL CHECK (kind IN ('cancel', 'note')),
    text VARCHAR NOT NULL CHECK (length(trim(text)) > 0));
"""


def connect(path: Path | str = PAPER_DB, read_only: bool = False):
    """read_only=True: dashboard i odczyty — nic nie zapisuje (bez CREATE, bez wykonań). Zapis: CLI zleceń i joby."""
    import duckdb

    if read_only:
        return duckdb.connect(str(path), read_only=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def decision_time(D) -> pd.Timestamp:
    """Chwila, od której liczy się wiedza dla decyzji z dnia D: min(teraz, D 22:00 UTC)."""
    return min(now_utc(), pd.Timestamp(D).normalize() + DECISION)


def best_momentum(mcon) -> str:
    try:
        r = mcon.execute("""SELECT wariant FROM backtest_momentum WHERE wariant LIKE 'momentum%'
                            ORDER BY na_rękę_po_likwidacji DESC LIMIT 1""").fetchone()
        return r[0] if r else "momentum_1m"
    except Exception:
        return "momentum_1m"


def new_account(pcon, mcon, name: str, cash: float = 1000.0, start=None) -> int:
    start = pd.Timestamp(start or now_utc().date())
    return pcon.execute("""INSERT INTO paper_accounts (name, created_at, start_date, start_cash, momentum_variant)
                           VALUES (?, ?, ?, ?, ?) RETURNING id""",
                        [name, now_utc(), start.date(), cash, best_momentum(mcon)]).fetchone()[0]


def account(pcon, acc_id: int | None = None) -> pd.Series:
    q = "SELECT * FROM paper_accounts " + ("WHERE id=?" if acc_id else "ORDER BY id DESC LIMIT 1")
    df = pcon.execute(q, [acc_id] if acc_id else []).df()
    if df.empty:
        raise LookupError("brak konta — uv run src/paper.py new --name ...")
    return df.iloc[0]


# --------------------------------------------------------------------------- migawka (tylko dane znane w t)


def _price_pln_known(book: PriceBook, asset: str, t: pd.Timestamp) -> pd.Series:
    f = book.frames[asset]
    f = f[f["known_at"] <= t]
    fx = pd.Series([book.fx(d) for d in f.index], index=f.index)
    return (f["value"].clip(lower=1e-9) * fx).dropna()


def bad_week_loss(book: PriceBook, asset: str, amount_pln: float, t) -> tuple[float, float]:
    """5. percentyl zwrotów 5-obserwacyjnych w PLN z ostatniego roku (dane znane w t) -> (strata zł, percentyl %)."""
    t = pd.Timestamp(t)
    p = _price_pln_known(book, asset, t)
    p = p[p.index > t - pd.Timedelta(days=365)]
    r5 = np.log(p / p.shift(5)).dropna()
    q = float(np.percentile(r5, 5))
    return amount_pln * (1 - np.exp(q)), 100 * (np.exp(q) - 1)


def edge_label(lo: float, hi: float) -> str:
    if np.isfinite(lo) and lo > 0:
        return "ma przewagę nad częstością bazową"
    if np.isfinite(hi) and hi < 0:
        return "GORSZY od częstości bazowej"
    return "brak przewagi nad częstością bazową"


def snapshot(mcon, book: PriceBook, asset: str, t) -> dict:
    """Co system pokazuje dla aktywa w chwili t (wyłącznie dane znane w t)."""
    from ms import prob, registry

    t = pd.Timestamp(t)
    p = prob.probability(mcon, asset, t.date() if t.hour >= 22 else (t - pd.Timedelta(days=1)).date())
    cards = {}
    for q in ("prob_up_5d", "prob_down_5d"):
        ch = registry.champion(mcon, asset, q)
        cards[q] = {"model": ch.model_id, "card": ch.card, "edge": edge_label(ch.ci_lo, ch.ci_hi)}
    f = book.frames[asset]
    usd = f.loc[(f["known_at"] <= t) & (f["value"] > 0), "value"]
    lr = np.log(usd).diff().dropna()  # zmienność z cen USD znanych w t
    ann = 365 if asset in ("BTC", "ETH") else 252
    rv20, rv1y = lr.tail(20).std() * np.sqrt(ann), lr.tail(ann).std() * np.sqrt(ann)
    dec = mcon.execute("""SELECT week, "group", contribution, unexplained, ret FROM decomp_weekly
                          WHERE asset=? AND week = (SELECT max(week) FROM decomp_weekly WHERE asset=? AND week <= ?)""",
                       [asset, asset, (t - pd.Timedelta(days=1)).date()]).df()
    price, pdate = book.known_close(asset, t)
    return {
        "asset": asset, "as_of": str(t), "instrument": INSTRUMENT_NAME[asset],
        "last_close_usd": price, "last_close_date": str(pdate.date()),
        "p_up": p.p_up, "p_down": p.p_down, "base_up": p.base_up, "base_down": p.base_down,
        "x_up_pct": p.x_up_pct, "x_down_pct": p.x_down_pct, "prob_text": prob.text(p), "models": cards,
        "rv20": rv20, "rv1y": rv1y,
        "decomp_week": str(dec["week"].iloc[0]) if len(dec) else None,
        "decomp": {g: c for g, c in zip(dec["group"], dec["contribution"])} if len(dec) else {},
        "decomp_unexplained": float(dec["unexplained"].iloc[0]) if len(dec) else None,
        "decomp_ret": float(dec["ret"].iloc[0]) if len(dec) else None,
    }


# --------------------------------------------------------------------------- zlecenia i odtworzenie konta


def place(pcon, mcon, book: PriceBook, acc_id: int, side: str, asset: str, reason: str, amount_pln: float | None = None,
          units: float | None = None, D=None) -> tuple[int, dict]:
    from ms import system

    if system.system_row(pcon, acc_id) is not None:
        raise PermissionError("konto „system” wykonuje wyłącznie reguły — ręczne zlecenia są niedozwolone")
    if asset not in GAME_ASSETS:
        raise ValueError(f"aktywo spoza gry: {asset} (dozwolone: {', '.join(GAME_ASSETS)})")
    if not reason or not reason.strip():
        raise ValueError("powód decyzji jest wymagany")
    D = pd.Timestamp(D or now_utc().date())
    t = decision_time(D)
    snap = snapshot(mcon, book, asset, t)
    if side == "buy":
        loss, q = bad_week_loss(book, asset, amount_pln, t)
        snap["bad_week_loss_pln"], snap["bad_week_pct"] = loss, q
    oid = pcon.execute("""INSERT INTO paper_orders (account_id, placed_at, decision_date, side, asset, amount_pln, units,
                          reason, snapshot) VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
                       [acc_id, now_utc(), D.date(), side, asset, amount_pln, units, reason, json.dumps(snap, default=str)]
                       ).fetchone()[0]
    return oid, snap


def order(pcon, mcon, book: PriceBook, acc_row: pd.Series, side: str, asset: str, reason: str,
          amount_pln: float | None = None, units: float | None = None, D=None) -> dict:
    """Zlecenie na sucho — wspólne dla CLI (paper.py buy/sell) i formularza dashboardu. Walidacja w place()."""
    oid, snap = place(pcon, mcon, book, int(acc_row["id"]), side, asset, reason, amount_pln=amount_pln, units=units, D=D)
    n_dec = pcon.execute("SELECT count(*) FROM paper_orders WHERE account_id=? AND status <> 'cancelled'",
                         [int(acc_row["id"])]).fetchone()[0]
    return {"id": oid, "snapshot": snap, "exec_date": book.exec_date(asset, D or now_utc().date()), "n_decisions": n_dec}


def execution_moment(book: PriceBook, asset: str, decision_date) -> pd.Timestamp:
    """Chwila wykonania zlecenia: known_at zamknięcia dnia wykonania; gdy ceny jeszcze nie ma — szacunek
    (krypto: 00:00 UTC po dniu D+1; ETF/ETC: 17:00 ET dnia wykonania)."""
    from ms.common import local_to_utc

    e = book.exec_date(asset, decision_date)
    _, cdate = book.close_on(asset, e)
    if not pd.isna(cdate):
        return pd.Timestamp(book.frames[asset].loc[cdate, "known_at"])
    if asset in ("BTC", "ETH"):
        return e + pd.Timedelta(days=1)
    return pd.Timestamp(local_to_utc(e, "17:00"))


def cancel(pcon, book: PriceBook, order_id: int, reason: str = "anulowane przez użytkownika", now=None) -> None:
    """Anuluje zlecenie tylko PRZED chwilą wykonania. Nic nie kasuje: status cancelled + wpis w dzienniku."""
    o = pcon.execute("SELECT * FROM paper_orders WHERE id=?", [order_id]).df()
    if o.empty:
        raise LookupError(f"brak zlecenia {order_id}")
    o = o.iloc[0]
    if o["status"] == "cancelled":
        raise ValueError(f"zlecenie {order_id} jest już anulowane")
    now = pd.Timestamp(now) if now is not None else now_utc()
    moment = execution_moment(book, o["asset"], o["decision_date"])
    if o["status"] == "executed" or now >= moment:
        raise ValueError(f"zlecenie {order_id} zostało już wykonane ({moment:%Y-%m-%d %H:%M} UTC) — nie można anulować")
    pcon.execute("UPDATE paper_orders SET status='cancelled' WHERE id=?", [order_id])
    pcon.execute("INSERT INTO paper_journal (order_id, logged_at, kind, text) VALUES (?, ?, 'cancel', ?)", [order_id, now, reason])


def add_note(pcon, order_id: int, text: str, now=None) -> None:
    """Poprawiony powód jako NOWY wpis z datą; pierwotny powód w paper_orders zostaje bez zmian."""
    if not pcon.execute("SELECT count(*) FROM paper_orders WHERE id=?", [order_id]).fetchone()[0]:
        raise LookupError(f"brak zlecenia {order_id}")
    if not text or not text.strip():
        raise ValueError("treść poprawki jest wymagana")
    pcon.execute("INSERT INTO paper_journal (order_id, logged_at, kind, text) VALUES (?, ?, 'note', ?)",
                 [order_id, pd.Timestamp(now) if now is not None else now_utc(), text])


def journal(pcon, order_id: int | None = None) -> pd.DataFrame:
    q = "SELECT * FROM paper_journal" + (" WHERE order_id=?" if order_id else "") + " ORDER BY logged_at, id"
    return pcon.execute(q, [order_id] if order_id else []).df()


@dataclass
class State:
    acc: Account
    values: pd.Series
    executed: list


def replay(pcon, book: PriceBook, acc_row: pd.Series, until=None, costs: Costs | None = None) -> State:
    """Odtwarza konto od startu: odsetki, wykonania zleceń po zamknięciu D+1, podatek 31.12.
    Zlecenie wykonuje się tylko, gdy w bazie jest zamknięcie z dnia wykonania (albo późniejsze)."""
    from ms import system

    if system.system_row(pcon, int(acc_row["id"])) is not None:   # konto „system”: decyzje reguł, nie zlecenia
        st = system.replay(pcon, book, acc_row, until, costs)
        return State(st.acc, st.values, [])
    start = pd.Timestamp(acc_row["start_date"])
    until = pd.Timestamp(until or now_utc().normalize())
    acc = Account(float(acc_row["start_cash"]), costs or Costs(), last_accrual=start)
    orders = pcon.execute("SELECT * FROM paper_orders WHERE account_id=? AND status <> 'cancelled' ORDER BY id",
                          [int(acc_row["id"])]).df()
    plan: dict = {}
    for o in orders.itertuples():
        e = book.exec_date(o.asset, o.decision_date)
        price, cdate = book.close_on(o.asset, e)
        if pd.isna(cdate) or cdate > until:
            continue  # brak jeszcze ceny z dnia wykonania
        plan.setdefault(cdate, []).append(o)
    values, executed = {}, []
    for day in pd.date_range(start, until):
        acc.accrue(day, book)
        for o in plan.get(day, []):
            tr = (acc.buy(o.asset, o.amount_pln, day, book) if o.side == "buy"
                  else acc.sell(o.asset, None if pd.isna(o.units) else o.units, day, book))
            executed.append((o, tr))
        values[day] = acc.value(day, book)
    return State(acc, pd.Series(values), executed)


def sync_executions(pcon, state: State) -> int:
    """Zapisuje w bazie dane wykonania zleceń jeszcze 'pending' (do wglądu; stan konta i tak liczony z replay).
    Wołane WYŁĄCZNIE z joba (sync_all) — dashboard i status tylko czytają. Zwraca liczbę zleceń oznaczonych executed."""
    n = 0
    for o, tr in state.executed:
        if tr is None:
            r = pcon.execute("UPDATE paper_orders SET status='executed', exec_date=?, exec_units=0 "
                             "WHERE id=? AND status='pending' RETURNING id", [None, int(o.id)]).fetchall()
        else:
            r = pcon.execute("""UPDATE paper_orders SET status='executed', exec_date=?, exec_price_usd=?, exec_fx=?,
                                exec_units=?, exec_value_pln=?, costs_pln=? WHERE id=? AND status='pending' RETURNING id""",
                             [tr.date.date(), tr.price_usd, tr.fx, tr.units, tr.value_pln, tr.costs_pln, int(o.id)]).fetchall()
        n += len(r)
    return n


def sync_all(pcon, book: PriceBook, today=None) -> dict[str, int]:
    """Krok joba „system” (nocny): zlecenia gry z ceną zamknięcia z dnia wykonania -> status executed w bazie.
    Konta „system” pomijane (ich decyzje zapisuje src/system_accounts.py). {nazwa konta: liczba nowych wykonań}."""
    from ms import system

    out = {}
    for _, acc in pcon.execute("SELECT * FROM paper_accounts ORDER BY id").df().iterrows():
        if system.system_row(pcon, int(acc["id"])) is None:
            out[acc["name"]] = sync_executions(pcon, replay(pcon, book, acc, today))
    return out


def benchmark_paths(book: PriceBook, acc_row: pd.Series, until) -> dict[str, pd.Series]:
    """Ścieżki porównań od startu konta (momentum konta, kup-i-trzymaj złoto, lokata)."""
    start, cash = pd.Timestamp(acc_row["start_date"]), float(acc_row["start_cash"])
    until = pd.Timestamp(until)
    name = acc_row["momentum_variant"]
    if until <= start:
        return {k: pd.Series([cash], index=[start]) for k in (name, "kup_i_trzymaj_XAU", "lokata")}
    lb = next(lb for lb, prot in mm.VARIANTS if mm.variant_name(lb, prot) == name)
    prot = name.endswith("_ochronny")
    return {r.name: r.values for r in (mm.run_momentum(book, lb, prot, start, until, cash=cash),
                                       mm.run_buy_hold(book, "XAU", start, until, cash=cash),
                                       mm.run_deposit(book, start, until, cash=cash))}


def benchmarks(book: PriceBook, acc_row: pd.Series, until) -> dict[str, float]:
    return {k: float(v.iloc[-1]) for k, v in benchmark_paths(book, acc_row, until).items()}

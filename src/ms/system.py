"""Konta „system” w grze na sucho (etap 5 krok 5): reguły wykonywane automatycznie, na przyszłych danych.

- „system” = rowny_podzial_4 (zwycięzca D7), „system_ostrozny” = iv_filtr_ovx (V3; drugi test — wyłącznie przyszłe dane).
- Decyzja dnia D: te same funkcje co backtest (rules.target_weights / rebalance_triggers; równy podział: aktywa z historią),
  wyłącznie z danych znanych w D 22:00 UTC. Zapisywana w paper_system_decisions przez job „system” następnego dnia
  (OVX z FRED publikowany jest dzień później — dzięki temu decyzja = decyzja backtestu).
- Wykonanie: na zamknięciu dnia wykonania z harmonogramu silnika (momentum.plan_equal / rules.plan_rules), tym samym
  kodem (momentum.rebalance_equal / rules.execute_targets). Brak ceny z dnia wykonania -> czeka na następny dzień.
  Test: konto prowadzone tą ścieżką = backtest grosz w grosz (tests/test_system.py).
- Ręczne zlecenia na kontach „system” są odrzucane (ms.paper.place).
- Wyłączenie D9 (osobno dla każdego konta): obsunięcie > 1,5 × najgorsze z części rozwojowej -> decyzja „stop”
  (sprzedaż wszystkiego na najbliższym zamknięciu), potem konto w gotówce, bez dalszych decyzji. Reguł to nie zmienia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ms import momentum as mm, rules as R
from ms.trading import GAME_ASSETS, Account, Costs, PriceBook

ACCOUNTS = {"system": "rowny_podzial_4", "system_ostrozny": "iv_filtr_ovx"}
DD_FACTOR = 1.5
OVX_WAIT_DAYS = 5   # V3: czekaj na OVX z dnia D do 5 dni (potem reguła sama bierze ostatni świeży — jak w backteście)

SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_system (
    account_id INTEGER PRIMARY KEY, variant VARCHAR NOT NULL, rules_hash VARCHAR NOT NULL, dev_max_dd DOUBLE NOT NULL,
    dd_limit DOUBLE NOT NULL, created_at TIMESTAMP NOT NULL, note VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS paper_system_decisions (
    account_id INTEGER NOT NULL, decision_date DATE NOT NULL, exec_date DATE NOT NULL, placed_at TIMESTAMP NOT NULL,
    kind VARCHAR NOT NULL CHECK (kind IN ('rebalance', 'brak', 'stop')), target JSON, why VARCHAR, snapshot JSON,
    PRIMARY KEY (account_id, decision_date));
"""


def init(pcon) -> None:
    pcon.execute(SCHEMA)


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


def system_row(pcon, acc_id: int) -> pd.Series | None:
    """Wiersz paper_system konta albo None (konto gry). Działa też na połączeniu tylko do odczytu."""
    if not pcon.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='paper_system'").fetchone()[0]:
        return None
    df = pcon.execute("SELECT * FROM paper_system WHERE account_id=?", [int(acc_id)]).df()
    return None if df.empty else df.iloc[0]


def create(pcon, mcon, name: str, start, cash: float = 1000.0) -> int:
    """Nowe konto „system”; próg D9 z części rozwojowej (koszty x1); wpis próby w runs (stage 5-live)."""
    from ms import paper as pp

    init(pcon)
    variant = ACCOUNTS[name]
    if pcon.execute("SELECT count(*) FROM paper_accounts WHERE name=?", [name]).fetchone()[0]:
        raise ValueError(f"konto {name!r} już istnieje")
    dev_dd = mcon.execute("SELECT max_obsuniecie FROM backtest_rules_dev WHERE wariant=? AND koszty_wersja='x1'",
                          [variant]).fetchone()[0]
    acc_id = pp.new_account(pcon, mcon, name, cash, start)
    note = ("zwycięzca D7 (część rozwojowa)" if name == "system" else
            "drugi test na żywo, wybrany PO obejrzeniu wyników części rozwojowej i odłożonej — ocena wyłącznie na "
            "przyszłych danych od daty startu")
    pcon.execute("INSERT INTO paper_system VALUES (?,?,?,?,?,?,?)",
                 [acc_id, variant, R.definitions_hash(), dev_dd, DD_FACTOR * dev_dd, now_utc(), note])
    mcon.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                 [f"5-live-{name}-{pd.Timestamp(start).date()}", now_utc(), "PORTFEL", "5-live",
                  json.dumps({"konto": name, "wariant": variant, "hash": R.definitions_hash(), "start": str(pd.Timestamp(start).date()),
                              "kapital": cash, "prog_wylaczenia_D9": DD_FACTOR * dev_dd, "obsuniecie_rozwoj": dev_dd},
                             default=float), 0, note])
    return acc_id


def schedule(book: PriceBook, variant: str, start, until) -> dict:
    """{dzień wykonania: dzień decyzji} — dokładnie harmonogram silnika backtestu."""
    if variant == "rowny_podzial_4":
        return mm.plan_equal(book, start, until)
    return R.plan_rules(book, start, until)


def _decisions(pcon, acc_id: int) -> pd.DataFrame:
    return pcon.execute("SELECT * FROM paper_system_decisions WHERE account_id=? ORDER BY decision_date",
                        [int(acc_id)]).df()


@dataclass
class State:
    acc: Account
    values: pd.Series
    executed: list


def replay(pcon, book: PriceBook, acc_row: pd.Series, until=None, costs: Costs | None = None) -> State:
    """Stan konta z zapisanych decyzji (bez stanu mutowalnego), wykonanie tym samym kodem co backtest."""
    start = pd.Timestamp(acc_row["start_date"])
    until = pd.Timestamp(until or now_utc().normalize())
    acc = Account(float(acc_row["start_cash"]), costs or Costs(), last_accrual=start)
    dec = _decisions(pcon, int(acc_row["id"]))
    variant = system_row(pcon, int(acc_row["id"]))["variant"]
    pending = {pd.Timestamp(r.exec_date): r for r in dec.itertuples() if r.kind != "brak"}
    values, executed = {}, []
    for day in pd.date_range(start, until):
        acc.accrue(day, book)
        if day in pending:
            r = pending[day]
            target = json.loads(r.target) if r.target else {}
            need = {*target, *acc.pos}
            if not all(book.has_close(a, day) for a in need):
                pending.setdefault(day + pd.Timedelta(days=1), r)   # brak ceny z dnia wykonania -> następny dzień
            elif r.kind == "stop":
                R.execute_targets(acc, {}, day, book)
                executed.append((r, day))
            elif variant == "rowny_podzial_4":
                mm.rebalance_equal(acc, list(target), day, book)
                executed.append((r, day))
            else:
                R.execute_targets(acc, target, day, book)
                executed.append((r, day))
            del pending[day]
        values[day] = acc.value(day, book)
    return State(acc, pd.Series(values, dtype=float), executed)


def _ready(data: R.RuleData, variant: str, D: pd.Timestamp, today: pd.Timestamp) -> bool:
    """Decyzję dnia D podejmuje się dopiero następnego dnia (dane z D kompletne); V3 czeka też na OVX z dnia D."""
    if today <= D:
        return False
    if variant == "iv_filtr_ovx" and data.ovx.index.max() < D and today <= D + pd.Timedelta(days=OVX_WAIT_DAYS):
        return False
    return True


def decide(data: R.RuleData, variant: str, acc: Account, D: pd.Timestamp, prev_expo: dict | None) -> tuple[str, dict, str, dict]:
    """(kind, target, why, snapshot) — te same funkcje co backtest."""
    if variant == "rowny_podzial_4":
        elig = mm.assets_with_history(data.book, D, GAME_ASSETS)
        return "rebalance", {a: 1 / len(elig) for a in elig}, "równy podział: start albo koniec kwartału", {}
    target, snap = R.target_weights(data, D, variant)
    current = R.known_weights(acc, data, D)
    why = R.rebalance_triggers(D, current, target, snap["exposure"], prev_expo)
    snap = {**snap, "wagi_biezace": current}
    return ("rebalance" if why else "brak"), target, "; ".join(why), snap


def run_account(pcon, data: R.RuleData, acc_row: pd.Series, today=None) -> list[str]:
    """Dopisuje decyzje dla dni gotowych do decyzji, potem sprawdza próg D9. Zwraca opis zmian."""
    today = pd.Timestamp(today or now_utc().normalize())
    acc_id, sysrow = int(acc_row["id"]), system_row(pcon, int(acc_row["id"]))
    variant, book, log = sysrow["variant"], data.book, []
    dec = _decisions(pcon, acc_id)
    if (dec["kind"] == "stop").any():
        return ["konto zatrzymane regułą D9 — bez nowych decyzji"]
    done = set(pd.to_datetime(dec["decision_date"]))
    prev_expo = json.loads(dec["snapshot"].iloc[-1]).get("exposure") if len(dec) and dec["snapshot"].iloc[-1] else None
    for exec_day, D in sorted(schedule(book, variant, acc_row["start_date"], today + pd.Timedelta(days=40)).items(),
                              key=lambda x: x[1]):
        D = pd.Timestamp(D)
        if D in done:
            continue
        if not _ready(data, variant, D, today):
            break
        # stan jak w silniku: przebieg do dnia przed wykonaniem + odsetki do dnia wykonania, przed transakcjami
        st = replay(pcon, book, acc_row, until=pd.Timestamp(exec_day) - pd.Timedelta(days=1))
        st.acc.accrue(pd.Timestamp(exec_day), book)
        kind, target, why, snap = decide(data, variant, st.acc, D, prev_expo)
        if variant != "rowny_podzial_4":
            prev_expo = snap["exposure"]
        pcon.execute("INSERT INTO paper_system_decisions VALUES (?,?,?,?,?,?,?,?)",
                     [acc_id, D.date(), pd.Timestamp(exec_day).date(), now_utc(), kind, json.dumps(target), why,
                      json.dumps(snap, default=float)])
        log.append(f"{acc_row['name']}: decyzja {D.date()} -> {kind}{(' (' + why + ')') if why else ''}")
    # D9: obsunięcie liczone na dzień ostatniego znanego zamknięcia
    st = replay(pcon, book, acc_row, until=today)
    v = st.values.dropna()
    if len(v):
        dd = float((v / v.cummax() - 1).min())
        if dd < float(sysrow["dd_limit"]):
            last = v.index[-1]
            pcon.execute("INSERT INTO paper_system_decisions VALUES (?,?,?,?,?,?,?,?)",
                         [acc_id, (last + pd.Timedelta(days=1)).date(), book.next_bday(last).date(), now_utc(), "stop", "{}",
                          f"D9: obsunięcie {dd:.1%} < próg {float(sysrow['dd_limit']):.1%}", json.dumps({"obsuniecie": dd})])
            log.append(f"{acc_row['name']}: ZATRZYMANE (D9) — obsunięcie {dd:.1%}")
    return log


# --------------------------------------------------------------------------- alarmy (NIE są regułą handlu)

ALARM_DD = -0.30      # spadek od szczytu
ALARM_WEEK = -0.15    # spadek w 7 dni kalendarzowych


def alarms(values: pd.Series) -> list[str]:
    """Alarmy dla ścieżki wartości konta na ostatni dzień. Tylko informacja: nie zmienia decyzji ani stanu konta
    (DECISIONS 2026-10-07: alarm nie jest regułą handlu; wyłączenie konta = wyłącznie D9)."""
    v = values.dropna()
    if len(v) < 2:
        return []
    out = []
    dd = float(v.iloc[-1] / v.max() - 1)
    if dd < ALARM_DD:
        out.append(f"spadek od szczytu {dd:.1%} (próg {ALARM_DD:.0%})".replace(".", ","))
    week = v[v.index <= v.index[-1] - pd.Timedelta(days=7)]
    if len(week):
        w = float(v.iloc[-1] / week.iloc[-1] - 1)
        if w < ALARM_WEEK:
            out.append(f"spadek w tygodniu {w:.1%} (próg {ALARM_WEEK:.0%})".replace(".", ","))
    return out

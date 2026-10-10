"""Reguła momentum (backtest i porównanie w grze) + punkty odniesienia: lokata, kup-i-trzymaj złoto, równy podział.

Decyzja w dniu D z danych znanych w D 22:00 UTC (known_at); wykonanie po zamknięciu następnego dnia roboczego USA
(wszystkie aktywa jednocześnie — zamiana WTI -> BTC nie może kupić przed sprzedażą). Koszty i podatek: ms.trading.
Wariant: okno N ∈ {4 tyg. (rebalans tygodniowy), 1/3/6 mies. (rebalans miesięczny)} × ochronny (zwycięzca < 0 -> gotówka).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ms.trading import GAME_ASSETS, Account, Costs, PriceBook

LOOKBACK = {"4w": pd.DateOffset(weeks=4), "1m": pd.DateOffset(months=1), "3m": pd.DateOffset(months=3),
            "6m": pd.DateOffset(months=6)}
VARIANTS = [(lb, prot) for lb in LOOKBACK for prot in (False, True)]
DECISION = pd.Timedelta(hours=22)


def variant_name(lb: str, prot: bool) -> str:
    return f"momentum_{lb}{'_ochronny' if prot else ''}"


def rebalance_dates(book: PriceBook, start, end, freq: str) -> list[pd.Timestamp]:
    """Ostatni dzień roboczy USA tygodnia (freq='W') albo miesiąca (freq='M') w [start, end]."""
    last: dict = {}
    for d in pd.date_range(start, end):
        if d.weekday() < 5 and d not in book._hol:
            key = tuple(d.isocalendar()[:2]) if freq == "W" else (d.year, d.month)
            last[key] = d  # dni rosnąco -> zostaje ostatni dzień okresu
    return sorted(last.values())


def signal(book: PriceBook, D: pd.Timestamp, lookback: str, assets=GAME_ASSETS) -> tuple[str | None, dict]:
    """Zwroty za okno N z cen znanych w D 22:00. Aktywo bez pełnej historii okna nie startuje."""
    t = pd.Timestamp(D) + DECISION
    rets = {}
    for a in assets:
        p1, d1 = book.known_close(a, t)
        if pd.isna(d1) or d1 < pd.Timestamp(D) - pd.Timedelta(days=7):  # brak świeżej ceny
            continue
        p0 = book.known_close_before(a, t, d1 - LOOKBACK[lookback])
        first = book.frames[a].index.min()
        if np.isfinite(p0) and p0 > 0 and first <= d1 - LOOKBACK[lookback]:
            rets[a] = p1 / p0 - 1
    if not rets:
        return None, rets
    return max(rets, key=rets.get), rets


def _defer_if_no_price(plan: dict, day: pd.Timestamp, book: PriceBook, assets) -> bool:
    """Brak ceny z dnia wykonania (dane jeszcze nie w bazie) -> wykonanie przechodzi na następny dzień, jak zlecenie
    w grze. Zwraca True, gdy odłożono."""
    if all(book.has_close(a, day) for a in assets if a):
        return False
    plan.setdefault(day + pd.Timedelta(days=1), plan[day])
    del plan[day]
    return True


@dataclass
class Result:
    name: str
    values: pd.Series
    acc: Account
    switches: int
    final: float
    final_liq: float
    costs: float
    tax: float


def _finish(name, acc, values, switches, end, book) -> Result:
    liq, lc, lt = acc.liquidation_value(end, book)
    return Result(name, pd.Series(values), acc, switches, values[max(values)], liq, acc.costs_total + lc, acc.tax_total + lt)


def run_momentum(book: PriceBook, lookback: str, protective: bool, start, end, costs: Costs | None = None,
                 cash: float = 1000.0) -> Result:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    acc = Account(cash, costs or Costs(), last_accrual=start)
    plan = {}
    for D in rebalance_dates(book, start, end, "W" if lookback == "4w" else "M"):
        win, rets = signal(book, D, lookback)
        target = None if win is None or (protective and rets[win] < 0) else win
        plan[book.next_bday(D)] = target
    holding, switches, values = None, 0, {}
    for day in pd.date_range(start, end):
        acc.accrue(day, book)
        if day in plan and plan[day] != holding and not _defer_if_no_price(plan, day, book, (holding, plan[day])):
            if holding:
                acc.sell(holding, None, day, book)
            if plan[day]:
                acc.buy(plan[day], acc.cash, day, book)
            holding, switches = plan[day], switches + 1
        values[day] = acc.value(day, book)
    return _finish(variant_name(lookback, protective), acc, values, switches, end, book)


def run_deposit(book, start, end, costs=None, cash=1000.0) -> Result:
    acc = Account(cash, costs or Costs(), last_accrual=pd.Timestamp(start))
    values = {}
    for day in pd.date_range(start, end):
        acc.accrue(day, book)
        values[day] = acc.value(day, book)
    return _finish("lokata", acc, values, 0, pd.Timestamp(end), book)


def run_buy_hold(book, asset, start, end, costs=None, cash=1000.0) -> Result:
    start = pd.Timestamp(start)
    acc = Account(cash, costs or Costs(), last_accrual=start)
    buy_day, values = book.next_bday(start - pd.Timedelta(days=1)), {}
    for day in pd.date_range(start, end):
        acc.accrue(day, book)
        if day == buy_day:
            if book.has_close(asset, day):
                acc.buy(asset, acc.cash, day, book)
            else:
                buy_day += pd.Timedelta(days=1)  # brak jeszcze ceny z dnia zakupu -> czekamy, gotówka na lokacie
        values[day] = acc.value(day, book)
    return _finish(f"kup_i_trzymaj_{asset}", acc, values, 1, pd.Timestamp(end), book)


def assets_with_history(book, D, assets) -> list[str]:
    return [a for a in assets if not pd.isna(book.known_close(a, D + DECISION)[1])]


def rebalance_equal(acc: Account, elig: list[str], day: pd.Timestamp, book: PriceBook) -> None:
    """Wykonanie równego podziału na zamknięciu `day` (tylko różnice > 2%). Wspólne dla backtestu i konta „system”."""
    total = acc.value(day, book)
    target = total / len(elig)
    for a in list(acc.pos):  # sprzedaż nadwyżek
        v = acc.pos[a].units * book.value_on(a, day) * book.fx(day)
        if a not in elig or v > target * 1.02:
            acc.sell(a, acc.pos[a].units * (1 if a not in elig else (v - target) / v), day, book)
    for a in elig:  # dokupienie braków
        v = acc.pos[a].units * book.value_on(a, day) * book.fx(day) if a in acc.pos else 0.0
        if v < target * 0.98:
            acc.buy(a, min(acc.cash, target - v), day, book)


def plan_equal(book: PriceBook, start, end) -> dict:
    """Harmonogram równego podziału {dzień wykonania: dzień decyzji}: start + końce kwartałów."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    q_end = [d for d in rebalance_dates(book, start, end, "M") if d.month in (3, 6, 9, 12)]
    plan = {book.next_bday(start - pd.Timedelta(days=1)): start}
    plan.update({book.next_bday(D): D for D in q_end})
    return plan


def run_equal_weight(book, start, end, costs=None, cash=1000.0, assets=GAME_ASSETS) -> Result:
    """Równy podział aktywów z historią w dniu decyzji, rebalans kwartalny (tylko różnice)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    acc = Account(cash, costs or Costs(), last_accrual=start)
    plan = plan_equal(book, start, end)
    values, n = {}, 0
    for day in pd.date_range(start, end):
        acc.accrue(day, book)
        if day in plan and not _defer_if_no_price(plan, day, book,
                                                         {*assets_with_history(book, plan[day], assets), *acc.pos}):
            rebalance_equal(acc, assets_with_history(book, plan[day], assets), day, book)
            n += 1
        values[day] = acc.value(day, book)
    return _finish("rowny_podzial_4", acc, values, n, end, book)


def metrics(r: Result, cash: float = 1000.0) -> dict:
    v = r.values
    years = (v.index[-1] - v.index[0]).days / 365.25
    peak = v.cummax()
    dd = (v / peak - 1).min()
    under = (v < peak).astype(int)
    longest = int(under.groupby((under == 0).cumsum()).sum().max())
    return {"wariant": r.name, "kapitał_końcowy": r.final, "na_rękę_po_likwidacji": r.final_liq,
            "zwrot_roczny": (r.final_liq / cash) ** (1 / years) - 1 if years > 0 else np.nan,
            "max_obsunięcie": dd, "najdłużej_pod_kreską_dni": longest, "zmiany": r.switches,
            "koszty": r.costs, "podatek": r.tax}

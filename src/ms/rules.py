"""Etap 5: portfel regułowy (docs/ETAP5-PLAN.md, decyzje D1–D11 w docs/DECISIONS.md 2026-10-07).

R1 σ = średnia σ_60 i σ_250 (log-zwroty z cen znanych w D 22:00, w skali roku).  R2 wagi ∝ 1/σ, krypto razem ≤ 25%,
nadwyżka na XAG/WTI proporcjonalnie.  R3 trend: ekspozycja = odsetek dodatnich zwrotów z 3/6/9/12 mies., reszta na
lokacie.  R4 (V3) σ_WTI = OVX/100 × k, k = mediana z 756 dni ilorazu σ zrealizowanej w kolejnych 21 dniach / OVX
(tylko okna zakończone przed D), gdy mistrz WTI prob_down_5d jest modelem na OVX.  R5 rebalans w dniu decyzji
(ostatni dzień roboczy USA miesiąca): koniec kwartału, odchylenie wagi > ±25% względnie albo zmiana ekspozycji trendu;
zlecenia < 1% kapitału pomijane (poza wyjściem do zera).
Wykonanie, koszty, podatek, lokata — ms.trading jak w 4P.

**Reguły zamrożone:** `definitions_hash()` (DEFINITION + kod funkcji reguł) zapisany w `runs` (stage 5-prereg) przed
pierwszym przeliczeniem; test w bramce porównuje go z kodem. Dane odłożone (> DEV_END) tylko z kluczem z open_holdout().
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ms.momentum import Result, _finish, rebalance_dates
from ms.trading import Account, Costs, PriceBook

DECISION = pd.Timedelta(hours=22)
DEV_START, DEV_END = pd.Timestamp("2016-10-06"), pd.Timestamp("2024-10-05")
HOLDOUT_START, HOLDOUT_END = pd.Timestamp("2024-10-06"), pd.Timestamp("2026-10-05")

DEFINITION = {
    "etap": "5", "plan": "docs/ETAP5-PLAN.md",
    "assets": ["BTC", "ETH", "XAG", "WTI"], "crypto": ["BTC", "ETH"], "crypto_cap": 0.25,
    "sigma": {"windows": [60, 250], "combine": "mean_of_sigmas", "ann_days": {"BTC": 365, "ETH": 365, "XAG": 252, "WTI": 252},
              "min_obs": 250},
    "trend": {"months": [3, 6, 9, 12], "exposure": "fraction_positive", "price": "USD, known_close"},
    "ovx": {"series": "FRED.OVXCLS", "k_days": 756, "rv_days": 21, "rv_ann": 252, "champion_asset": "WTI",
            "champion_question": "prob_down_5d", "ovx_models": ["iv_raw", "iv_calibrated"], "fresh_days": 7},
    "rebalance": {"decision": "ostatni dzień roboczy USA miesiąca, 22:00 UTC", "quarter_months": [3, 6, 9, 12],
                  "drift_rel": 0.25, "on_trend_change": True, "min_trade_frac": 0.01, "exit_to_zero_always": True},
    "variants": {"iv_bez_filtra": {"trend": False, "ovx": False}, "iv_filtr": {"trend": True, "ovx": False},
                 "iv_filtr_ovx": {"trend": True, "ovx": True}},
    "benchmarks": ["rowny_podzial_4", "lokata", "kup_i_trzymaj_XAU", "momentum_1m"],
    "costs": "ms.trading.Costs() jak 4P; wersja x2: spread, przewalutowanie, prowizja krypto i prowizja ETF powyżej "
             "limitu x2; lokata i podatek bez zmian",
    "periods": {"dev": ["2016-10-06", "2024-10-05"], "holdout": ["2024-10-06", "2026-10-05"]},
    "selection": "D7: najprostszy z iv_bez_filtra < iv_filtr < iv_filtr_ovx, chyba że bardziej złożony ma na części "
                 "rozwojowej (koszty x1) wyższy Sharpe i nie gorsze maks. obsunięcie; zwycięzca musi mieć wyższy Sharpe "
                 "niż rowny_podzial_4 przy kosztach x1 i x2, inaczej konto system = rowny_podzial_4",
    "sharpe": "miesięczne zwroty wartości konta w PLN ponad lokatę, x sqrt(12)",
}
VARIANTS = tuple(DEFINITION["variants"])


def costs_x2(c: Costs | None = None) -> Costs:
    c = c or Costs()
    return Costs(etf_commission_pct=c.etf_commission_pct * 2, etf_free_turnover_eur=c.etf_free_turnover_eur,
                 etf_commission_above_pct=c.etf_commission_above_pct * 2, crypto_commission_pct=c.crypto_commission_pct * 2,
                 fx_pct=c.fx_pct * 2, spread_pct=c.spread_pct * 2, deposit_spread_pp=c.deposit_spread_pp, belka=c.belka)


# --------------------------------------------------------------------------- dane


@dataclass
class RuleData:
    """Wszystko, czego reguły potrzebują; każda funkcja filtruje po known_at <= chwila decyzji."""
    book: PriceBook                      # frames[a]: value, logret, known_at
    ovx: pd.DataFrame                    # index observed_at; value (%), known_at
    ovx_champion: bool                   # mistrz WTI prob_down_5d jest modelem na OVX
    champion_id: str = ""
    _rv: pd.DataFrame | None = field(default=None, repr=False)

    @classmethod
    def load(cls, con) -> "RuleData":
        from ms import registry
        from ms.pit import first_release
        from ms.prices import price_frame

        frames = {a: price_frame(con, a)[["value", "logret", "known_at"]] for a in (*DEFINITION["assets"], "XAU")}
        book = PriceBook(con, frames=frames)
        o = first_release(con, [DEFINITION["ovx"]["series"]]).set_index("observed_at")[["value", "known_at"]]
        o.index = pd.to_datetime(o.index)
        ch = registry.champion(con, DEFINITION["ovx"]["champion_asset"], DEFINITION["ovx"]["champion_question"])
        return cls(book, o.sort_index(), ch.model_id in DEFINITION["ovx"]["ovx_models"], ch.model_id)

    def rv_ratio(self) -> pd.DataFrame:
        """Dla dnia s: σ zrealizowana WTI w 21 kolejnych notowaniach / OVX(s); `known_at` = kiedy znane całe okno."""
        if self._rv is None:
            n, ann = DEFINITION["ovx"]["rv_days"], DEFINITION["ovx"]["rv_ann"]
            f = self.book.frames["WTI"]
            r = f["logret"].to_numpy()
            # każde okno liczone osobno (rolling().std() pandas liczy przyrostowo — błąd zaokrągleń z przyszłych
            # wartości przechodził na wcześniejsze okna; test PIT to wykrył)
            win = np.lib.stride_tricks.sliding_window_view(r, n).std(axis=1, ddof=1)  # std r[i..i+n-1]
            rv = np.full(len(r), np.nan)
            rv[:len(win) - 1] = win[1:] * np.sqrt(ann)                                 # okno i+1..i+n
            known = f["known_at"].shift(-n).to_numpy()                                 # znane z ostatnim dniem okna
            df = pd.DataFrame({"rv": rv, "known_at": known}, index=f.index)
            o = self.ovx["value"].reindex(df.index) / 100
            df["ratio"] = df["rv"] / o
            self._rv = df.dropna(subset=["ratio", "known_at"])
        return self._rv


# --------------------------------------------------------------------------- reguły (kod wchodzi do hasha)


def sigma_hist(data: RuleData, asset: str, t: pd.Timestamp) -> float | None:
    """R1: średnia σ_60 i σ_250 dziennych log-zwrotów znanych w t, w skali roku. Za krótka historia -> None."""
    s = DEFINITION["sigma"]
    f = data.book.frames[asset]
    r = f.loc[f["known_at"] <= t, "logret"].dropna()
    if len(r) < s["min_obs"]:
        return None
    sig = np.mean([r.iloc[-w:].std() for w in s["windows"]])
    return float(sig * np.sqrt(s["ann_days"][asset]))


def sigma_ovx(data: RuleData, t: pd.Timestamp) -> float | None:
    """R4: OVX/100 × k; k = mediana z ostatnich k_days ilorazów znanych w t. Brak świeżego OVX lub historii -> None."""
    o = DEFINITION["ovx"]
    known = data.ovx[data.ovx["known_at"] <= t]
    if known.empty or known.index[-1] < t.normalize() - pd.Timedelta(days=o["fresh_days"]):
        return None
    rv = data.rv_ratio()
    ratios = rv.loc[rv["known_at"] <= t, "ratio"]
    if len(ratios) < o["k_days"]:
        return None
    k = float(ratios.iloc[-o["k_days"]:].median())
    return float(known["value"].iloc[-1] / 100 * k)


def trend_exposure(data: RuleData, asset: str, D: pd.Timestamp) -> float | None:
    """R3: odsetek okien 3/6/9/12 mies. z dodatnim zwrotem ceny (ceny znane w D 22:00). Brak historii -> None."""
    book, t = data.book, pd.Timestamp(D) + DECISION
    p1, d1 = book.known_close(asset, t)
    if pd.isna(d1) or d1 < pd.Timestamp(D) - pd.Timedelta(days=7):
        return None
    months = DEFINITION["trend"]["months"]
    if book.frames[asset].index.min() > d1 - pd.DateOffset(months=max(months)):
        return None
    pos = [book.known_close_before(asset, t, d1 - pd.DateOffset(months=m)) for m in months]
    if not all(np.isfinite(p) and p > 0 for p in pos):
        return None
    return float(np.mean([p1 / p0 - 1 > 0 for p0 in pos]))


def target_weights(data: RuleData, D: pd.Timestamp, variant: str) -> tuple[dict, dict]:
    """R1–R4: docelowe wagi (suma <= 1; reszta = lokata) i migawka (σ, źródło σ ropy, ekspozycje)."""
    v = DEFINITION["variants"][variant]
    t = pd.Timestamp(D) + DECISION
    sig, src, expo = {}, {}, {}
    for a in DEFINITION["assets"]:
        s = sigma_hist(data, a, t)
        if s is None:
            continue
        src[a] = "hist"
        if v["ovx"] and a == "WTI" and data.ovx_champion:
            so = sigma_ovx(data, t)
            if so is not None:
                s, src[a] = so, "ovx"
        if v["trend"]:
            e = trend_exposure(data, a, D)
            if e is None:
                continue
            expo[a] = e
        sig[a] = s
    if not sig:
        return {}, {"sigma": {}, "sigma_src": {}, "exposure": {}}
    inv = {a: 1 / s for a, s in sig.items()}
    w = {a: x / sum(inv.values()) for a, x in inv.items()}
    cr = [a for a in w if a in DEFINITION["crypto"]]
    c = sum(w[a] for a in cr)
    cap = DEFINITION["crypto_cap"]
    if c > cap:
        nc = [a for a in w if a not in cr]
        for a in cr:
            w[a] *= cap / c
        for a in nc:
            w[a] *= (1 - cap) / (1 - c)
    if v["trend"]:
        w = {a: x * expo[a] for a, x in w.items()}
    return w, {"sigma": sig, "sigma_src": {a: src[a] for a in sig}, "exposure": expo}


def rebalance_triggers(D: pd.Timestamp, current: dict, target: dict, expo: dict, prev_expo: dict | None) -> list[str]:
    """R5: powody rebalansu w dniu decyzji D (pusta lista = brak transakcji). current/target: wagi w kapitale."""
    rb = DEFINITION["rebalance"]
    why = []
    if pd.Timestamp(D).month in rb["quarter_months"]:
        why.append("koniec kwartału")
    for a in sorted(set(current) | set(target)):
        cur, tgt = current.get(a, 0.0), target.get(a, 0.0)
        if (tgt <= 0 and cur > 0) or (tgt > 0 and abs(cur / tgt - 1) > rb["drift_rel"]):
            why.append(f"odchylenie {a}")
    if rb["on_trend_change"] and prev_expo is not None and expo != prev_expo:
        why.append("zmiana trendu")
    return why


RULE_FUNCS = (sigma_hist, sigma_ovx, trend_exposure, target_weights, rebalance_triggers, costs_x2)


def definitions_hash() -> str:
    """Hash definicji i kodu reguł (prerejestracja). Zmiana czegokolwiek = nowa próba."""
    payload = json.dumps(DEFINITION, sort_keys=True, ensure_ascii=False) + "".join(inspect.getsource(f) for f in RULE_FUNCS)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- symulacja


class HoldoutKey:
    """Klucz do danych odłożonych — tworzy go wyłącznie open_holdout() (jedno otwarcie, wpis w runs)."""

    def __init__(self, _token: object):
        if _token is not _TOKEN:
            raise PermissionError("dane odłożone otwiera tylko ms.rules.open_holdout()")


_TOKEN = object()


def open_holdout(con, winner: str) -> HoldoutKey:
    """Jedyne otwarcie danych odłożonych. Najpierw wpis w runs (stage 5-holdout: hash, zwycięzca D7, czas), potem klucz.
    Po zapisaniu wyników (close_holdout) każde kolejne wywołanie odmawia. Przerwany przebieg (wpis bez wyników) można
    dokończyć tylko z identyczną definicją reguł i tym samym zwycięzcą."""
    h = definitions_hash()
    rows = con.execute("SELECT params FROM runs WHERE stage='5-holdout'").fetchall()
    if rows:
        p = json.loads(rows[0][0])
        if p.get("wyniki"):
            raise PermissionError(f"dane odłożone już otwarte {p['otwarte']} — drugie otwarcie niedozwolone")
        if p["hash"] != h or p["zwyciezca"] != winner:
            raise PermissionError("przerwane otwarcie miało inną definicję/zwycięzcę — dokończenie niedozwolone")
        return HoldoutKey(_TOKEN)
    now = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")
    con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                [f"5-holdout-{h}", now, "PORTFEL", "5-holdout",
                 json.dumps({"hash": h, "zwyciezca": winner, "otwarte": str(now), "okres": [str(HOLDOUT_START.date()),
                             str(HOLDOUT_END.date())], "wyniki": False}), 0,
                 "jedyne otwarcie danych odłożonych (etap 5 krok 4); po nim żadnych zmian reguł"])
    return HoldoutKey(_TOKEN)


def close_holdout(con, summary: dict) -> None:
    row = con.execute("SELECT run_id, params FROM runs WHERE stage='5-holdout'").fetchone()
    p = json.loads(row[1])
    p.update(wyniki=True, podsumowanie=summary)
    con.execute("UPDATE runs SET params=?, n_eval=? WHERE run_id=?", [json.dumps(p, default=float), summary.get("miesiace", 0), row[0]])


def known_weights(acc: Account, data: RuleData, D: pd.Timestamp) -> dict:
    """Bieżące wagi z cen znanych w D 22:00 (do decyzji o rebalansie; PIT)."""
    t, fx = pd.Timestamp(D) + DECISION, data.book.fx(D)
    vals = {a: p.units * data.book.known_close(a, t)[0] * fx for a, p in acc.pos.items()}
    vals = {a: (v if np.isfinite(v) else 0.0) for a, v in vals.items()}
    total = acc.cash + sum(vals.values())
    return {a: v / total for a, v in vals.items()} if total > 0 else {}


def execute_targets(acc: Account, target: dict, day: pd.Timestamp, book: PriceBook) -> None:
    """R5 wykonanie na zamknięciu `day`: najpierw sprzedaże, potem kupna; zlecenia < min_trade_frac kapitału pomijane,
    wyjście do zera zawsze. Wspólne dla backtestu i konta „system”."""
    min_frac = DEFINITION["rebalance"]["min_trade_frac"]
    total = acc.value(day, book)
    fx = book.fx(day)
    for a in list(acc.pos):                                   # najpierw sprzedaże
        v = acc.pos[a].units * book.value_on(a, day) * fx
        tv = target.get(a, 0.0) * total
        if tv <= 0:
            acc.sell(a, None, day, book)
        elif v - tv > min_frac * total:
            acc.sell(a, acc.pos[a].units * (v - tv) / v, day, book)
    for a, w in target.items():                               # potem kupna
        v = acc.pos[a].units * book.value_on(a, day) * fx if a in acc.pos else 0.0
        if w * total - v > min_frac * total:
            acc.buy(a, min(acc.cash, w * total - v), day, book)


def plan_rules(book: PriceBook, start, end) -> dict:
    """Harmonogram reguł {dzień wykonania: dzień decyzji}: ostatni dzień roboczy przed startem + końce miesięcy."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    d0 = start - pd.Timedelta(days=1)
    while d0.weekday() >= 5 or d0 in book._hol:
        d0 -= pd.Timedelta(days=1)
    plan = {book.next_bday(d0): d0}
    plan.update({book.next_bday(D): D for D in rebalance_dates(book, start, end, "M")})
    return plan


def run_rules(data: RuleData, variant: str, start, end, costs: Costs | None = None, cash: float = 1000.0,
              holdout: HoldoutKey | None = None) -> tuple[Result, pd.DataFrame]:
    """Backtest wariantu. Decyzja D (dane znane w D 22:00) -> wykonanie na zamknięciu następnego dnia roboczego USA."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end > DEV_END and not isinstance(holdout, HoldoutKey):
        raise PermissionError(f"koniec {end.date()} wchodzi w dane odłożone (> {DEV_END.date()}) — tylko przez open_holdout()")
    book = data.book
    acc = Account(cash, costs or Costs(), last_accrual=start)
    plan = plan_rules(book, start, end)
    values, log, prev_expo, n = {}, [], None, 0
    for day in pd.date_range(start, end):
        acc.accrue(day, book)
        if day in plan:
            D = plan[day]
            target, snap = target_weights(data, D, variant)
            why = rebalance_triggers(D, known_weights(acc, data, D), target, snap["exposure"], prev_expo)
            prev_expo = snap["exposure"]
            if why:
                execute_targets(acc, target, day, book)
                n += 1
            log.append({"decision": D, "exec": day, "why": "; ".join(why), "traded": bool(why),
                        **{f"w_{a}": target.get(a, 0.0) for a in DEFINITION["assets"]},
                        **{f"sigma_{a}": snap["sigma"].get(a) for a in DEFINITION["assets"]},
                        **{f"e_{a}": snap["exposure"].get(a) for a in DEFINITION["assets"]},
                        "sigma_src_WTI": snap["sigma_src"].get("WTI")})
        values[day] = acc.value(day, book)
    return _finish(variant, acc, values, n, end, book), pd.DataFrame(log)

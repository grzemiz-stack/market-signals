"""Silnik transakcji (backtest i gra na sucho): ceny w PLN, koszty, odsetki od gotówki, podatek 19% rozliczany 31.12.

Instrumenty: XAG -> ETF srebro, WTI -> ETC ropa (wycena PRZYBLIŻONA ruchem spot), BTC/ETH -> giełda krypto,
XAU -> ETF złoto (tylko punkt odniesienia). Konto w PLN, jednostki ułamkowe dozwolone.
Koszty (decyzja 2026-10-06): ETF/ETC 0% prowizji do 100 tys. EUR obrotu w miesiącu (ZAŁOŻENIE powyżej: 0,2%),
krypto 0,1% prowizji, przewalutowanie 0,5% przy każdej konwersji PLN<->USD (kupno i sprzedaż), spread 0,1%.
Gotówka: stopa referencyjna NBP − 1 pp, naliczana dziennie, po podatku Belki 19% (ZAŁOŻENIE: pobierany od razu).
Podatek 19% rozliczany 31.12: pula „kapitałowa” (ETF/ETC, zysk − strata w roku, bez przenoszenia strat) i pula krypto
(ms.tax.crypto_year: koszty roku + przeniesione). Kursy do podatku: NBP z dnia roboczego przed transakcją (ms.tax).
Brak gotówki na podatek -> proporcjonalna sprzedaż pozycji 31.12 (UPROSZCZENIE: wynik tej sprzedaży w puli kolejnego roku).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ms import tax
from ms.common import us_holidays

GAME_ASSETS = ("BTC", "ETH", "XAG", "WTI")
INSTRUMENT = {"XAG": "etf", "WTI": "etc", "XAU": "etf", "BTC": "krypto", "ETH": "krypto", "BRENT": "etc"}
INSTRUMENT_NAME = {"XAG": "ETF srebro (przybliżenie spot)", "WTI": "ETC ropa (przybliżenie spot)",
                   "XAU": "ETF złoto (przybliżenie spot)", "BTC": "BTC (giełda)", "ETH": "ETH (giełda)",
                   "BRENT": "ropa Brent (tylko obserwacja, poza grą)"}


@dataclass
class Costs:
    etf_commission_pct: float = 0.0
    etf_free_turnover_eur: float = 100_000.0
    etf_commission_above_pct: float = 0.2      # ZAŁOŻENIE powyżej darmowego limitu
    crypto_commission_pct: float = 0.1
    fx_pct: float = 0.5
    spread_pct: float = 0.1
    deposit_spread_pp: float = 1.0
    belka: float = 0.19

    @classmethod
    def zero(cls) -> "Costs":
        return cls(0.0, 1e18, 0.0, 0.0, 0.0, 0.0, 1.0, 0.19)


# --------------------------------------------------------------------------- ceny


class PriceBook:
    """Zamknięcia USD (ms.prices, z known_at), USD/PLN i EUR/PLN (NBP), stopa referencyjna NBP."""

    def __init__(self, mcon, assets=(*GAME_ASSETS, "XAU"), frames: dict | None = None):
        from ms.prices import price_frame

        self.frames = frames or {a: price_frame(mcon, a)[["value", "known_at"]] for a in assets}

        def series(sid):
            df = mcon.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id=? ORDER BY 1", [sid]).df()
            return pd.Series(df["value"].to_numpy(), index=pd.to_datetime(df["observed_at"]).astype("datetime64[ns]"))

        self.usdpln, self.eurpln, self.ref = series("NBP.USDPLN"), series("NBP.EURPLN"), series("NBP.REF")
        self._hol = {pd.Timestamp(d) for d in us_holidays()}

    @staticmethod
    def _last(s: pd.Series, d, strict: bool = False) -> float:
        """Ostatnia wartość z indeksem <= d (strict: < d). Wyszukiwanie binarne."""
        if s.empty:
            return np.nan
        t = pd.Timestamp(d) - (pd.Timedelta(1, "ns") if strict else pd.Timedelta(0))
        i = s.index.searchsorted(t, side="right") - 1
        return float(s.iloc[i]) if i >= 0 else np.nan

    def fx(self, d) -> float:
        return self._last(self.usdpln, d)

    def fx_tax(self, d) -> float:
        """NBP z ostatniego dnia roboczego PRZED d (zasada podatkowa, jak ms.tax.nbp_rate_for_tax)."""
        return self._last(self.usdpln, d, strict=True)

    def eur(self, d) -> float:
        return self._last(self.eurpln, d)

    def deposit_rate(self, d, c: Costs) -> float:
        return max(0.0, self._last(self.ref, d) - c.deposit_spread_pp) / 100

    def next_bday(self, d) -> pd.Timestamp:
        d = pd.Timestamp(d).normalize() + pd.Timedelta(days=1)
        while d.weekday() >= 5 or d in self._hol:
            d += pd.Timedelta(days=1)
        return d

    def exec_date(self, asset: str, d) -> pd.Timestamp:
        """Zlecenie z dnia D: krypto -> zamknięcie D+1; ETF/ETC -> zamknięcie następnego dnia roboczego USA."""
        if INSTRUMENT[asset] == "krypto":
            return pd.Timestamp(d).normalize() + pd.Timedelta(days=1)
        return self.next_bday(d)

    def close_on(self, asset: str, d) -> tuple[float, pd.Timestamp]:
        """Zamknięcie z dnia d, a gdy go nie ma (święto na giełdzie) — pierwsze kolejne. (cena USD, data)."""
        f = self.frames[asset]["value"]
        s = f[(f.index >= pd.Timestamp(d).normalize()) & (f > 0)]  # ETC nie handluje po cenie <= 0 (WTI 2020-04-20)
        return (float(s.iloc[0]), s.index[0]) if len(s) else (np.nan, pd.NaT)

    def has_close(self, asset: str, d) -> bool:
        """Czy jest już zamknięcie z dnia d albo późniejsze (inaczej transakcji w d nie da się jeszcze wykonać)."""
        return not pd.isna(self.close_on(asset, d)[1])

    def last_close_date(self, asset: str, d) -> pd.Timestamp:
        """d, gdy jest zamknięcie z d lub później; inaczej ostatni dzień z zamknięciem > 0 (likwidacja, podatek 31.12)."""
        if self.has_close(asset, d):
            return pd.Timestamp(d)
        f = self.frames[asset]["value"]
        return f[(f.index <= pd.Timestamp(d)) & (f > 0)].index.max()

    def known_close(self, asset: str, t) -> tuple[float, pd.Timestamp]:
        """Ostatnie zamknięcie znane w chwili t (known_at <= t) — do decyzji."""
        f = self.frames[asset]
        f = f[f["known_at"] <= pd.Timestamp(t)]
        return (float(f["value"].iloc[-1]), f.index[-1]) if len(f) else (np.nan, pd.NaT)

    def known_close_before(self, asset: str, t, date_limit) -> float:
        """Zamknięcie z dnia <= date_limit, znane w t."""
        f = self.frames[asset]
        f = f[(f["known_at"] <= pd.Timestamp(t)) & (f.index <= pd.Timestamp(date_limit))]
        return float(f["value"].iloc[-1]) if len(f) else np.nan

    def value_on(self, asset: str, d) -> float:
        """Wycena dzienna: ostatnie zamknięcie z dnia <= d (bez wymogu known_at — do krzywej kapitału po fakcie);
        obcięte na 0 (wycena ETC ropy przybliżona spotem; spot WTI był ujemny 2020-04-20)."""
        return max(0.0, self._last(self.frames[asset]["value"], d))


def _require_price(asset: str, d, price: float, price_date) -> None:
    """Transakcja bez ceny = błąd, nigdy cicho (wcześniej: zabrana gotówka i NaN jednostek -> wartość konta NaN)."""
    if pd.isna(price_date) or not np.isfinite(price):
        raise ValueError(f"brak zamknięcia {asset} z dnia {pd.Timestamp(d).date()} ani późniejszego — transakcja niemożliwa")


# --------------------------------------------------------------------------- konto


@dataclass
class Position:
    units: float = 0.0
    cost_pln: float = 0.0       # ekonomiczny koszt (z kosztami transakcji)
    cost_tax_pln: float = 0.0   # koszt podatkowy (USD × NBP z dnia przed + koszty)


@dataclass
class Trade:
    date: pd.Timestamp
    side: str
    asset: str
    units: float
    price_usd: float
    fx: float
    value_pln: float
    costs_pln: float


@dataclass
class Account:
    cash: float
    costs: Costs = field(default_factory=Costs)
    pos: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)
    capital_pnl: dict = field(default_factory=dict)       # rok -> zysk/strata ETF/ETC (podatkowo)
    crypto_proceeds: dict = field(default_factory=dict)   # rok -> przychód
    crypto_costs: dict = field(default_factory=dict)      # rok -> koszty nabycia
    crypto_carry: float = 0.0
    costs_total: float = 0.0
    tax_total: float = 0.0
    interest_total: float = 0.0
    turnover_eur: dict = field(default_factory=dict)      # (rok, miesiąc) -> obrót EUR ETF/ETC
    last_accrual: pd.Timestamp | None = None

    # -- koszty jednej transakcji o wartości v PLN
    def _cost(self, asset: str, v: float, d: pd.Timestamp, book: PriceBook) -> float:
        c = self.costs
        pct = c.spread_pct + c.fx_pct
        if INSTRUMENT[asset] == "krypto":
            pct += c.crypto_commission_pct
        else:
            key = (d.year, d.month)
            eur = v / book.eur(d)
            used = self.turnover_eur.get(key, 0.0)
            free = max(0.0, c.etf_free_turnover_eur - used)
            self.turnover_eur[key] = used + eur
            paid_part = max(0.0, eur - free) / eur if eur > 0 else 0.0
            pct += c.etf_commission_pct + paid_part * c.etf_commission_above_pct
        return v * pct / 100

    def accrue(self, to: pd.Timestamp, book: PriceBook) -> None:
        """Odsetki dzienne od dodatniej gotówki do dnia `to` (bez niego), po podatku Belki."""
        to = pd.Timestamp(to).normalize()
        d = self.last_accrual or to
        while d < to:
            if self.cash > 0:
                r = book.deposit_rate(d, self.costs) * (1 - self.costs.belka) / 365
                gain = self.cash * r
                self.cash += gain
                self.interest_total += gain
            d += pd.Timedelta(days=1)
            if d.month == 1 and d.day == 1:
                self.settle_tax(d.year - 1, d - pd.Timedelta(days=1), book)
        self.last_accrual = to

    def buy(self, asset: str, amount_pln: float, d, book: PriceBook) -> Trade | None:
        d = pd.Timestamp(d).normalize()
        amount_pln = min(amount_pln, self.cash)
        if amount_pln <= 0:
            return None
        price, pd_ = book.close_on(asset, d)
        _require_price(asset, d, price, pd_)
        fx = book.fx(pd_)
        cost = self._cost(asset, amount_pln, pd_, book)
        units = (amount_pln - cost) / (price * fx)
        self.cash -= amount_pln
        p = self.pos.setdefault(asset, Position())
        p.units += units
        p.cost_pln += amount_pln
        tax_cost = (amount_pln - cost) / fx * book.fx_tax(pd_) + cost
        p.cost_tax_pln += tax_cost
        if INSTRUMENT[asset] == "krypto":
            self.crypto_costs[pd_.year] = self.crypto_costs.get(pd_.year, 0.0) + tax_cost
        self.costs_total += cost
        t = Trade(pd_, "buy", asset, units, price, fx, amount_pln, cost)
        self.trades.append(t)
        return t

    def sell(self, asset: str, units: float | None, d, book: PriceBook, pool_year: int | None = None) -> Trade | None:
        d = pd.Timestamp(d).normalize()
        p = self.pos.get(asset)
        if p is None or p.units <= 0:
            return None
        units = p.units if units is None else min(units, p.units)
        price, pd_ = book.close_on(asset, d)
        _require_price(asset, d, price, pd_)
        fx = book.fx(pd_)
        gross = units * price * fx
        cost = self._cost(asset, gross, pd_, book)
        proceeds = gross - cost
        frac = units / p.units
        proceeds_tax = units * price * book.fx_tax(pd_) - cost
        y = pool_year or pd_.year
        if INSTRUMENT[asset] == "krypto":
            self.crypto_proceeds[y] = self.crypto_proceeds.get(y, 0.0) + proceeds_tax
        else:
            self.capital_pnl[y] = self.capital_pnl.get(y, 0.0) + proceeds_tax - frac * p.cost_tax_pln
        p.cost_pln *= 1 - frac
        p.cost_tax_pln *= 1 - frac
        p.units -= units
        if p.units <= 1e-12:
            del self.pos[asset]
        self.cash += proceeds
        self.costs_total += cost
        t = Trade(pd_, "sell", asset, units, price, fx, proceeds, cost)
        self.trades.append(t)
        return t

    def tax_due(self, year: int) -> tuple[float, float]:
        """(podatek za rok, nowa nadwyżka kosztów krypto) — bez zmiany stanu."""
        cap = max(0.0, self.capital_pnl.get(year, 0.0)) * tax.RATE_CAPITAL
        _, crypto_tax, carry = tax.crypto_year(self.crypto_proceeds.get(year, 0.0), self.crypto_costs.get(year, 0.0),
                                               self.crypto_carry)
        return cap + crypto_tax, carry

    def settle_tax(self, year: int, d: pd.Timestamp, book: PriceBook) -> float:
        due, carry = self.tax_due(year)
        self.crypto_carry = carry
        if due > self.cash:  # brak gotówki: ten sam ułamek każdej pozycji (+1% na koszty); wynik do puli kolejnego roku
            total = self.holdings_value(d, book)
            f = min(1.0, (due - self.cash) / total * 1.01) if total > 0 else 0.0
            for a in list(self.pos):
                self.sell(a, self.pos[a].units * f, book.last_close_date(a, d), book, pool_year=year + 1)
        self.cash -= due
        self.tax_total += due
        return due

    def holdings_value(self, d, book: PriceBook) -> float:
        return sum(p.units * book.value_on(a, d) * book.fx(d) for a, p in self.pos.items())

    def value(self, d, book: PriceBook) -> float:
        return self.cash + self.holdings_value(d, book)

    def liquidation_value(self, d, book: PriceBook) -> tuple[float, float, float]:
        """Wartość po sprzedaży wszystkiego w d i rozliczeniu podatku za bieżący rok: (na rękę, koszty, podatek)."""
        import copy

        acc = copy.deepcopy(self)
        c0 = acc.costs_total
        for a in list(acc.pos):
            acc.sell(a, None, book.last_close_date(a, d), book)
        due, _ = acc.tax_due(pd.Timestamp(d).year)
        return acc.cash - due, acc.costs_total - c0, due

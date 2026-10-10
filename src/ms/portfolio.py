"""Portfel (PLN): pozycje, wycena, rozbicie wyniku cena/kurs, sprzedaż hipotetyczna po podatku, koszt zamiany,
symulacje. Pozycje w OSOBNEJ bazie (data/portfolio.duckdb, dane osobiste) — market.duckdb tylko do odczytu.

Model wyceny: każda pozycja = u jednostek „bazowych” (uncje złota/srebra, monety krypto) × spot USD × USD/PLN (NBP).
- sztabka/moneta: u = ilość × oz_per_unit; „na rękę” = rynkowa × (1 − dyskonto skupu, domyślnie 3%).
- ETF: brak notowań ETF w bazie -> PRZYBLIŻENIE: u = (kwota zakupu w PLN) / (spot × USD/PLN w dniu zakupu), czyli
  „uncje kupione za te pieniądze”; ETF śledzi spot (bez TER, błędu odwzorowania i premii/dyskonta do NAV).
- krypto: u = ilość monet; spot = Binance USDT (≈ USD).
Podatki: wyłącznie ms.tax (do potwierdzenia u doradcy).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ms import tax
from ms.db import ROOT

PORTFOLIO_DB = ROOT / "data" / "portfolio.duckdb"
EXAMPLE_DB = ROOT / "data" / "portfolio_example.duckdb"
FORMS = ("sztabka", "moneta", "etf", "krypto_gielda", "krypto_portfel")
UNITS = ("oz", "szt", "jednostki")
DEFAULT_DISCOUNT_PCT = 3.0
# ZAŁOŻENIA kosztów wyjścia/wejścia (konfigurowalne argumentami funkcji)
EXIT_FEE_PCT = {"sztabka": 0.0, "moneta": 0.0, "etf": 0.29, "krypto_gielda": 0.2, "krypto_portfel": 0.3}
ENTRY_PREMIUM_PCT = {"sztabka": 3.0, "moneta": 5.0, "etf": 0.29, "krypto_gielda": 0.2, "krypto_portfel": 0.3}
SCENARIOS = {"2008-09…2008-11 (kryzys finansowy)": ("2008-09-01", "2008-11-30"),
             "2013-04 (krach złota)": ("2013-04-01", "2013-04-30"),
             "2020-03 (COVID)": ("2020-03-01", "2020-03-31"),
             "2022-03…2022-10 (podwyżki stóp)": ("2022-03-01", "2022-10-31")}

SCHEMA = f"""
CREATE SEQUENCE IF NOT EXISTS pos_id START 1;
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id INTEGER PRIMARY KEY DEFAULT nextval('pos_id'),
    asset VARCHAR NOT NULL, form VARCHAR NOT NULL CHECK (form IN {FORMS}), ticker VARCHAR,
    quantity DOUBLE NOT NULL CHECK (quantity > 0), unit VARCHAR NOT NULL CHECK (unit IN {UNITS}),
    oz_per_unit DOUBLE NOT NULL DEFAULT 1.0,
    buy_price DOUBLE NOT NULL CHECK (buy_price > 0), currency VARCHAR NOT NULL, buy_date DATE NOT NULL,
    buy_fee DOUBLE NOT NULL DEFAULT 0, premium_pct DOUBLE, storage_cost_pln_year DOUBLE NOT NULL DEFAULT 0,
    buyback_discount_pct DOUBLE NOT NULL DEFAULT {DEFAULT_DISCOUNT_PCT}, note VARCHAR,
    sell_date DATE, sell_price DOUBLE, sell_currency VARCHAR, sell_fee DOUBLE, sell_discount_pct DOUBLE,
    created_at TIMESTAMP NOT NULL DEFAULT now()::TIMESTAMP);
"""


def connect(path: Path | str = PORTFOLIO_DB):
    import duckdb

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def add(pcon, **kw) -> int:
    if kw.get("form") in tax.PHYSICAL and kw.get("unit") == "jednostki":
        raise ValueError("złoto fizyczne: unit = oz albo szt")
    cols = [k for k, v in kw.items() if v is not None]
    q = f"INSERT INTO portfolio_positions ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) RETURNING id"
    return pcon.execute(q, [kw[c] for c in cols]).fetchone()[0]


def close(pcon, pos_id: int, sell_date, sell_price: float, sell_currency: str, sell_fee: float = 0.0,
          sell_discount_pct: float | None = None) -> None:
    n = pcon.execute("""UPDATE portfolio_positions SET sell_date=?, sell_price=?, sell_currency=?, sell_fee=?,
                        sell_discount_pct=? WHERE id=? AND sell_date IS NULL RETURNING id""",
                     [pd.Timestamp(sell_date).date(), sell_price, sell_currency, sell_fee, sell_discount_pct, pos_id]).fetchall()
    if not n:
        raise LookupError(f"brak otwartej pozycji {pos_id}")


def positions(pcon, open_only: bool = True) -> pd.DataFrame:
    q = "SELECT * FROM portfolio_positions" + (" WHERE sell_date IS NULL" if open_only else "") + " ORDER BY id"
    return pcon.execute(q).df()


# --------------------------------------------------------------------------- dane rynkowe


class Market:
    """Spot USD i USD/PLN z market.duckdb (as_of teraz), z pamięcią podręczną."""

    def __init__(self, mcon):
        from ms.prices import price_frame

        self.mcon = mcon
        self._pf = price_frame
        self._spot: dict[str, pd.Series] = {}
        fx = mcon.execute("""SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id='NBP.USDPLN'
                             ORDER BY observed_at""").df()
        self.usdpln = pd.Series(fx["value"].to_numpy(), index=pd.to_datetime(fx["observed_at"]).astype("datetime64[ns]"))

    def spot_series(self, asset: str) -> pd.Series:
        if asset not in self._spot:
            self._spot[asset] = self._pf(self.mcon, asset)["value"]
        return self._spot[asset]

    @staticmethod
    def _at(s: pd.Series, d) -> tuple[float, pd.Timestamp]:
        s = s[s.index <= pd.Timestamp(d)]
        if s.empty:
            return np.nan, pd.NaT
        return float(s.iloc[-1]), s.index[-1]

    def spot(self, asset: str, d) -> float:
        return self._at(self.spot_series(asset), d)[0]

    def fx(self, d) -> float:
        """Rynkowy USD/PLN: ostatnia tabela NBP <= d (do wyceny; do podatku: tax.nbp_rate_for_tax)."""
        return self._at(self.usdpln, d)[0]


# --------------------------------------------------------------------------- wycena i rozbicie


@dataclass
class Valuation:
    id: int
    asset: str
    form: str
    units: float              # uncje / monety
    cost_pln: float           # koszt nabycia (podatkowy kurs NBP z dnia roboczego przed zakupem) z prowizją
    market0_pln: float        # wartość rynkowa w dniu zakupu (spot × kurs)
    market_pln: float         # wartość rynkowa dziś
    net_pln: float            # „na rękę” przed podatkiem (dyskonto skupu / prowizja wyjścia)
    price_effect: float       # zmiana ceny w USD przy kursie z dnia zakupu
    fx_effect: float          # zmiana USD/PLN przy dzisiejszej cenie
    entry_costs: float        # (ujemne) premia i prowizja przy zakupie = market0 − koszt
    exit_costs: float         # (ujemne) dyskonto skupu / prowizja wyjścia = net − market
    storage: float            # (ujemne) koszt przechowania od zakupu
    result_pln: float         # net − koszt + storage = suma składników
    tax_pln: float
    after_tax_pln: float      # wynik na rękę po podatku przy sprzedaży dziś
    tax_rule: str
    exempt_from: pd.Timestamp | None


def units(row, m: Market, mcon) -> float:
    if row["form"] in tax.PHYSICAL:
        return row["quantity"] * (row["oz_per_unit"] if row["unit"] == "szt" else 1.0)
    if row["form"] == "etf":
        return cost_pln(row, mcon, include_fee=False) / (m.spot(row["asset"], row["buy_date"]) * m.fx(row["buy_date"]))
    return float(row["quantity"])


def cost_pln(row, mcon, include_fee: bool = True) -> float:
    rate, _ = tax.nbp_rate_for_tax(mcon, row["currency"], row["buy_date"])
    return (row["quantity"] * row["buy_price"] + (row["buy_fee"] if include_fee else 0.0)) * rate


def value(row, m: Market, mcon, d, exit_fee_pct: float | None = None, crypto_cost_pln: float | None = None) -> Valuation:
    """crypto_cost_pln: koszt z puli krypto (crypto_pool_cost) — podatek od sprzedaży tej pozycji jest krańcowy."""
    d = pd.Timestamp(d)
    u = units(row, m, mcon)
    s0, s1 = m.spot(row["asset"], row["buy_date"]), m.spot(row["asset"], d)
    f0, f1 = m.fx(row["buy_date"]), m.fx(d)
    m0, m1 = u * s0 * f0, u * s1 * f1
    price_eff = u * (s1 - s0) * f0
    fx_eff = u * s1 * (f1 - f0)
    if row["form"] in tax.PHYSICAL:
        net = m1 * (1 - row["buyback_discount_pct"] / 100)
    else:
        fee = EXIT_FEE_PCT[row["form"]] if exit_fee_pct is None else exit_fee_pct
        net = m1 * (1 - fee / 100)
    c = cost_pln(row, mcon)
    years = max(0.0, (d - pd.Timestamp(row["buy_date"])).days / 365.25)
    storage = -years * row["storage_cost_pln_year"]
    # podatek: przychód w USD przeliczony kursem NBP z dnia roboczego przed sprzedażą; złoto fizyczne sprzedaje się za PLN
    if row["form"] in tax.PHYSICAL:
        proceeds_tax = net
    else:
        rate_tax, _ = tax.nbp_rate_for_tax(mcon, "USD", d)
        proceeds_tax = net * rate_tax / f1
    tax_cost = c if row["form"] not in tax.CRYPTO or crypto_cost_pln is None else crypto_cost_pln
    t = tax.tax_on_sale(row["form"], proceeds_tax, tax_cost, row["buy_date"], d)
    result = net - c + storage
    return Valuation(int(row["id"]), row["asset"], row["form"], u, c, m0, m1, net, price_eff, fx_eff,
                     m0 - c, net - m1, storage, result, t.tax_pln, result - t.tax_pln, t.rule,
                     tax.gold_exempt_from(row["buy_date"]) if row["form"] in tax.PHYSICAL else None)


def crypto_pool_cost(pcon, mcon, d) -> float:
    """Koszt „z puli” dla dodatkowej sprzedaży krypto w roku d: max(0, koszty roku + nadwyżka z lat poprzednich
    − przychody już zrealizowane w roku). Koszty = wydatki na nabycie w roku (także pozycji wciąż trzymanych)."""
    allp = positions(pcon, open_only=False)
    cr = allp[allp["form"].isin(tax.CRYPTO)]
    if cr.empty:
        return 0.0
    year = pd.Timestamp(d).year
    buys = {}
    for _, r in cr.iterrows():
        buys.setdefault(pd.Timestamp(r["buy_date"]).year, 0.0)
        buys[pd.Timestamp(r["buy_date"]).year] += cost_pln(r, mcon)
    sales = {}
    for _, r in cr[cr["sell_date"].notna()].iterrows():
        y = pd.Timestamp(r["sell_date"]).year
        rate, _ = tax.nbp_rate_for_tax(mcon, r["sell_currency"], r["sell_date"])
        sales[y] = sales.get(y, 0.0) + (r["quantity"] * r["sell_price"] - (r["sell_fee"] or 0.0)) * rate
    carry = 0.0
    for y in range(min(buys), year):
        _, _, carry = tax.crypto_year(sales.get(y, 0.0), buys.get(y, 0.0), carry)
    return max(0.0, buys.get(year, 0.0) + carry - sales.get(year, 0.0))


def valuate(pcon, mcon, d) -> pd.DataFrame:
    m = Market(mcon)
    pool = crypto_pool_cost(pcon, mcon, d)
    return pd.DataFrame([value(r, m, mcon, d, crypto_cost_pln=pool).__dict__ for _, r in positions(pcon).iterrows()])


# --------------------------------------------------------------------------- koszt zamiany A -> B


@dataclass
class SwapCost:
    value_pln: float
    exit_costs: float
    tax: float
    entry_costs: float
    total: float
    threshold_pct: float
    text: str


def swap_cost(pcon, mcon, pos_id: int, target_form: str, d, target_premium_pct: float | None = None) -> SwapCost:
    """Koszt zamiany pozycji A na formę B dziś (PLN, >= 0) i próg: B musi zyskać względem A ponad X%,
    żeby zamiana się opłaciła (przy założeniu, że A trzymane dalej nie ponosi teraz żadnych kosztów)."""
    row = positions(pcon).set_index("id").loc[pos_id]
    row = row.copy()
    row["id"] = pos_id
    v = value(row, Market(mcon), mcon, d, crypto_cost_pln=crypto_pool_cost(pcon, mcon, d))
    exit_c = max(0.0, v.market_pln - v.net_pln)
    after_exit_tax = v.net_pln - v.tax_pln
    p = (ENTRY_PREMIUM_PCT[target_form] if target_premium_pct is None else target_premium_pct) / 100
    entry_c = max(0.0, after_exit_tax * p / (1 + p))
    total = exit_c + max(0.0, v.tax_pln) + entry_c
    invested = v.market_pln - total
    x = (v.market_pln / invested - 1) * 100 if invested > 0 else np.inf
    def pln(a: float) -> str:
        return f"{a + 0.0:,.0f}".replace(",", " ")
    text = (f"Zamiana {row['form']} {row['asset']} (id {pos_id}) -> {target_form}: koszt {pln(total)} PLN "
            f"(wyjście {pln(exit_c)}, podatek {pln(v.tax_pln)}, wejście {pln(entry_c)}). "
            f"Zamiana opłaca się, jeśli B zyska względem A ponad {x:.2f}%.".replace(f"{x:.2f}%", f"{x:.2f}%".replace(".", ",")))
    return SwapCost(v.market_pln, exit_c, v.tax_pln, entry_c, total, x, text)


# --------------------------------------------------------------------------- symulacje


def shock(val: pd.DataFrame, rows: pd.DataFrame, shocks: dict[str, float], fx_pct: float = 0.0) -> pd.DataFrame:
    """Szoki ręczne (% zmiany ceny USD per aktywo, % zmiany USD/PLN). Wartość „na rękę” przed podatkiem."""
    out = val[["id", "asset", "form", "net_pln"]].copy()
    mult = np.array([(1 + shocks.get(a, 0.0) / 100) * (1 + fx_pct / 100) for a in out["asset"]])
    out["net_after"] = out["net_pln"] * mult
    out["change"] = out["net_after"] - out["net_pln"]
    return out


def historical_moves(m: Market, start, end, assets) -> tuple[dict[str, float | None], float]:
    """Łączne ruchy (%) aktywów i USD/PLN w oknie [start, end]: poziom na koniec / poziom przed startem."""
    s, e = pd.Timestamp(start) - pd.Timedelta(days=1), pd.Timestamp(end)
    moves = {}
    for a in assets:
        ser = m.spot_series(a)
        if ser.index.min() > s:
            moves[a] = None  # brak historii (np. BTC w 2008)
            continue
        moves[a] = (m._at(ser, e)[0] / m._at(ser, s)[0] - 1) * 100
    fx = (m._at(m.usdpln, e)[0] / m._at(m.usdpln, s)[0] - 1) * 100
    return moves, fx


def concentration(m: Market, val: pd.DataFrame, d, days: int = 365) -> tuple[pd.DataFrame, pd.Series]:
    """Korelacja dziennych zwrotów w PLN między pozycjami (1 rok) i udział w ryzyku (wariancji) portfela."""
    d = pd.Timestamp(d)
    dates = m.usdpln.index[(m.usdpln.index > d - pd.Timedelta(days=days)) & (m.usdpln.index <= d)]
    lv = {}
    for _, r in val.iterrows():
        s = m.spot_series(r["asset"]).reindex(dates, method="ffill")
        lv[f"{r['id']}:{r['form']} {r['asset']}"] = np.log(s * m.usdpln.reindex(dates))
    rets = pd.DataFrame(lv).diff().dropna()
    corr = rets.corr()
    w = val["net_pln"].to_numpy() / val["net_pln"].sum()
    cov = rets.cov().to_numpy()
    var = float(w @ cov @ w)
    contrib = pd.Series(w * (cov @ w) / var if var > 0 else np.nan, index=rets.columns)
    return corr, contrib

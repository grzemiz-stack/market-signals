"""Cechy dzienne (features_daily): jedna chwila decyzji na dzień, D 22:00 UTC.

Dwa tory danych (oba tylko z known_at <= D 22:00, wektorowo dla wszystkich dni naraz):
- PANEL: db.panel_asof — ostatnia obserwacja w ostatniej wersji znanej w t. Poziomy i zmiany
  „panel(D) − panel(D − k dni decyzji)”.
- OKNO: szereg pierwszych publikacji, statystyka okna dostępna od cummax(known_at) okna, dopasowana do D (pit.align).
z-score: kroczący 3 lata na kalendarzu aktywa (okno kończy się w D), min 1 rok, inaczej NaN.
Etykiety (przyszłość) są w osobnej tabeli labels — tu ich nie ma.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ms import db
from ms.pit import CRYPTO_ASSETS, align, available_from, decision_days, decision_times, first_release, panel
from ms.prices import price_frame

log = logging.getLogger("features")

GROUPS = ("koszt_alternatywny", "ryzyko", "momentum_pozycje", "ropa_podaz", "plynnosc", "krzywa")
SHORT_HISTORY_GROUPS = ("krzywa",)  # krzywa ropy od 2026-10: krótka historia, poza analogiami
START = {"bday": pd.Timestamp("1985-01-01"), "crypto": pd.Timestamp("2017-08-17")}

COT = {  # aktywo -> (raport, rynek, long, short, OI)
    "XAU": ("disaggregated", "GOLD", "m_money_positions_long_all", "m_money_positions_short_all", "open_interest_all"),
    "XAG": ("disaggregated", "SILVER", "m_money_positions_long_all", "m_money_positions_short_all", "open_interest_all"),
    "WTI": ("disaggregated", "WTI", "m_money_positions_long_all", "m_money_positions_short_all", "open_interest_all"),
    "BRENT": ("disaggregated", "BRENT", "m_money_positions_long_all", "m_money_positions_short_all", "open_interest_all"),
    "BTC": ("legacy", "BTC", "noncommercial_positions_long_all", "noncommercial_positions_short_all", "open_interest_all"),
    "ETH": ("legacy", "ETH", "noncommercial_positions_long_all", "noncommercial_positions_short_all", "open_interest_all"),
}
OIL = {"WTI": ("EIA.WCESTUS1", "EIA.CUSHING", "CURVE.CL"), "BRENT": ("EIA.WCESTUS1", "EIA.CUSHING", "CURVE.BZ")}
CRYPTO_SYM = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

PANEL_SERIES = ["FRED.DFII10", "FRED.DGS2", "FRED.EFFR", "FRED.T10YIE", "FRED.DTWEXBGS",
                "FRED.DEXUSEU", "FRED.DEXJPUS", "FRED.DEXCHUS", "FRED.DEXUSAL",
                "FRED.VIXCLS", "FRED.GVZCLS", "FRED.OVXCLS", "FRED.NFCI", "FRED.STLFSI4",
                "FRED.WALCL", "FRED.WTREGEN", "FRED.RRPONTSYD", "DVOL.BTC.close", "DVOL.ETH.close",
                "FNG.crypto", "EIA.WPULEUS3",
                "CURVE.CL.M1", "CURVE.CL.M6", "CURVE.BZ.M1", "CURVE.BZ.M6",
                *[f"COT.{r}.{m}.{c}" for r, m, *cols in COT.values() for c in cols]]


# --------------------------------------------------------------------------- tor OKNO


def window_feature(fr: pd.DataFrame, fn, times: pd.DatetimeIndex) -> pd.Series:
    """fr: observed_at, value, known_at (jedna seria, pierwsze publikacje). fn: Series(value) -> Series (po obserwacjach)."""
    fr = fr.sort_values("observed_at")
    stat = fn(fr["value"].reset_index(drop=True))
    return align(stat, available_from(fr["known_at"].reset_index(drop=True)), times)


def price_features(pf: pd.DataFrame, times: pd.DatetimeIndex, ann: float) -> dict[str, pd.Series]:
    lr = pf["logret"].reset_index(drop=True)
    avail = available_from(pf["known_at"].reset_index(drop=True))
    out = {}
    for k in (5, 20, 60):
        out[f"ret_{k}d"] = align(lr.rolling(k, min_periods=k).sum(), avail, times)
    for k in (20, 60):
        out[f"rv_{k}d"] = align(lr.rolling(k, min_periods=k).std() * np.sqrt(ann), avail, times)
    return out


def seasonal_deviation(fr: pd.DataFrame, years: int = 5, min_years: int = 3) -> pd.Series:
    """Tygodniowe zapasy: v / średnia z tego samego tygodnia (±4 dni) w poprzednich `years` latach − 1."""
    s = fr.set_index("observed_at")["value"].sort_index()
    base = pd.DataFrame({"d": s.index})
    hist = []
    for n in range(1, years + 1):
        target = pd.DataFrame({"d": s.index, "t": s.index - pd.DateOffset(years=n)})
        m = pd.merge_asof(target.sort_values("t"), pd.DataFrame({"t": s.index, "v": s.values}),
                          on="t", direction="nearest", tolerance=pd.Timedelta(days=4)).sort_values("d")
        hist.append(m["v"].values)
    h = np.vstack(hist)
    cnt = np.sum(~np.isnan(h), axis=0)
    with np.errstate(all="ignore"):
        tot = np.nansum(h, axis=0)
    mean = np.where(cnt >= min_years, tot / np.maximum(cnt, 1), np.nan)
    return pd.Series(s.values / mean - 1, index=base.index)


# --------------------------------------------------------------------------- budowa


def asset_calendar(asset: str, end) -> pd.DatetimeIndex:
    kind = "crypto" if asset in CRYPTO_ASSETS else "bday"
    return decision_days(asset, START[kind], end)


def compute_asset(con, asset: str, end, pnl: pd.DataFrame | None = None, fr_cache: dict | None = None) -> pd.DataFrame:
    """Cechy surowe dla aktywa na wszystkich dniach decyzji do `end` (włącznie). Kolumny: feature -> wartości."""
    days = asset_calendar(asset, end)
    times = decision_times(days)
    if pnl is None:
        pnl = panel(con, PANEL_SERIES, times)
    else:
        pnl = pnl.reindex(times)
    fr_cache = fr_cache if fr_cache is not None else {}

    def fr(sid):
        if sid not in fr_cache:
            fr_cache[sid] = first_release(con, [sid])
        return fr_cache[sid]

    lag = lambda s, k=20: s - s.shift(k)  # noqa: E731  (zmiana względem k dni decyzji wcześniej)
    P = lambda sid: pnl[sid] if sid in pnl else pd.Series(np.nan, index=times)  # noqa: E731
    F: dict[str, tuple[str, pd.Series]] = {}

    # koszt alternatywny
    F["dfii10"] = ("koszt_alternatywny", P("FRED.DFII10"))
    F["dfii10_chg20"] = ("koszt_alternatywny", lag(P("FRED.DFII10")))
    F["dgs2_minus_effr"] = ("koszt_alternatywny", P("FRED.DGS2") - P("FRED.EFFR"))
    usd = pd.concat([-np.log(P("FRED.DEXUSEU")), np.log(P("FRED.DEXJPUS")),
                     np.log(P("FRED.DEXCHUS")), -np.log(P("FRED.DEXUSAL"))], axis=1).mean(axis=1, skipna=False)
    F["usd_gram_basket_ret20"] = ("koszt_alternatywny", lag(usd))
    F["dtwexbgs_ret20"] = ("koszt_alternatywny", lag(np.log(P("FRED.DTWEXBGS"))))
    F["t10yie"] = ("koszt_alternatywny", P("FRED.T10YIE"))

    # ryzyko
    for sid, name in (("FRED.VIXCLS", "vix"), ("FRED.GVZCLS", "gvz"), ("FRED.OVXCLS", "ovx"),
                      ("FRED.NFCI", "nfci"), ("FRED.STLFSI4", "stlfsi4")):
        F[name] = ("ryzyko", P(sid))
    if asset in CRYPTO_ASSETS:
        F["dvol"] = ("ryzyko", P(f"DVOL.{asset}.close"))
    F["gpr_ma7"] = ("ryzyko", window_feature(fr("GPR.GPRD"), lambda v: v.rolling(7, min_periods=7).mean(), times))
    F["epu_ma7"] = ("ryzyko", window_feature(fr("FRED.USEPUINDXD"), lambda v: v.rolling(7, min_periods=7).mean(), times))

    # momentum i pozycje
    pf = price_frame(con, asset)
    for k, v in price_features(pf, times, 365 if asset in CRYPTO_ASSETS else 252).items():
        F[k] = ("momentum_pozycje", v)
    rep, mkt, lng, sht, oi = COT[asset]
    F["cot_net_oi"] = ("momentum_pozycje",
                       (P(f"COT.{rep}.{mkt}.{lng}") - P(f"COT.{rep}.{mkt}.{sht}")) / P(f"COT.{rep}.{mkt}.{oi}"))
    if asset in CRYPTO_ASSETS:
        sym = CRYPTO_SYM[asset]
        F["funding_ma7d"] = ("momentum_pozycje", window_feature(
            fr(f"{sym}.funding.binance"), lambda v: v.rolling(21, min_periods=21).mean(), times))
        oi5 = fr(f"{sym}.sum_open_interest")
        oid = oi5.assign(day=oi5["observed_at"].dt.normalize()).groupby("day").agg(
            value=("value", "last"), known_at=("known_at", "max"), observed_at=("observed_at", "max")).reset_index(drop=True)
        F["oi_chg7d"] = ("momentum_pozycje", window_feature(oid, lambda v: np.log(v / v.shift(7)), times))
        F["fear_greed"] = ("momentum_pozycje", P("FNG.crypto"))

    # ropa: podaż i krzywa
    if asset in OIL:
        stocks, cushing, curve = OIL[asset]
        for sid, name in ((stocks, "crude_stocks_vs_5y"), (cushing, "cushing_vs_5y")):
            f = fr(sid).sort_values("observed_at").reset_index(drop=True)
            F[name] = ("ropa_podaz", align(seasonal_deviation(f), available_from(f["known_at"]), times))
        F["refinery_util"] = ("ropa_podaz", P("EIA.WPULEUS3"))
        F["curve_m6_m1"] = ("krzywa", P(f"{curve}.M6") / P(f"{curve}.M1") - 1)

    # płynność (WALCL, WTREGEN: mln USD; RRPONTSYD: mld USD -> ×1000; wynik w mld)
    net = (P("FRED.WALCL") - P("FRED.WTREGEN") - 1000 * P("FRED.RRPONTSYD")) / 1000
    F["net_liquidity_chg20"] = ("plynnosc", lag(net))
    F["m2_yoy"] = ("plynnosc", window_feature(fr("FRED.M2SL"), lambda v: np.log(v / v.shift(12)), times))

    out = pd.DataFrame({k: v.values for k, (_, v) in F.items()}, index=days)
    out = out.replace([np.inf, -np.inf], np.nan)  # np. log(OI=0) — brak wartości, nie nieskończoność
    out.attrs["groups"] = {k: g for k, (g, _) in F.items()}
    return out


def zscore(raw: pd.DataFrame, asset: str) -> pd.DataFrame:
    """Kroczący z-score 3 lata (okno kończy się w D), min 1 rok — wyłącznie przeszłość i D."""
    win, minp = (1095, 365) if asset in CRYPTO_ASSETS else (756, 252)
    r = raw.rolling(win, min_periods=minp)
    sd = r.std()
    return (raw - r.mean()) / sd.where(sd > 0)


def to_long(raw: pd.DataFrame, z: pd.DataFrame, asset: str) -> pd.DataFrame:
    groups = raw.attrs["groups"]
    rl = raw.stack(future_stack=True).rename("value_raw")
    zl = z.stack(future_stack=True).rename("value_z")
    df = pd.concat([rl, zl], axis=1).reset_index()
    df.columns = ["date", "feature", "value_raw", "value_z"]
    df["asset"] = asset
    df["grp"] = df["feature"].map(groups)
    df["short_history"] = df["grp"].isin(SHORT_HISTORY_GROUPS)
    df = df.dropna(subset=["value_raw"])
    return df[["date", "asset", "feature", "grp", "value_raw", "value_z", "short_history"]]


def build(con, assets=("XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"), end=None) -> pd.DataFrame:
    end = pd.Timestamp(end or pd.Timestamp.now(tz="UTC").tz_localize(None)).normalize()
    all_days = pd.date_range(START["bday"], end, freq="D")
    pnl = panel(con, PANEL_SERIES, decision_times(all_days))  # jedno zapytanie ASOF dla wszystkich aktywów
    fr_cache: dict = {}
    parts = []
    for a in assets:
        raw = compute_asset(con, a, end, pnl, fr_cache)
        parts.append(to_long(raw, zscore(raw, a), a))
        log.info("cechy %s: %d dni, %d cech", a, len(raw), raw.shape[1])
    return pd.concat(parts, ignore_index=True)


def write(con, df: pd.DataFrame) -> None:
    """Przebudowa w całości (DROP + CREATE)."""
    con.register("feat_df", df)
    con.execute("DROP TABLE IF EXISTS features_daily")
    con.execute("""CREATE TABLE features_daily AS
                   SELECT CAST(date AS DATE) AS date, asset, feature, grp, value_raw, value_z, short_history,
                          now()::TIMESTAMP AS built_at FROM feat_df""")
    con.unregister("feat_df")

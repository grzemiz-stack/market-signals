"""Dekompozycja tygodniowych zwrotów na wkłady grup czynników (styl GRAM). Definicje: docs/ETAP4-PLAN.md.

Betas z okna 260 tygodni kończącego się w t−1, zastosowane do czynników tygodnia t (bez patrzenia w t i dalej).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ms.features import COT, seasonal_deviation  # noqa: F401  (seasonal_deviation — wzorzec sezonowości)
from ms.pit import CRYPTO_ASSETS, align, available_from, first_release, panel
from ms.prices import price_frame

log = logging.getLogger("decompose")

WINDOW, MIN_ROWS, MIN_FACTOR_WEEKS = 260, 104, 156
IV = {"XAU": "FRED.GVZCLS", "WTI": "FRED.OVXCLS", "BRENT": "FRED.OVXCLS", "BTC": "DVOL.BTC.close", "ETH": "DVOL.ETH.close"}
GROUPS = {"dfii10_chg": "koszt_alternatywny", "usd_gram_ret": "koszt_alternatywny", "t10yie_chg": "koszt_alternatywny",
          "vix_chg": "ryzyko", "gpr_ma7_chg": "ryzyko", "iv_chg": "ryzyko",
          "mom_4w": "momentum_pozycje", "cot_net_oi_chg": "momentum_pozycje",
          "stocks_surprise": "ropa_podaz", "wti_ret": "krzyzowe"}


def week_ends(asset: str, start, end) -> pd.DatetimeIndex:
    """Chwile końca tygodnia (UTC). Etykieta tygodnia = data piątku (krypto: niedzieli)."""
    if asset in CRYPTO_ASSETS:
        sundays = pd.date_range(pd.Timestamp(start).normalize(), end, freq="W-SUN")
        return sundays + pd.Timedelta(days=1)
    fridays = pd.date_range(pd.Timestamp(start).normalize(), end, freq="W-FRI")
    return fridays + pd.Timedelta(hours=22)


def label(times: pd.DatetimeIndex, asset: str) -> pd.DatetimeIndex:
    return (times - pd.Timedelta(days=1)).normalize() if asset in CRYPTO_ASSETS else times.normalize()


def weekly_returns(pf: pd.DataFrame, times: pd.DatetimeIndex) -> pd.Series:
    """Suma logret między ostatnimi znanymi zamknięciami na kolejne końce tygodnia; NaN gdy w środku jest NaN."""
    lr = pf["logret"].reset_index(drop=True)
    s = lr.fillna(0).cumsum()
    nn = lr.isna().cumsum()
    avail = available_from(pf["known_at"].reset_index(drop=True))
    pos = align(pd.Series(np.arange(len(pf), dtype=float)), avail, times)
    sv, nv = s.to_numpy(), nn.to_numpy()
    out = np.full(len(times), np.nan)
    for i in range(1, len(times)):
        a, b = pos.iloc[i - 1], pos.iloc[i]
        if np.isnan(a) or np.isnan(b):
            continue
        a, b = int(a), int(b)
        out[i] = 0.0 if a == b else (sv[b] - sv[a] if nv[b] - nv[a] == 0 else np.nan)
    return pd.Series(out, index=times)


def report_surprises(con, sid: str = "EIA.WCESTUS1") -> tuple[pd.DataFrame, pd.Series]:
    """Dla każdego raportu WPSR: zmiana zapasów − średnia zmiana tego tygodnia w 5 poprzednich latach (tylko przeszłość).
    Zwraca (first_release posortowane po observed_at, niespodzianka w tej samej kolejności)."""
    fr = first_release(con, [sid]).sort_values("observed_at").reset_index(drop=True)
    v = fr.set_index("observed_at")["value"]
    chg = v.diff()
    hist = []
    for n in range(1, 6):
        tgt = pd.DataFrame({"t": chg.index - pd.DateOffset(years=n), "d": chg.index}).sort_values("t")
        m = pd.merge_asof(tgt, pd.DataFrame({"t": chg.index, "c": chg.values}), on="t", direction="nearest",
                          tolerance=pd.Timedelta(days=4)).sort_values("d")
        hist.append(m["c"].to_numpy())
    h = np.vstack(hist)
    cnt = np.sum(~np.isnan(h), axis=0)
    with np.errstate(all="ignore"):
        seas = np.where(cnt >= 3, np.nansum(h, axis=0) / np.maximum(cnt, 1), np.nan)
    return fr, pd.Series(chg.to_numpy() - seas)


def stocks_surprise(con, times: pd.DatetimeIndex, sid: str = "EIA.WCESTUS1") -> pd.Series:
    """Zmiana zapasów z raportu WPSR opublikowanego w tygodniu − średnia zmiana tego tygodnia w 5 poprzednich latach."""
    fr, surprise = report_surprises(con, sid)
    idx = align(pd.Series(np.arange(len(fr), dtype=float)), available_from(fr["known_at"]), times)
    out = np.zeros(len(times))
    for i in range(1, len(times)):
        a, b = idx.iloc[i - 1], idx.iloc[i]
        if np.isnan(b):
            out[i] = np.nan
        elif not np.isnan(a) and b > a:
            out[i] = np.nansum(surprise.iloc[int(a) + 1 : int(b) + 1])  # raport(y) opublikowane w tygodniu
    return pd.Series(out, index=times)


def factors(con, asset: str, end=None) -> pd.DataFrame:
    pf = price_frame(con, asset)
    times = week_ends(asset, pf.index.min(), end or pd.Timestamp.now(tz="UTC").tz_localize(None))
    rep, mkt, lng, sht, oi = COT[asset]
    cot = [f"COT.{rep}.{mkt}.{c}" for c in (lng, sht, oi)]
    sids = ["FRED.DFII10", "FRED.T10YIE", "FRED.VIXCLS", "FRED.DEXUSEU", "FRED.DEXJPUS", "FRED.DEXCHUS", "FRED.DEXUSAL", *cot]
    if asset in IV:
        sids.append(IV[asset])
    P = panel(con, sids, times)
    col = lambda s: P[s] if s in P else pd.Series(np.nan, index=times)  # noqa: E731
    W = pd.DataFrame(index=times)
    W["ret"] = weekly_returns(pf, times)
    W["dfii10_chg"] = col("FRED.DFII10").diff()
    usd = pd.concat([-np.log(col("FRED.DEXUSEU")), np.log(col("FRED.DEXJPUS")), np.log(col("FRED.DEXCHUS")),
                     -np.log(col("FRED.DEXUSAL"))], axis=1).mean(axis=1, skipna=False)
    W["usd_gram_ret"] = usd.diff()
    W["t10yie_chg"] = col("FRED.T10YIE").diff()
    W["vix_chg"] = col("FRED.VIXCLS").diff()
    g = first_release(con, ["GPR.GPRD"]).sort_values("observed_at").reset_index(drop=True)
    W["gpr_ma7_chg"] = align(g["value"].rolling(7, min_periods=7).mean(), available_from(g["known_at"]), times).diff()
    if asset in IV:
        W["iv_chg"] = col(IV[asset]).diff()
    W["mom_4w"] = W["ret"].shift(1).rolling(4, min_periods=4).sum()
    W["cot_net_oi_chg"] = ((col(cot[0]) - col(cot[1])) / col(cot[2])).diff()
    if asset in ("WTI", "BRENT"):
        W["stocks_surprise"] = stocks_surprise(con, times)
    if asset in ("XAU", "XAG"):
        W["wti_ret"] = weekly_returns(price_frame(con, "WTI"), times)
    W.index = label(times, asset)
    W.index.name = "week"
    return W.replace([np.inf, -np.inf], np.nan)


def rolling_decompose(W: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Zwraca (wyniki tygodniowe: ret, yhat, unexplained, r2_in, wkłady grup; betas long).
    Betas tygodnia t wyłącznie z wierszy t−260..t−1."""
    fac = [c for c in W.columns if c != "ret"]
    y = W["ret"].to_numpy()
    F = W[fac].to_numpy()
    rows, betas = [], []
    for i in range(WINDOW // 2, len(W)):
        lo = max(0, i - WINDOW)
        Fw, yw = F[lo:i], y[lo:i]
        use = [k for k in range(len(fac)) if np.isfinite(F[i, k]) and np.isfinite(Fw[:, k]).sum() >= MIN_FACTOR_WEEKS]
        if not use or not np.isfinite(y[i]):
            continue
        ok = np.isfinite(yw) & np.isfinite(Fw[:, use]).all(axis=1)
        n = int(ok.sum())
        if n < MIN_ROWS or n <= len(use) + 10:
            continue
        X = np.column_stack([np.ones(n), Fw[ok][:, use]])
        b, *_ = np.linalg.lstsq(X, yw[ok], rcond=None)
        res = yw[ok] - X @ b
        dof = n - X.shape[1]
        s2 = res @ res / dof
        se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))
        r2_in = 1 - (res @ res) / np.sum((yw[ok] - yw[ok].mean()) ** 2)
        contrib = {fac[k]: b[j + 1] * F[i, k] for j, k in enumerate(use)}
        groups: dict[str, float] = {}
        for f, c in contrib.items():
            groups[GROUPS[f]] = groups.get(GROUPS[f], 0.0) + c
        total = sum(contrib.values())
        rows.append({"week": W.index[i], "ret": y[i], "yhat": b[0] + total, "unexplained": y[i] - total,
                     "r2_in": r2_in, "n_window": n, **{f"g:{g}": v for g, v in groups.items()}})
        for j, k in enumerate(use):
            betas.append((W.index[i], fac[k], b[j + 1], b[j + 1] / se[j + 1] if se[j + 1] > 0 else np.nan))
    out = pd.DataFrame(rows).set_index("week")
    return out, pd.DataFrame(betas, columns=["week", "factor", "beta", "t_stat"])


def oos_r2(out: pd.DataFrame) -> float:
    y, yh = out["ret"], out["yhat"]
    return float(1 - ((y - yh) ** 2).sum() / ((y - y.mean()) ** 2).sum())

"""Punkty odniesienia ze zmienności (etap 3A): p_up/p_down dla |ruch 5d| > 1,5·sigma_5d (definicja z labels).

Każdy model zwraca DataFrame indeksowany dniem decyzji D: p_up, p_down — wyłącznie z informacji znanej w D 22:00
(obserwacje do L(D), parametry z walk-forward). Szczegóły i decyzje: docs/ETAP3-PLAN.md.
"""

from __future__ import annotations

import logging
import warnings
import zlib

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from ms.wf import AssetData, folds, test_mask, train_mask

log = logging.getLogger("baselines")
K_SIGMA = 1.5
IV_SERIES = {"XAU": "FRED.GVZCLS", "WTI": "FRED.OVXCLS", "BRENT": "FRED.OVXCLS", "BTC": "DVOL.BTC.close",
             "ETH": "DVOL.ETH.close"}


def _thr(d: AssetData) -> np.ndarray:
    """Próg prognozy: 1,5 · std(252 obs do L(D)) · √5. NIE sigma_5d z etykiety — ta liczona jest do D włącznie,
    a obserwacje między L i D (np. świeca D krypto) nie są znane w chwili prognozy."""
    s = pd.Series(d.r).rolling(252, min_periods=252).std().to_numpy() * np.sqrt(5)
    return K_SIGMA * s[d.table["pos_l"].to_numpy()]


# --------------------------------------------------------------------------- a) rv-ratio, logistyczna


def rv_features(d: AssetData) -> pd.DataFrame:
    r = pd.Series(d.r)
    s252 = r.rolling(252, min_periods=252).std()
    x = pd.DataFrame({"lr20": np.log(r.rolling(20).std() / s252), "lr5": np.log(r.rolling(5).std() / s252)})
    x = x.replace([np.inf, -np.inf], np.nan)
    return x.iloc[d.table["pos_l"].to_numpy()].set_index(d.table.index)  # cechy z L(D)


def walk_forward_logit(X: pd.DataFrame, d: AssetData, C: float = 1e6) -> pd.DataFrame:
    """Logistyczna per kierunek, refit co rok (rozszerzane okno, purge + embargo)."""
    t = d.table
    out = pd.DataFrame(np.nan, index=t.index, columns=["p_up", "p_down"])
    ok = X.notna().all(axis=1)
    for fold in folds(t):
        tr = train_mask(t, fold[0]) & ok
        te = test_mask(t, fold) & ok
        if te.sum() == 0 or tr.sum() < 500:
            continue
        for col, y in (("p_up", "y_up"), ("p_down", "y_down")):
            if t.loc[tr, y].nunique() < 2:
                continue
            m = LogisticRegression(C=C, max_iter=1000).fit(X[tr], t.loc[tr, y])
            out.loc[te, col] = m.predict_proba(X[te])[:, 1]
    return out


def model_rv_ratio(d: AssetData) -> pd.DataFrame:
    return walk_forward_logit(rv_features(d), d)


# --------------------------------------------------------------------------- b) GARCH(1,1)-t


def model_garch(d: AssetData, sims: int = 2000, start: pd.Timestamp | None = None, seed: int = 0) -> pd.DataFrame:
    """Refit co miesiąc na obserwacjach znanych przed pierwszą decyzją miesiąca; symulacja sum kroków g+1..g+5."""
    from arch.univariate import GARCH, ConstantMean, StudentsT

    t = d.table
    out = pd.DataFrame(np.nan, index=t.index, columns=["p_up", "p_down"])
    y = d.r * 100
    thr = _thr(d) * 100
    idx = t.index if start is None else t.index[t.index >= start]
    for _, month in pd.Series(idx, index=idx).groupby([idx.year, idx.month]):
        days = month.index
        tm = t.loc[days]
        fit_end = int(tm["pos_l"].min())  # obserwacje znane w pierwszej decyzji miesiąca
        if fit_end < 1000:
            continue
        max_origin = int(tm["pos_l"].max())
        # symulacja losuje z generatora rozkładu -> ziarno (aktywo, miesiąc) w StudentsT: wynik powtarzalny
        # (random_state w forecast() działa w arch tylko dla method="bootstrap")
        dist = StudentsT(seed=np.random.default_rng(zlib.crc32(f"{d.asset}{days[0]:%Y-%m}{seed}".encode())))
        am = ConstantMean(y[: max_origin + 1], volatility=GARCH(1, 0, 1), distribution=dist, rescale=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = am.fit(last_obs=fit_end + 1, disp="off", show_warning=False)
            H = int(tm["g"].max()) + 5
            origins = sorted(set(tm["pos_l"]))
            fc = res.forecast(start=min(origins), horizon=H, method="simulation", simulations=sims, reindex=False)
        sim = fc.simulations.values  # (n_origin, sims, H), origin = min(origins) ... max_origin
        for day, row in tm.iterrows():
            o, g = int(row["pos_l"]) - min(origins), int(row["g"])
            s5 = sim[o, :, g : g + 5].sum(axis=1)
            th = thr[t.index.get_loc(day)]
            if np.isfinite(th):
                out.loc[day] = [(s5 > th).mean(), (s5 < -th).mean()]
    return out


# --------------------------------------------------------------------------- c) HAR-RV


def har_design(r: np.ndarray) -> pd.DataFrame:
    r2 = pd.Series(r ** 2)
    return pd.DataFrame({"rv_d": r2, "rv_w": r2.rolling(5).mean(), "rv_m": r2.rolling(22).mean(),
                         "target": r2[::-1].rolling(5).mean()[::-1].shift(-1),  # średnia r² kroków 1..5
                         "ret5": pd.Series(r)[::-1].rolling(5).sum()[::-1].shift(-1)})


def model_har(d: AssetData) -> pd.DataFrame:
    """OLS: średnia wariancja 5 dni ~ RV_d + RV_w + RV_m; σ̂_5d = √(5·v̂); p z rozkładu t dopasowanego na resztach
    standaryzowanych (ret5/σ̂_5d) z treningu. Próbki treningowe = pochodzenia L(t) dni treningowych (etykieta t znana)."""
    t = d.table
    h = har_design(d.r)
    Xall = h[["rv_d", "rv_w", "rv_m"]].to_numpy()
    out = pd.DataFrame(np.nan, index=t.index, columns=["p_up", "p_down"])
    thr = _thr(d)
    for fold in folds(t):
        tr = train_mask(t, fold[0]).to_numpy()
        te = test_mask(t, fold)
        # pochodzenia treningowe: wszystkie obserwacje, których okno 5 kroków kończy się przed foldem i embargiem
        last_pos = int(t.loc[tr, "pos_l"].max()) if tr.any() else -1
        tr_obs = np.arange(len(h)) <= last_pos - 5
        ok = tr_obs & np.isfinite(Xall).all(axis=1) & np.isfinite(h["target"].to_numpy())
        if ok.sum() < 500 or te.sum() == 0:
            continue
        A = np.column_stack([np.ones(ok.sum()), Xall[ok]])
        beta, *_ = np.linalg.lstsq(A, h["target"].to_numpy()[ok], rcond=None)
        fitted = np.clip(np.column_stack([np.ones(len(h)), Xall]) @ beta, 1e-12, None)
        sig5 = np.sqrt(5 * fitted)
        z = (h["ret5"].to_numpy() / sig5)[ok]
        z = z[np.isfinite(z)]
        df_, _, scale = stats.t.fit(z, floc=0)
        pl = t.loc[te, "pos_l"].to_numpy()
        s = sig5[pl]
        th = thr[te.to_numpy()]
        x = th / (s * scale)
        out.loc[te, "p_up"] = stats.t.sf(x, df_)
        out.loc[te, "p_down"] = stats.t.cdf(-x, df_)
    return out


# --------------------------------------------------------------------------- d) implied vol


def iv_series(con, d: AssetData) -> pd.Series | None:
    from ms.pit import decision_times, panel

    sid = IV_SERIES.get(d.asset)
    if sid is None:
        return None
    p = panel(con, [sid], decision_times(d.table.index))
    return pd.Series(p[sid].to_numpy() if sid in p else np.nan, index=d.table.index)


def model_iv_raw(con, d: AssetData) -> pd.DataFrame | None:
    iv = iv_series(con, d)
    if iv is None:
        return None
    sig = iv / 100 * np.sqrt(5 / d.ann)  # DVOL na 365 dniach kalendarzowych, GVZ/OVX: √(5/252) wg decyzji
    x = _thr(d) / sig.to_numpy()
    p = stats.norm.sf(x)
    return pd.DataFrame({"p_up": p, "p_down": p}, index=d.table.index)


def model_iv_calibrated(con, d: AssetData, raw: pd.DataFrame | None = None) -> pd.DataFrame | None:
    raw = raw if raw is not None else model_iv_raw(con, d)
    if raw is None:
        return None
    lg = np.log(raw["p_up"].clip(1e-6, 1 - 1e-6) / (1 - raw["p_up"].clip(1e-6, 1 - 1e-6)))
    return walk_forward_logit(pd.DataFrame({"logit_p": lg}), d)


MODELS = ("rv_ratio", "garch_t", "har_rv", "iv_raw", "iv_calibrated")


def run_all(con, d: AssetData, garch_start: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:
    out = {"rv_ratio": model_rv_ratio(d), "har_rv": model_har(d)}
    log.info("%s: rv_ratio, har_rv gotowe", d.asset)
    out["garch_t"] = model_garch(d, start=garch_start)
    log.info("%s: garch_t gotowe", d.asset)
    raw = model_iv_raw(con, d)
    if raw is not None:
        out["iv_raw"] = raw
        out["iv_calibrated"] = model_iv_calibrated(con, d, raw)
    return out

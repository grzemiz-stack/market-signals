"""Etap 3B: LightGBM per aktywo i kierunek (up/down), walk-forward, kalibracja sigmoid z przeszłych foldów, SHAP.

- Cechy: z-score z features_daily (bez short_history) + prognoza punktu odniesienia wybranego W KAŻDYM FOLDZIE
  na podstawie przeszłości (najniższy Brier na prognozach out-of-sample sprzed foldu; bez historii: rv_ratio).
  Wybór „najlepszego” z raportu 3A byłby strojeniem na okresie testowym.
- Walk-forward: foldy roczne, rozszerzane okno, purge (end_5d < start foldu) + embargo 40 dni (wf.train_mask).
- Wczesne zatrzymanie: ostatnie 2 lata treningu = walidacja wewnętrzna (z własnym purge/embargo);
  potem refit na całym treningu z najlepszą liczbą rund.
- Wagi: unikalność etykiety (średnia 1/współbieżność po 5 obserwacjach okna), znormalizowane do średniej 1.
- Kalibracja: sigmoid (Platt) na logit surowej prognozy, dopasowana WYŁĄCZNIE na OOS z poprzednich foldów
  (end_5d < start foldu, data <= start − 40 d). Za mało historii -> brak prognozy skalibrowanej.
- SHAP: TreeExplainer (interventional), wyjście surowe = log-odds, tło 500 dni treningu, suma po grupach GRAM.
"""

from __future__ import annotations

import json
import logging

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ms import wf

log = logging.getLogger("gbm")

PARAMS = dict(objective="binary", num_leaves=15, min_data_in_leaf=100, learning_rate=0.03, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, seed=7, deterministic=True, force_row_wise=True,
              num_threads=4, verbose=-1)
MAX_ROUNDS = 1000
EARLY_STOP = 50
FALLBACK_ROUNDS = 100
INNER_VAL = pd.DateOffset(years=2)
MIN_CAL_ROWS, MIN_CAL_EVENTS = 250, 10
BASELINE_GROUP = "punkt_odniesienia"
FIRST_FOLD = {"bday": 2000, "crypto": 2021}


def feature_matrix(con, asset: str, t: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    f = con.execute("SELECT date, feature, grp, value_z FROM features_daily WHERE asset=? AND NOT short_history", [asset]).df()
    groups = dict(f[["feature", "grp"]].drop_duplicates().values)
    X = f.pivot(index="date", columns="feature", values="value_z")
    X.index = pd.to_datetime(X.index).astype("datetime64[ns]")
    return X.reindex(t.index), groups


def baseline_frame(con, asset: str, t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    b = con.execute("SELECT date, model, p_up, p_down FROM baseline_preds WHERE asset=?", [asset]).df()
    b["date"] = pd.to_datetime(b["date"]).astype("datetime64[ns]")
    return {m: g.set_index("date")[["p_up", "p_down"]].reindex(t.index) for m, g in b.groupby("model")}


def choose_baseline(bases: dict[str, pd.DataFrame], t: pd.DataFrame, fold_start: pd.Timestamp) -> str:
    """Model o najniższym Brierze (średnia up/down) na prognozach sprzed foldu (purge + embargo)."""
    past = wf.train_mask(t, fold_start)
    best, best_b = "rv_ratio", np.inf
    for m, p in bases.items():
        ok = past & p["p_up"].notna()
        if ok.sum() < 250:
            continue
        b = np.mean([((p.loc[ok, "p_up"] - t.loc[ok, "y_up"]) ** 2).mean(), ((p.loc[ok, "p_down"] - t.loc[ok, "y_down"]) ** 2).mean()])
        if b < best_b:
            best, best_b = m, b
    return best


def uniqueness_weights(t: pd.DataFrame, horizon: int = 5) -> pd.Series:
    """Średnia 1/współbieżność po obserwacjach okna etykiety (pos_d+1..pos_d+5); średnia wag = 1."""
    pos = t["pos_d"].to_numpy()
    n = int(pos.max()) + horizon + 2
    conc = np.zeros(n)
    for k in range(1, horizon + 1):
        np.add.at(conc, pos + k, 1)
    u = np.array([np.mean(1 / conc[p + 1 : p + horizon + 1]) for p in pos])
    return pd.Series(u / u.mean(), index=t.index)


def _fit(X: pd.DataFrame, y: pd.Series, w: pd.Series, t: pd.DataFrame, fold_start: pd.Timestamp) -> tuple[lgb.Booster, int]:
    tr = wf.train_mask(t, fold_start)
    val_start = fold_start - INNER_VAL
    inner = wf.train_mask(t, val_start)                      # trening wewnętrzny z purge/embargo względem walidacji
    val = tr & pd.Series(t.index >= val_start, index=t.index)
    if val.sum() < 200 or y[val].sum() < 5 or inner.sum() < 500:
        rounds = FALLBACK_ROUNDS  # za mało przeszłości na walidację wewnętrzną (zapisane w metadanych foldu)
    else:
        dtr = lgb.Dataset(X[inner], y[inner], weight=w[inner], free_raw_data=False)
        dva = lgb.Dataset(X[val], y[val], weight=w[val], reference=dtr, free_raw_data=False)
        m = lgb.train(PARAMS, dtr, MAX_ROUNDS, valid_sets=[dva], callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)])
        rounds = max(m.best_iteration, 10)
    final = lgb.train(PARAMS, lgb.Dataset(X[tr], y[tr], weight=w[tr]), rounds)
    return final, rounds


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calibrate(oos: pd.DataFrame, t: pd.DataFrame, fold_start: pd.Timestamp, ycol: str):
    """Platt na OOS z poprzednich foldów: tylko wiersze z zakończoną etykietą przed foldem (purge + embargo)."""
    past = oos.index[wf.train_mask(t, fold_start).reindex(oos.index, fill_value=False)]
    o = oos.loc[past].dropna(subset=["raw"])
    y = t.loc[o.index, ycol]
    if len(o) < MIN_CAL_ROWS or y.sum() < MIN_CAL_EVENTS or y.nunique() < 2:
        return None, o.index.max() if len(o) else None
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(o["raw"]).reshape(-1, 1), y)
    return lr, o.index.max()


def load_inputs(con, d: wf.AssetData) -> tuple[pd.DataFrame, dict[str, str], dict[str, pd.DataFrame]]:
    X0, groups = feature_matrix(con, d.asset, d.table)
    return X0, groups, baseline_frame(con, d.asset, d.table)


def run(con, d: wf.AssetData, direction: str, folds_from: int | None = None, shap_from: pd.Timestamp | None = None,
        inputs: tuple | None = None, until: pd.Timestamp | None = None):
    """Zwraca (prognozy OOS: raw, p, baseline_model, fold; metadane foldów; SHAP po grupach).
    inputs: (X0, groups, bases) — do testów perturbacji; until: pomiń foldy zaczynające się po tej dacie."""
    t = d.table
    ycol = f"y_{direction}"
    X0, groups, bases = inputs if inputs is not None else load_inputs(con, d)
    w = uniqueness_weights(t)
    kind = "crypto" if d.ann == 365 else "bday"
    oos = pd.DataFrame(index=t.index, columns=["raw", "p", "baseline_model", "fold"], dtype=object)
    meta, shap_rows = [], []
    for fold in wf.folds(t, folds_from or FIRST_FOLD[kind]):
        te = wf.test_mask(t, fold)
        if te.sum() == 0 or (until is not None and fold[0] > until):
            continue
        bm = choose_baseline(bases, t, fold[0])
        X = X0.copy()
        X["baseline_p_up"], X["baseline_p_down"] = (bases[bm]["p_up"], bases[bm]["p_down"]) if bm in bases else (np.nan, np.nan)
        y = t[ycol]
        model, rounds = _fit(X, y, w, t, fold[0])
        raw = model.predict(X[te])
        oos.loc[te, "raw"] = raw
        oos.loc[te, "baseline_model"] = bm
        oos.loc[te, "fold"] = fold[0].year
        cal, cal_max = calibrate(oos, t, fold[0], ycol)
        if cal is not None:
            oos.loc[te, "p"] = cal.predict_proba(logit(raw).reshape(-1, 1))[:, 1]
        meta.append({"fold": fold[0].year, "baseline_model": bm, "rounds": rounds, "n_train": int(wf.train_mask(t, fold[0]).sum()),
                     "calibrated": cal is not None, "cal_max_date": cal_max, "train_max_end_5d": t.loc[wf.train_mask(t, fold[0]), "end_5d"].max()})
        if shap_from is not None and fold[1] > shap_from:
            shap_rows.append(_shap(model, X, t, fold, groups, te & pd.Series(t.index >= shap_from, index=t.index)))
    oos["raw"] = oos["raw"].astype(float)
    oos["p"] = oos["p"].astype(float)
    shap_df = pd.concat(shap_rows, ignore_index=True) if shap_rows else pd.DataFrame()
    if len(shap_df):
        shap_df.insert(1, "asset", d.asset)
        shap_df.insert(2, "direction", direction)
    return oos, pd.DataFrame(meta), shap_df


def _shap(model, X, t, fold, groups, rows) -> pd.DataFrame:
    import shap

    tr = wf.train_mask(t, fold[0])
    bg = X[tr].sample(min(500, int(tr.sum())), random_state=0)
    masker = shap.maskers.Independent(bg, max_samples=len(bg))  # domyślnie shap obcina tło do 100 — chcemy 500
    ex = shap.TreeExplainer(model, data=masker, feature_perturbation="interventional", model_output="raw")
    sv = ex.shap_values(X[rows], check_additivity=False)
    sv = pd.DataFrame(sv, index=X.index[rows], columns=X.columns)
    grp = {c: groups.get(c, BASELINE_GROUP) for c in X.columns}
    agg = sv.T.groupby(grp).sum().T
    agg.index.name, agg.columns.name = "date", "group"
    return agg.stack().rename("contribution").reset_index()


def params_json() -> str:
    return json.dumps({**PARAMS, "max_rounds": MAX_ROUNDS, "early_stop": EARLY_STOP, "inner_val_years": 2,
                       "calibration": "sigmoid", "weights": "uniqueness", "baseline_feature": "wf-selected"}, sort_keys=True)

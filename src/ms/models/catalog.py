"""Katalog modeli rejestru. Opakowania istniejących prognoz walk-forward (nic nie jest liczone na nowo poza analogiami).

- base_rate: częstość bazowa (etykiety zakończone przed D) — zawsze fallback dla prob_*.
- rv_ratio, garch_t, har_rv, iv_raw, iv_calibrated: tabela baseline_preds (src/eval_baselines.py).
- lightgbm: tabela gbm_preds, prognoza skalibrowana (src/train_gbm.py).
- analogs_k20: częstość up/down w 20 analogiach (tabela analog_preds, liczona na żądanie: ensure_analog_preds).
- decomp_gram_260w / decomp_none: ŷ tygodnia z dekompozycji / średnia z okna (fallback).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ms import wf
from ms.models.base import Model

ASSETS = ("XAU", "XAG", "WTI", "BRENT", "BTC", "ETH")
IV_ASSETS = ("XAU", "WTI", "BRENT", "BTC", "ETH")
DISPLAY = {"base_rate": "częstość bazowa", "rv_ratio": "stosunek zmienności 20d/5d do rocznej",
           "garch_t": "GARCH(1,1)-t", "har_rv": "HAR-RV", "iv_raw": "implied vol (surowa)",
           "iv_calibrated": "implied vol skalibrowana", "lightgbm": "LightGBM", "analogs_k20": "analogie (k=20)",
           "decomp_gram_260w": "dekompozycja GRAM (okno 260 tyg.)", "decomp_none": "brak dekompozycji (średnia)"}
IV_NAME = {"XAU": "GVZ", "WTI": "OVX", "BRENT": "OVX", "BTC": "DVOL", "ETH": "DVOL"}

_tables: dict = {}


def _table(con, asset: str) -> pd.DataFrame:
    key = (id(con), asset)
    if key not in _tables:
        _tables[key] = wf.load(con, asset).table
    return _tables[key]


def clear_cache() -> None:
    _tables.clear()


def _dir(q: str) -> str:
    return "up" if q == "prob_up_5d" else "down"


class BaseRate(Model):
    def frame(self, con, asset):
        return wf.base_rate(_table(con, asset))[f"base_{_dir(self.question)}"]


class StoredBaseline(Model):
    def frame(self, con, asset):
        df = con.execute("SELECT date, p_up, p_down FROM baseline_preds WHERE asset=? AND model=? ORDER BY date",
                         [asset, self.id]).df()
        return pd.Series(df[f"p_{_dir(self.question)}"].to_numpy(), index=pd.to_datetime(df["date"]).astype("datetime64[ns]"))


class LightGBM(Model):
    def frame(self, con, asset):
        df = con.execute("SELECT date, p FROM gbm_preds WHERE asset=? AND direction=? AND p IS NOT NULL ORDER BY date",
                         [asset, _dir(self.question)]).df()
        return pd.Series(df["p"].to_numpy(), index=pd.to_datetime(df["date"]).astype("datetime64[ns]"))


class Analogs(Model):
    def frame(self, con, asset):
        try:
            df = con.execute("SELECT date, p_up, p_down FROM analog_preds WHERE asset=? ORDER BY date", [asset]).df()
        except Exception:  # tabela jeszcze nie istnieje
            return pd.Series(dtype=float)
        return pd.Series(df[f"p_{_dir(self.question)}"].to_numpy(), index=pd.to_datetime(df["date"]).astype("datetime64[ns]"))


class Decomp(Model):
    def frame(self, con, asset):
        df = con.execute("SELECT week, any_value(yhat) AS yhat FROM decomp_weekly WHERE asset=? GROUP BY week ORDER BY week",
                         [asset]).df()
        return pd.Series(df["yhat"].to_numpy(), index=pd.to_datetime(df["week"]).astype("datetime64[ns]"))


class DecompNone(Model):
    def frame(self, con, asset):
        df = con.execute("SELECT week, any_value(ret) AS ret FROM decomp_weekly WHERE asset=? GROUP BY week ORDER BY week",
                         [asset]).df()
        r = pd.Series(df["ret"].to_numpy(), index=pd.to_datetime(df["week"]).astype("datetime64[ns]"))
        return r.shift(1).rolling(260, min_periods=104).mean()  # tylko przeszłość


def ensure_analog_preds(con, asset: str, days: pd.DatetimeIndex) -> int:
    """Dolicza p_up/p_down z analogii dla brakujących dni (walk-forward: analogs.select widzi tylko path_end < D)."""
    from ms import analogs

    con.execute("CREATE TABLE IF NOT EXISTS analog_preds (date DATE, asset VARCHAR, p_up DOUBLE, p_down DOUBLE, n INTEGER)")
    have = {pd.Timestamp(d) for (d,) in con.execute("SELECT date FROM analog_preds WHERE asset=?", [asset]).fetchall()}
    todo = [d for d in days if d not in have]
    if not todo:
        return 0
    data = analogs.load(con, asset)
    rows = []
    for d in todo:
        if d not in data.z.index:
            continue
        r = analogs.select(data, d, n_null=0)
        if len(r.analogs) < analogs.K:
            continue
        rows.append((d.date(), asset, float(r.analogs["up_5d"].astype(float).mean()),
                     float(r.analogs["down_5d"].astype(float).mean()), len(r.analogs)))
    if rows:
        con.executemany("INSERT INTO analog_preds VALUES (?,?,?,?,?)", rows)
    return len(rows)


def all_models() -> list[Model]:
    out: list[Model] = []
    for q in ("prob_up_5d", "prob_down_5d"):
        out.append(BaseRate("base_rate", q, ASSETS, {"rule": "etykiety z end_5d < D"}, DISPLAY["base_rate"]))
        for m in ("rv_ratio", "garch_t", "har_rv"):
            out.append(StoredBaseline(m, q, ASSETS, {"source": "baseline_preds", "stage": "3A"}, DISPLAY[m]))
        for m in ("iv_raw", "iv_calibrated"):
            out.append(StoredBaseline(m, q, IV_ASSETS, {"source": "baseline_preds", "stage": "3A"}, DISPLAY[m]))
        out.append(LightGBM("lightgbm", q, ASSETS, {"source": "gbm_preds", "stage": "3B", "params": "ms.gbm.PARAMS"},
                            DISPLAY["lightgbm"]))
        out.append(Analogs("analogs_k20", q, ASSETS, {"k": 20, "min_feature_share": 0.7, "gap_days": 20}, DISPLAY["analogs_k20"]))
    out.append(Decomp("decomp_gram_260w", "decomp_weekly", ASSETS, {"window": 260, "stage": "4A"}, DISPLAY["decomp_gram_260w"]))
    out.append(DecompNone("decomp_none", "decomp_weekly", ASSETS, {"rule": "średnia 260 tyg."}, DISPLAY["decomp_none"]))
    return out


def display(model_id: str, asset: str) -> str:
    if model_id.startswith("iv_") and asset in IV_NAME:
        return f"{IV_NAME[asset]} {'skalibrowany' if model_id == 'iv_calibrated' else 'surowy'}"
    return DISPLAY.get(model_id, model_id)


def truth(con, asset: str, question: str) -> pd.DataFrame:
    """Prawda do oceny: kolumny y, resolved_at (koniec okna etykiety / tygodnia)."""
    if question.startswith("prob_"):
        t = _table(con, asset)
        return pd.DataFrame({"y": t[f"y_{_dir(question)}"], "resolved_at": t["end_5d"]}).dropna()
    df = con.execute("SELECT week, any_value(ret) AS y FROM decomp_weekly WHERE asset=? GROUP BY week", [asset]).df()
    idx = pd.DatetimeIndex(pd.to_datetime(df["week"]).astype("datetime64[ns]").to_numpy())
    return pd.DataFrame({"y": df["y"].to_numpy(), "resolved_at": idx.to_numpy()}, index=idx).sort_index()


__all__ = ["all_models", "ensure_analog_preds", "truth", "display", "np"]

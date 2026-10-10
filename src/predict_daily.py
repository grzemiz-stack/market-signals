"""Dzienne prognozy mistrzów (p_up/p_down) dla nowych dni — krok joba snapshot po build_features.

uv run src/predict_daily.py [--assets XAU ...]

Bez ponownego trenowania: ten sam kod modeli co comiesięczne eval_baselines (job registry), a parametry foldu
bieżącego roku zależą wyłącznie od etykiet zamkniętych przed jego początkiem (ms.wf.train_mask) — więc są takie same
jak w ostatnim comiesięcznym przebiegu (test: tests/test_predict_daily.py). GARCH: refit miesięczny na obserwacjach
znanych przed pierwszą decyzją miesiąca, tak samo jak w 3A. Dopisuje do baseline_preds tylko dni nowsze niż ostatni
zapisany i przelicza ostatnie 7 dni (spóźnione dane wejściowe; korekty w logu). Comiesięczny job registry przelicza
całość od nowa (jak dotąd).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import baselines, db, registry, wf  # noqa: E402

log = logging.getLogger("predict_daily")
ASSETS = ["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"]
QUESTIONS = ("prob_up_5d", "prob_down_5d")
NOT_STORED = {"base_rate"}  # liczone na bieżąco z etykiet (ms.models.catalog.BaseRate) — nic do dopisania


def model_preds(con, d: wf.AssetData, model_id: str, first_new: pd.Timestamp) -> pd.DataFrame:
    if model_id == "rv_ratio":
        return baselines.model_rv_ratio(d)
    if model_id == "har_rv":
        return baselines.model_har(d)
    if model_id == "garch_t":
        return baselines.model_garch(d, start=first_new.replace(day=1))  # cały miesiąc: te same pochodzenia co w 3A
    if model_id == "iv_raw":
        return baselines.model_iv_raw(con, d)
    if model_id == "iv_calibrated":
        return baselines.model_iv_calibrated(con, d)
    raise ValueError(f"mistrz {model_id!r} nie ma dziennego liczenia (dopisz w src/predict_daily.py)")


REFRESH_DAYS = 7   # dane spóźnione (np. GVZ/OVX z FRED publikowane następnego dnia, known_at = dzień notowania) -> przelicz okno


def predict_asset(con, asset: str) -> dict[str, int]:
    """Prognozy dla nowych dni + przeliczenie ostatnich REFRESH_DAYS dni (wejścia mogły dojść później; 2026-10-08:
    XAU 2026-10-06 policzone przed publikacją GVZ). Wiersze w oknie są zastępowane; zmiany wartości trafiają do logu."""
    d = wf.load(con, asset)
    models = sorted({registry.champion(con, asset, q).model_id for q in QUESTIONS} - NOT_STORED)
    added = {}
    for m in models:
        last = con.execute("SELECT max(date) FROM baseline_preds WHERE asset=? AND model=?", [asset, m]).fetchone()[0]
        lo = pd.Timestamp(last) - pd.Timedelta(days=REFRESH_DAYS) if last is not None else None
        days = d.table.index[d.table.index > lo] if lo is not None else d.table.index
        if not len(days):
            added[m] = 0
            continue
        p = model_preds(con, d, m, days.min())
        p = p.loc[p.index.isin(days)].dropna()
        old = con.execute("SELECT date, p_up, p_down FROM baseline_preds WHERE asset=? AND model=? AND date > ?",
                          [asset, m, (lo or pd.Timestamp("1900-01-01")).date()]).df()
        old["date"] = pd.to_datetime(old["date"])
        cmp = old.set_index("date").join(p, rsuffix="_new", how="inner")
        revised = cmp[(cmp["p_up"] - cmp["p_up_new"]).abs().gt(1e-12) | (cmp["p_down"] - cmp["p_down_new"]).abs().gt(1e-12)]
        for dt, r in revised.iterrows():
            log.info("%s %s %s: korekta po spóźnionych danych p_up %.5f -> %.5f, p_down %.5f -> %.5f", asset, m, dt.date(),
                     r.p_up, r.p_up_new, r.p_down, r.p_down_new)
        con.execute("DELETE FROM baseline_preds WHERE asset=? AND model=? AND date > ?",
                    [asset, m, (lo or pd.Timestamp("1900-01-01")).date()])
        df = p.reset_index(names="date").assign(asset=asset, model=m)
        con.register("bp", df)
        con.execute("INSERT INTO baseline_preds SELECT CAST(date AS DATE), asset, model, p_up, p_down, now()::TIMESTAMP FROM bp")
        con.unregister("bp")
        added[m] = len(df) - len(cmp)
        if len(df) < len(days):
            log.warning("%s %s: %d z %d dni bez prognozy (brak danych wejściowych, np. OVX)", asset, m, len(days) - len(df), len(days))
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=ASSETS)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "predict_daily.log"), logging.StreamHandler()])
    con = db.connect()
    for asset in a.assets:
        log.info("%s: dopisano %s", asset, predict_asset(con, asset))
    return 0


if __name__ == "__main__":
    sys.exit(main())

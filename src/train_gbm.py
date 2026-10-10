"""Etap 3B: LightGBM per aktywo i kierunek -> gbm_preds, shap_daily, runs + reports/gbm-eval-{data}.md.

uv run src/train_gbm.py [--assets XAU ...]
Każde uruchomienie = wpis w tabeli runs (konfiguracja + wynik): liczba prób do korekty wielokrotnych testów.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, evalframe as ef, gbm, wf  # noqa: E402

ASSETS = ["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"]


def best_baseline(con, asset: str, t: pd.DataFrame, base: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """Najlepszy punkt odniesienia z 3A (najwyższy BSS, wszystkie dni, ostatnie 10 lat) — porównanie ostrożne dla LGBM."""
    best, best_bss, best_p = None, -np.inf, None
    for m, p in gbm.baseline_frame(con, asset, t).items():
        df = ef.window(p.join(t[["y_up", "y_down"]]).join(base).dropna(), t.index.max())
        if len(df) < 120:
            continue
        s = ef.scores(df)["bss"]
        if s > best_bss:
            best, best_bss, best_p = m, s, p
    return best, best_p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=ASSETS)
    ap.add_argument("--note", default="pierwsza konfiguracja (bez strojenia)",
                    help='np. "rerun_after_pit_fix" — ponowne przeliczenie tej samej konfiguracji, nie nowa próba')
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "gbm.log"), logging.StreamHandler()])
    con = db.connect()
    con.execute("""CREATE TABLE IF NOT EXISTS runs (run_id VARCHAR, started_at TIMESTAMP, asset VARCHAR, stage VARCHAR,
                   params VARCHAR, n_eval INTEGER, bss DOUBLE, bss_lo DOUBLE, bss_hi DOUBLE,
                   bss_vs_baseline DOUBLE, vs_lo DOUBLE, vs_hi DOUBLE, baseline_model VARCHAR, note VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS gbm_preds (date DATE, asset VARCHAR, direction VARCHAR, raw DOUBLE, p DOUBLE,
                   baseline_model VARCHAR, fold INTEGER, run_id VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS shap_daily (date DATE, asset VARCHAR, direction VARCHAR, "group" VARCHAR,
                   contribution DOUBLE, run_id VARCHAR)""")
    run_id = uuid.uuid4().hex[:12]
    started = pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows, metas = [], []
    for asset in a.assets:
        t0 = time.time()
        d = wf.load(con, asset)
        t = d.table
        base = wf.base_rate(t)
        shap_from = t.index.max() - pd.DateOffset(years=ef.YEARS)
        res = {}
        for direction in ("up", "down"):
            oos, meta, sh = gbm.run(con, d, direction, shap_from=shap_from)
            res[direction] = oos
            metas.append(meta.assign(asset=asset, direction=direction))
            con.execute("DELETE FROM gbm_preds WHERE asset=? AND direction=?", [asset, direction])
            g = oos.dropna(subset=["raw"]).reset_index(names="date").assign(asset=asset, direction=direction, run_id=run_id)
            con.register("g", g)
            con.execute("INSERT INTO gbm_preds SELECT CAST(date AS DATE), asset, direction, raw, p, baseline_model, fold, run_id FROM g")
            con.unregister("g")
            con.execute("DELETE FROM shap_daily WHERE asset=? AND direction=?", [asset, direction])
            if len(sh):
                con.register("s", sh.assign(run_id=run_id))
                con.execute('INSERT INTO shap_daily SELECT CAST(date AS DATE), asset, direction, "group", contribution, run_id FROM s')
                con.unregister("s")
        bname, bp = best_baseline(con, asset, t, base)
        df = pd.DataFrame({"p_up": res["up"]["p"], "p_down": res["down"]["p"]}).join(t[["y_up", "y_down"]]).join(base)
        df = df.join(bp.rename(columns={"p_up": "b_up", "p_down": "b_down"}))
        df = ef.window(df.dropna(), t.index.max())
        for v in ("wszystkie", "co20"):
            sub, blocks = ef.variant(df, v)
            sg = ef.scores(sub)
            sb = ef.scores(sub, ("b_up", "b_down"))
            lo, hi = ef.bootstrap(sub, blocks, lambda x: ef.scores(x)["bss"])
            dlo, dhi = ef.bootstrap(sub, blocks, lambda x: ef.scores(x)["bss"] - ef.scores(x, ("b_up", "b_down"))["bss"])
            rows.append(dict(asset=asset, wariant=v, n=len(sub), od=sub.index.min().date(), bss=sg["bss"], lo=lo, hi=hi,
                             bss_base_model=sb["bss"], diff=sg["bss"] - sb["bss"], dlo=dlo, dhi=dhi, baseline=bname))
            if v == "wszystkie":
                con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            [run_id, started, asset, "3B", gbm.params_json(), len(sub), sg["bss"], lo, hi,
                             sg["bss"] - sb["bss"], dlo, dhi, bname, a.note])
        logging.info("%s: %.0f s", asset, time.time() - t0)
    r = pd.DataFrame(rows)
    n_runs = con.execute("SELECT count(DISTINCT run_id) FROM runs WHERE stage='3B'").fetchone()[0]
    n_cfg = con.execute("SELECT count(DISTINCT params) FROM runs WHERE stage='3B'").fetchone()[0]
    notes = con.execute("""SELECT note, count(DISTINCT run_id) FROM runs WHERE stage='3B' GROUP BY 1 ORDER BY 1""").fetchall()

    def verdict(x):
        if x.dlo > 0:
            return "LightGBM lepszy od najlepszego punktu odniesienia"
        if x.dhi < 0:
            return "LightGBM GORSZY od najlepszego punktu odniesienia"
        return "LightGBM NIE wygrywa z najlepszym punktem odniesienia (różnica nieodróżnialna od zera)"

    out = [f"# LightGBM vs punkty odniesienia — {date.today()}", "",
           f"Konfiguracja (jedna, bez strojenia na okresie testowym): `{gbm.params_json()}`.", "",
           f"Konfiguracje 3B (różne parametry) w tabeli runs: **{n_cfg}** — to liczba prób do korekty wielokrotnych testów. "
           f"Uruchomienia: {n_runs} ({'; '.join(f'{n}: {k}' for n, k in notes)}). To uruchomienie: `{a.note}`, run_id `{run_id}`.", "",
           "Prognoza skalibrowana (sigmoid na OOS z poprzednich foldów). Najlepszy punkt odniesienia = model z 3A o najwyższym "
           "BSS na wszystkich dniach ostatnich 10 lat (wybór na okresie testowym, więc porównanie jest OSTROŻNE dla LightGBM). "
           "Różnica BSS: bootstrap blokowy (wszystkie dni: bloki 60 dni; co20: bloki 6 zapytań).", "",
           "## Werdykt (wszystkie dni)", "", "| aktywo | n | BSS LightGBM [95% CI] | najlepszy punkt odniesienia | jego BSS | różnica [95% CI] | werdykt |",
           "|---|---|---|---|---|---|---|"]
    for x in r[r.wariant == "wszystkie"].itertuples():
        out.append(f"| {x.asset} | {x.n} | {x.bss:+.3f} [{x.lo:+.3f}, {x.hi:+.3f}] | {x.baseline} | {x.bss_base_model:+.3f} | "
                   f"{x.diff:+.3f} [{x.dlo:+.3f}, {x.dhi:+.3f}] | {verdict(x)} |")
    out += ["", "## Wariant co 20 dni", "", "| aktywo | n | BSS LightGBM [95% CI] | różnica vs punkt odniesienia [95% CI] |", "|---|---|---|---|"]
    for x in r[r.wariant == "co20"].itertuples():
        out.append(f"| {x.asset} | {x.n} | {x.bss:+.3f} [{x.lo:+.3f}, {x.hi:+.3f}] | {x.diff:+.3f} [{x.dlo:+.3f}, {x.dhi:+.3f}] |")
    meta = pd.concat(metas, ignore_index=True)
    out += ["", "## Foldy (ostatnie 10 lat): wybrany punkt odniesienia, liczba rund po wczesnym zatrzymaniu", ""]
    m10 = meta[meta.fold >= date.today().year - 10]
    out.append(m10.pivot_table(index=["asset", "direction"], columns="fold", values="rounds").to_markdown())
    shap_sum = con.execute("""SELECT asset, direction, "group", avg(abs(contribution)) AS sredni_abs FROM shap_daily
                              WHERE run_id=? GROUP BY ALL ORDER BY asset, direction, sredni_abs DESC""", [run_id]).df()
    out += ["", "## SHAP (log-odds): średni |wkład| grup, ostatnie 10 lat", "",
            shap_sum.pivot_table(index=["asset", "direction"], columns="group", values="sredni_abs").round(3).to_markdown()]
    p = db.ROOT / "reports" / f"gbm-eval-{date.today()}.md"
    p.write_text("\n".join(out) + "\n")
    print(r[r.wariant == "wszystkie"][["asset", "bss", "lo", "hi", "baseline", "bss_base_model", "diff", "dlo", "dhi"]].round(3).to_string())
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

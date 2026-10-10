"""Etap 3A: punkty odniesienia ze zmienności -> tabela baseline_preds + reports/baselines-eval-{data}.md.

uv run src/eval_baselines.py [--assets XAU ...]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import baselines, db, evalframe as ef, wf  # noqa: E402

ASSETS = ["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"]


def save_preds(con, asset: str, preds: dict[str, pd.DataFrame]) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS baseline_preds (date DATE, asset VARCHAR, model VARCHAR,
                   p_up DOUBLE, p_down DOUBLE, built_at TIMESTAMP)""")
    con.execute("DELETE FROM baseline_preds WHERE asset = ?", [asset])
    for m, p in preds.items():
        df = p.dropna().reset_index(names="date").assign(asset=asset, model=m)
        con.register("bp", df)
        con.execute("INSERT INTO baseline_preds SELECT CAST(date AS DATE), asset, model, p_up, p_down, now()::TIMESTAMP FROM bp")
        con.unregister("bp")


def evaluate_asset(d: wf.AssetData, preds: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    base = wf.base_rate(d.table)
    rows, rel = [], {}
    for m, p in preds.items():
        df = p.join(d.table[["y_up", "y_down"]]).join(base).dropna()
        df = ef.window(df, d.table.index.max())
        if len(df) < 120:
            continue
        for v in ("co20", "wszystkie"):
            sub, blocks = ef.variant(df, v)
            s = ef.scores(sub)
            lo, hi = ef.bootstrap(sub, blocks, lambda x: ef.scores(x)["bss"])
            rows.append({"aktywo": d.asset, "model": m, "wariant": v, "n": len(sub), "od": sub.index.min().date(),
                         "brier": s["brier"], "brier_bazowej": s["brier_base"], "bss": s["bss"], "ci_lo": lo, "ci_hi": hi})
        rel[m] = (ef.reliability(df, "p_up", "y_up"), ef.reliability(df, "p_down", "y_down"))
    return pd.DataFrame(rows), rel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=ASSETS)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "baselines.log"), logging.StreamHandler()])
    con = db.connect()
    tables, rels = [], {}
    for asset in a.assets:
        t0 = time.time()
        d = wf.load(con, asset)
        garch_start = d.table.index.max() - pd.DateOffset(years=ef.YEARS + 1)
        preds = baselines.run_all(con, d, garch_start=garch_start)
        save_preds(con, asset, preds)
        res, rel = evaluate_asset(d, preds)
        tables.append(res)
        rels[asset] = rel
        logging.info("%s: %d modeli, %.0f s", asset, len(preds), time.time() - t0)
    res = pd.concat(tables, ignore_index=True)
    con.register("ev", res.assign(od=pd.to_datetime(res["od"]), built_at=pd.Timestamp.now(tz="UTC").tz_localize(None)))
    con.execute("DROP TABLE IF EXISTS baseline_eval")  # wyniki 3A dla ms.prob (wybór modelu i jego BSS z CI)
    con.execute("CREATE TABLE baseline_eval AS SELECT * FROM ev")
    con.unregister("ev")

    allv = res[res.wariant == "wszystkie"]
    best = allv.loc[allv.groupby("aktywo")["bss"].idxmax()].set_index("aktywo")
    out = [f"# Punkty odniesienia ze zmienności — {date.today()}", "",
           "Cel: up_5d/down_5d (suma logret D+1..D+5 vs ±1,5·sigma_5d). Prognoza w chwili D 22:00 UTC. "
           "Brier = średnia z up i down; BSS vs częstość bazowa liczona wyłącznie z etykiet zakończonych przed D. "
           "95% CI: bootstrap blokowy (co20: bloki 6 zapytań; wszystkie: bloki 60 dni). Ostatnie 10 lat "
           "(krócej, gdy model/aktywo ma krótszą historię — kolumna „od”). Definicje: docs/ETAP3-PLAN.md.", "",
           "## Najlepszy punkt odniesienia per aktywo (najwyższy BSS, wszystkie dni)", "",
           "| aktywo | model | BSS [95% CI] | wniosek |", "|---|---|---|---|"]
    for asset, r in best.iterrows():
        concl = ("lepszy od częstości bazowej" if r.ci_lo > 0 else
                 "gorszy od częstości bazowej" if r.ci_hi < 0 else "nieodróżnialny od częstości bazowej")
        out.append(f"| {asset} | {r.model} | {r.bss:+.3f} [{r.ci_lo:+.3f}, {r.ci_hi:+.3f}] | {concl} |")
    out += ["", "Uwaga: „najlepszy” = maksimum z 3–5 modeli na tym samym okresie — BSS zwycięzcy jest zawyżony przez selekcję, "
            "a CI tego nie uwzględnia. Ceny rynkowe (EIA spot, Stooq, Yahoo, Binance) są znane w dniu notowania (known_at = zamknięcie sesji, decyzja 2026-10-06); implied vol z FRED — następnego dnia.", ""]
    out += ["", "## Wszystkie modele", "", "| aktywo | model | wariant | n | od | Brier | Brier bazowej | BSS [95% CI] |",
            "|---|---|---|---|---|---|---|---|"]
    for r in res.itertuples():
        out.append(f"| {r.aktywo} | {r.model} | {r.wariant} | {r.n} | {r.od} | {r.brier:.4f} | {r.brier_bazowej:.4f} | "
                   f"{r.bss:+.3f} [{r.ci_lo:+.3f}, {r.ci_hi:+.3f}] |")
    out += ["", "## Niezawodność (wszystkie dni): przedziały prognozy -> faktyczna częstość", ""]
    for asset, rel in rels.items():
        for m, (ru, rd) in rel.items():
            out += [f"### {asset} · {m}", "", "**up**", "", ru.to_markdown(floatfmt=".3f"), "", "**down**", "",
                    rd.to_markdown(floatfmt=".3f"), ""]
    p = db.ROOT / "reports" / f"baselines-eval-{date.today()}.md"
    p.write_text("\n".join(out))
    print(best[["model", "bss", "ci_lo", "ci_hi"]].to_string())
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

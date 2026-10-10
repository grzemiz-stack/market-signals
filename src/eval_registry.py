"""Miesięczna ewaluacja rejestru: model_scores za ostatni pełny miesiąc + reguły awansu/degradacji + raport.

uv run src/eval_registry.py [--month 2026-09]
Odświeżenie prognoz przed oceną: tools/registry_monthly.sh (launchd 1. dnia miesiąca 06:00).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, registry as rg  # noqa: E402
from ms.models import catalog  # noqa: E402

log = logging.getLogger("registry")


def start_champions(con) -> dict[tuple[str, str], str]:
    ev = con.execute("""SELECT aktywo, model FROM baseline_eval WHERE wariant='wszystkie'
                        QUALIFY row_number() OVER (PARTITION BY aktywo ORDER BY bss DESC) = 1""").fetchall()
    out = {}
    for asset, model in ev:
        out[(asset, "prob_up_5d")] = model
        out[(asset, "prob_down_5d")] = model
        out[(asset, "decomp_weekly")] = "decomp_gram_260w"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM; domyślnie ostatni pełny miesiąc")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "registry.log"), logging.StreamHandler()])
    con = db.connect()
    rg.init_schema(con)
    models = catalog.all_models()
    if rg.initialize(con, models, start_champions(con)):
        log.info("rejestr zainicjowany (mistrzowie z 3A)")
    new_trials = [m.id for m in models if rg.register_trial(con, m, "katalog")]
    known = {(r.asset, r.question, r.model_id) for r in rg.roles(con).itertuples()}
    for m in models:
        for asset in m.assets:
            if m.question != "event_response" and (asset, m.question, m.id) not in known:
                rg.set_role(con, asset, m.question, m.id, "challenger", "nowy model w katalogu")

    month = (pd.Timestamp(a.month + "-01") if a.month else
             (pd.Timestamp.now().normalize().replace(day=1) - pd.offsets.MonthBegin(1)))
    rule_m = rg.rule_months(month)
    span_start = min([month, *rule_m])
    catalog.clear_cache()

    changes, rows, diags = [], [], {}
    for asset in catalog.ASSETS:
        for q in ("prob_up_5d", "prob_down_5d", "decomp_weekly"):
            truth = catalog.truth(con, asset, q)
            if q.startswith("prob_") and q == "prob_up_5d":
                need = truth[(truth.resolved_at >= span_start) & (truth.resolved_at < month + pd.offsets.MonthBegin(1))].index
                catalog.ensure_analog_preds(con, asset, pd.DatetimeIndex(need))
            base = None
            if q.startswith("prob_"):
                base = next(m for m in models if m.id == "base_rate" and m.question == q).frame(con, asset)
            frames = {}
            for m in models:
                if m.question != q or asset not in m.assets:
                    continue
                df = rg.daily_frame(m.frame(con, asset), truth, base)
                frames[m.id] = df
                s = rg.score_month(df, q, month)
                con.execute("""INSERT OR REPLACE INTO model_scores VALUES (?,?,?,?,?,?,?,?,?)""",
                            [asset, q, m.id, month.date(), s["metric"], s["value"], s["ci_lo"], s["ci_hi"], s["n"]])
                rows.append({"asset": asset, "question": q, "model": m.id, **s})
            champ = rg.champion(con, asset, q).model_id
            dec, diag = rg.decide(q, champ, frames, rule_m)
            diags[(asset, q)] = diag
            changes += rg.apply(con, asset, q, dec)
    report(con, month, rule_m, pd.DataFrame(rows), changes, diags, new_trials)
    return 0


def report(con, month, rule_m, scores, changes, diags, new_trials) -> None:
    from ms.models.catalog import display

    def f(x):
        return "—" if x is None or not np.isfinite(x) else f"{x:+.3f}".replace(".", ",")

    in_sel = month <= rg.SELECTION_END
    out = [f"# Rejestr modeli — {month:%Y-%m}", "",
           f"Miesiąc oceny: {month:%Y-%m} (dni, których etykieta rozstrzyga się w tym miesiącu)."
           + (" **Miesiąc należy do okresu selekcji 3A — wynik informacyjny, reguły go nie liczą.**" if in_sel else ""),
           f"Miesiące liczone przez reguły (po {rg.SELECTION_END.date()}): {len(rule_m)}/{rg.RULE_MONTHS}"
           + ("" if len(rule_m) >= rg.RULE_MONTHS else " — za mało, reguły awansu/degradacji jeszcze nie działają."),
           f"Próby w model_trials: {rg.n_trials(con)} (nowe w tym uruchomieniu: {', '.join(new_trials) or 'brak'}).", "",
           "Uwaga: wynik jednego miesiąca (~20 dni, często 0–2 zdarzenia) jest bardzo zaszumiony — BSS potrafi wynosić "
           "+0,8 albo −5. Reguły decydują wyłącznie na 6 połączonych miesiącach (bootstrap blokowy, n >= 100 dni).", "",
           "## Aktywo × pytanie", "", "| aktywo | pytanie | mistrz (wizytówka) | wynik mistrza w miesiącu | pretendenci: wynik w miesiącu |",
           "|---|---|---|---|---|"]
    for asset in catalog.ASSETS:
        for q in ("prob_up_5d", "prob_down_5d", "decomp_weekly"):
            c = rg.champion(con, asset, q)
            sc = scores[(scores.asset == asset) & (scores.question == q)].set_index("model")
            cs = sc.loc[c.model_id] if c.model_id in sc.index else None
            chal = rg.roles(con, asset, q)
            chal = chal[chal.role == "challenger"]["model_id"]
            ctext = "; ".join(f"{display(m, asset)} {f(sc.loc[m, 'value']) if m in sc.index else '—'}" for m in chal)
            cv = f"{f(cs['value'])} [{f(cs['ci_lo'])}; {f(cs['ci_hi'])}], n={int(cs['n'])}" if cs is not None else "—"
            out.append(f"| {asset} | {q} | {c.card} | {cv} | {ctext} |")
    out += ["", "## Zmiany ról", ""]
    out += [f"- {c.asset} · {c.question}: {c.model_id} {c.old_role} -> {c.new_role} ({c.reason})" for c in changes] or ["Brak zmian."]
    out += ["", "## Event_response", "", "Zarezerwowane na etap zdarzeń (GDELT) — brak modeli.", ""]
    p = db.ROOT / "reports" / f"registry-{month:%Y-%m}.md"
    p.write_text("\n".join(out) + "\n")
    print(p)


if __name__ == "__main__":
    sys.exit(main())

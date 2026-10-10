"""Walidacja analogii -> reports/analogs-eval-{data}.md (definicje: ms/evaluate.py).

uv run src/eval_analogs.py [--assets XAU WTI ...]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import analogs, db, evaluate  # noqa: E402

ROWS = [("Brier: analogie", "brier_analog"), ("Brier: losowe z tercyla rv_60d", "brier_random"),
        ("Brier: częstość bazowa (tylko przeszłość)", "brier_base"),
        ("BSS analogie vs bazowa", "bss_analog"), ("BSS losowe vs bazowa", "bss_random"),
        ("BSS analogie − losowe", "bss_analog_minus_random"),
        ("oczekiwany BSS samego szumu próby k=20 (p(1−p)/k)", "bss_noise_k"),
        ("Spearman: mediana 20d analogii vs fakt", "spearman_20d"), ("Spearman: mediana 20d losowych vs fakt", "spearman_20d_rand"),
        ("Spearman: mediana 60d analogii vs fakt", "spearman_60d"), ("Spearman: mediana 60d losowych vs fakt", "spearman_60d_rand")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"])
    a = ap.parse_args()
    con = db.connect(db.DB_PATH, read_only=True)
    out = [f"# Walidacja analogii — {date.today()}", "",
           f"Zapytania co {evaluate.STEP} dni decyzji, ostatnie {evaluate.YEARS} lat (krypto: od kiedy są cechy i kandydaci). "
           f"Prognoza p_up/p_down = częstość w {analogs.K} analogiach; fakt z tabeli labels (±1,5σ, 5 dni). "
           f"Brier = średnia z up i down. BSS = 1 − Brier/Brier_bazowej. 95% CI: bootstrap blokowy "
           f"(bloki po {evaluate.BLOCK} zapytań, {evaluate.N_BOOT} powtórzeń). Werdykt „lepsze” tylko gdy dolna granica CI BSS > 0.",
           "",
           "Interpretacja: częstość w 20 datach ma wariancję p(1−p)/20, więc nawet trafne co do średniej analogie płacą karę "
           "w Brierze względem gładkiej częstości bazowej (wiersz „oczekiwany BSS samego szumu”). BSS gorszy niż ta kara "
           "= dodatkowo zła kalibracja (np. częstość w analogiach systematycznie wyższa niż fakt).", ""]
    summary = ["## Podsumowanie", "", "| aktywo | zapytań | BSS analogie [95% CI] | BSS losowe | BSS szumu k=20 | werdykt |", "|---|---|---|---|---|---|"]
    body = []
    for asset in a.assets:
        t0 = time.time()
        d = analogs.load(con, asset)
        df, skipped = evaluate.run(d)
        if len(df) < 2 * evaluate.BLOCK:
            body += [f"## {asset}", "", f"Za mało zapytań do oceny ({len(df)}; pominięte {skipped}).", ""]
            continue
        m = evaluate.metrics(df)
        ci = evaluate.bootstrap(df)
        v = evaluate.verdict(m, ci)
        summary.append(f"| {asset} | {len(df)} | {m['bss_analog']:+.3f} [{ci.loc['bss_analog','lo']:+.3f}, "
                       f"{ci.loc['bss_analog','hi']:+.3f}] | {m['bss_random']:+.3f} | {m['bss_noise_k']:+.3f} | {v.split(' (')[0]} |")
        body += [f"## {asset}", "",
                 f"Zapytań: {len(df)} ({df['query'].min().date()} … {df['query'].max().date()}), pominiętych: {skipped} "
                 f"(za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: "
                 f"{df['oldest_candidate'].min().date()} … {df['oldest_candidate'].max().date()}. "
                 f"Faktyczna częstość w zapytaniach: up {df['y_up'].mean():.3f}, down {df['y_down'].mean():.3f}; "
                 f"średnia prognoza analogii: up {df['p_up'].mean():.3f}, down {df['p_down'].mean():.3f}.", "",
                 "| metryka | wartość | 95% CI |", "|---|---|---|"]
        for label, key in ROWS:
            val = m[key]
            body.append(f"| {label} | {val:.4f} | [{ci.loc[key, 'lo']:.4f}, {ci.loc[key, 'hi']:.4f}] |"
                        if not np.isnan(val) else f"| {label} | — | — |")
        body += ["", f"Werdykt: {v}", "", f"_czas: {time.time() - t0:.0f} s_", ""]
        print(asset, len(df), f"{m['bss_analog']:+.3f}", v, flush=True)
    p = db.ROOT / "reports" / f"analogs-eval-{date.today()}.md"
    p.write_text("\n".join(out + summary + [""] + body))
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

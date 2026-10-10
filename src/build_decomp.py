"""Dekompozycja tygodniowa -> tabele decomp_weekly, betas_weekly + reports/decomp-{data}.md.

uv run src/build_decomp.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, decompose as dc  # noqa: E402

ASSETS = ["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"]
GROUP_ORDER = ["koszt_alternatywny", "ryzyko", "momentum_pozycje", "ropa_podaz", "krzyzowe"]
BETA_VIEWS = [("XAU", "dfii10_chg", "złoto vs Δ DFII10 (realna stopa 10 l.)"),
              ("XAU", "usd_gram_ret", "złoto vs koszyk dolara GRAM"),
              ("XAG", "wti_ret", "srebro vs zwrot WTI"),
              ("BTC", "vix_chg", "BTC vs Δ VIX (ryzyko)")]
OOS_MIN = 0.05


def yearly_r2(out: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y, g in out.groupby(out.index.year):
        if len(g) >= 20:
            rows.append({"rok": y, "R2_poza_proba": dc.oos_r2(g), "R2_w_probie": g["r2_in"].mean(), "tygodni": len(g)})
    return pd.DataFrame(rows).set_index("rok")


def main() -> int:
    con = db.connect()
    outs, bets = {}, []
    for a in ASSETS:
        W = dc.factors(con, a)
        out, b = dc.rolling_decompose(W)
        outs[a] = out
        bets.append(b.assign(asset=a))
    # tabele
    dec = []
    for a, out in outs.items():
        gcols = [c for c in out.columns if c.startswith("g:")]
        long = out[gcols].stack().rename("contribution").reset_index()
        long.columns = ["week", "group", "contribution"]
        long["group"] = long["group"].str[2:]
        long = long.merge(out[["unexplained", "ret", "yhat"]].reset_index(), on="week")
        dec.append(long.assign(asset=a))
    dec = pd.concat(dec, ignore_index=True)[["week", "asset", "group", "contribution", "unexplained", "ret", "yhat"]]
    betas = pd.concat(bets, ignore_index=True)[["week", "asset", "factor", "beta", "t_stat"]]
    for name, df in (("decomp_weekly", dec), ("betas_weekly", betas)):
        con.register("x", df)
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(f"CREATE TABLE {name} AS SELECT CAST(week AS DATE) AS week, * EXCLUDE (week) FROM x")
        con.unregister("x")

    # raport
    rep = [f"# Co ruszyło ceną — dekompozycja tygodniowa ({date.today()})", "",
           "Wkład grupy = Σ beta × zmiana czynnika w tym samym tygodniu; betas z okna 260 tygodni kończącego się tydzień "
           "wcześniej (bez patrzenia w bieżący tydzień). Niewyjaśnione = zwrot − suma wkładów (zawiera stałą). "
           "Wartości w punktach procentowych log-zwrotu. Definicje: docs/ETAP4-PLAN.md.", "",
           "## Jakość: R² poza próbą (betas z t−1) vs R² w próbie (okno regresji)", "",
           "| aktywo | od | tygodni | R² poza próbą | R² w próbie | ocena |", "|---|---|---|---|---|---|"]
    yr = {}
    for a, out in outs.items():
        o, i = dc.oos_r2(out), out["r2_in"].mean()
        last10 = out[out.index >= out.index.max() - pd.DateOffset(years=10)]
        o10 = dc.oos_r2(last10)
        verdict = (f"**R² poza próbą < {OOS_MIN}: dekompozycja prawie nic nie wyjaśnia**" if o10 < OOS_MIN
                   else "wyjaśnia część ruchów")
        rep.append(f"| {a} | {out.index.min().date()} | {len(out)} | {o:.3f} (ost. 10 lat: {o10:.3f}) | {i:.3f} | {verdict} |")
        yr[a] = yearly_r2(out)
    rep += ["", "R² w próbie jest zawsze wyższe — mierzy dopasowanie do danych, na których liczono betas. "
            "Liczy się R² poza próbą.", "", "### Per rok (ostatnie 12 lat): poza próbą / w próbie", ""]
    years = range(date.today().year - 11, date.today().year + 1)
    rep.append("| aktywo | " + " | ".join(str(y) for y in years) + " |")
    rep.append("|---|" + "---|" * len(years))
    for a, t in yr.items():
        cells = [f"{t.loc[y, 'R2_poza_proba']:.2f} / {t.loc[y, 'R2_w_probie']:.2f}" if y in t.index else "—" for y in years]
        rep.append(f"| {a} | " + " | ".join(cells) + " |")

    rep += ["", "## Ostatnie 8 tygodni: co ruszyło ceną (pp)", ""]
    for a, out in outs.items():
        last = out.tail(8)
        cols = [g for g in GROUP_ORDER if f"g:{g}" in last.columns]
        t = pd.DataFrame({g: 100 * last[f"g:{g}"] for g in cols})
        t["niewyjaśnione"] = 100 * last["unexplained"]
        t["zwrot"] = 100 * last["ret"]
        t.index = [d.date() for d in t.index]
        rep += [f"### {a}", "", t.round(2).to_markdown(), ""]

    rep += ["## Betas w czasie (średnia roczna beta, w nawiasie średni t-stat)", ""]
    for a, f, title in BETA_VIEWS:
        b = betas[(betas.asset == a) & (betas.factor == f)].copy()
        if b.empty:
            rep += [f"### {title}", "", "brak danych", ""]
            continue
        b["rok"] = pd.to_datetime(b["week"]).dt.year
        y = b.groupby("rok").agg(beta=("beta", "mean"), t=("t_stat", "mean"), tygodni=("beta", "size"))
        rep += [f"### {title}", "", "| rok | beta | t | |", "|---|---|---|---|"]
        scale = max(abs(y["beta"]).max(), 1e-12)
        for r, row in y.iterrows():
            bar = ("█" * int(round(10 * abs(row.beta) / scale))) or "·"
            rep.append(f"| {r} | {row.beta:+.4f} | {row.t:+.1f} | {'−' if row.beta < 0 else '+'}{bar} |")
        if f == "dfii10_chg":
            pre = b[(b.rok >= 2015) & (b.rok <= 2021)]["beta"].mean()
            post = b[b.rok >= 2023]["beta"].mean()
            tpost = b[b.rok >= 2023]["t_stat"].mean()
            last_y = y.index.max()
            peak = y["beta"].loc[2015:2021].abs().max()
            rep += ["", f"Osłabienie po 2022 (beta = zmiana log-ceny złota na +1 pp realnej stopy 10 l.): średnia 2015–2021 "
                    f"{pre:+.4f}, od 2023 {post:+.4f} ({abs(post) / abs(pre):.0%} poziomu sprzed 2022; średni t {tpost:+.1f}); "
                    f"w {last_y}: {y.loc[last_y, 'beta']:+.4f} ({abs(y.loc[last_y, 'beta']) / peak:.0%} szczytu 2015–2021). "
                    "Związek nadal ujemny i istotny, ale wyraźnie słabszy niż przed 2022."
                    if abs(post) < abs(pre) else "Brak osłabienia względem 2015–2021."]
        rep.append("")
    p = db.ROOT / "reports" / f"decomp-{date.today()}.md"
    p.write_text("\n".join(rep) + "\n")
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Etap 5 — portfel regułowy (docs/ETAP5-PLAN.md).

uv run src/backtest_rules.py backfill-4p   # dopisuje do runs 11 przebiegów 4P (liczą się do liczby prób), idempotentne
uv run src/backtest_rules.py prereg        # zapisuje hash definicji V1–V3 + reguły wyboru PRZED pierwszym przeliczeniem
uv run src/backtest_rules.py dev           # krok 3: część rozwojowa 2016-10-06…2024-10-05 -> runs (stage 5),
                                           #   tabela backtest_rules_dev, reports/etap5-rozwoj-{data}.md
uv run src/backtest_rules.py holdout --winner rowny_podzial_4
                                           # krok 4: JEDYNE otwarcie danych odłożonych 2024-10-06…2026-10-05
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, momentum as mm, rules as R, rules_eval as E  # noqa: E402
from ms.trading import Costs  # noqa: E402


def now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


def backfill_4p(con) -> int:
    """Przebiegi 4P (tabela backtest_momentum) jako próby w runs — wcześniej ich tam nie było."""
    bm = con.execute("SELECT wariant, start, \"end\", built_at, zwrot_roczny, max_obsunięcie FROM backtest_momentum").df()
    c = Costs()
    added = 0
    for r in bm.itertuples(index=False):
        run_id = f"4P-{r.wariant}-{pd.Timestamp(r.built_at):%Y%m%d}"
        if con.execute("SELECT count(*) FROM runs WHERE run_id=?", [run_id]).fetchone()[0]:
            continue
        lb = next((k for k in mm.LOOKBACK if r.wariant.startswith(f"momentum_{k}")), None)
        params = {"wariant": r.wariant, "okno": lb, "ochronny": r.wariant.endswith("_ochronny"),
                  "start": str(pd.Timestamp(r.start).date()), "end": str(pd.Timestamp(r.end).date()),
                  "koszty": c.__dict__, "zwrot_roczny": r.zwrot_roczny, "max_obsuniecie": r.max_obsunięcie}
        con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                    [run_id, pd.Timestamp(r.built_at), "PORTFEL", "4P", json.dumps(params, default=float),
                     (pd.Timestamp(r.end) - pd.Timestamp(r.start)).days,
                     f"dopisane wstecznie w etapie 5 ({now().date()}); przebieg 4P z {pd.Timestamp(r.built_at):%Y-%m-%d %H:%M}"])
        added += 1
    return added


def prereg(con) -> str:
    h = R.definitions_hash()
    rows = con.execute("SELECT params FROM runs WHERE stage='5-prereg'").fetchall()
    if any(json.loads(p[0])["hash"] == h for p in rows):
        print(f"prerejestracja {h} już jest — bez zmian")
        return h
    done = con.execute("SELECT count(*) FROM runs WHERE stage IN ('5', '5-holdout')").fetchone()[0]
    if done:
        raise SystemExit("są już przeliczenia etapu 5 — nowa definicja = nowa próba z wpisem w DECISIONS, nie cicha prerejestracja")
    con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                [f"5-prereg-{h}", now(), "PORTFEL", "5-prereg",
                 json.dumps({"hash": h, "definicja": R.DEFINITION}, ensure_ascii=False), 0,
                 "prerejestracja przed pierwszym przeliczeniem (definicje V1–V3, porównania, okresy, reguła wyboru D7)"])
    print(f"zapisano prerejestrację {h}")
    return h


BENCH = {"rowny_podzial_4": lambda b, s, e, c: mm.run_equal_weight(b, s, e, costs=c),
         "lokata": lambda b, s, e, c: mm.run_deposit(b, s, e, costs=c),
         "kup_i_trzymaj_XAU": lambda b, s, e, c: mm.run_buy_hold(b, "XAU", s, e, costs=c),
         "momentum_1m": lambda b, s, e, c: mm.run_momentum(b, "1m", False, s, e, costs=c)}
WINDOWS = ["2016-10-06", "2018-10-06", "2020-10-06", "2022-10-06", "2024-10-06"]
FULL4_FROM = "2018-09-01"   # od tego miesiąca wszystkie 4 aktywa mają historię na σ i trend (D10)


def run_dev(con) -> dict:
    return run_period(con, R.DEV_START, R.DEV_END)


def run_period(con, s, e, key: R.HoldoutKey | None = None, windows=WINDOWS, sub_from: str | None = FULL4_FROM) -> dict:
    """Wszystkie przebiegi (V1–V3, porównania, koszty x1 i x2) dla okresu [s, e] — ten sam kod dla części rozwojowej
    i odłożonej."""
    h = R.definitions_hash()
    pre = con.execute("SELECT params FROM runs WHERE stage='5-prereg'").fetchall()
    if not any(json.loads(p[0])["hash"] == h for p in pre):
        raise SystemExit("brak prerejestracji bieżących definicji — najpierw prereg")
    data = R.RuleData.load(con)
    book = data.book
    out = {"paths": {}, "rows": [], "logs": {}}
    for tag, c in (("x1", Costs()), ("x2", R.costs_x2())):
        dep = mm.run_deposit(book, s, e, costs=c).values
        res = {}
        for v in R.VARIANTS:
            r, log = R.run_rules(data, v, s, e, costs=c, holdout=key)
            res[v] = r
            out["logs"][(v, tag)] = log
        for name, f in BENCH.items():
            res[name] = f(book, s, e, c)
        if tag == "x1":   # pozostałe próby 4P — tylko do N = 12 w Deflated Sharpe i PBO
            for lb, prot in mm.VARIANTS:
                n = mm.variant_name(lb, prot)
                if n not in res:
                    res[n] = mm.run_momentum(book, lb, prot, s, e, costs=c)
        for name, r in res.items():
            row = E.summary(name, r.values, dep, r.final_liq, r.costs, r.tax, r.switches)
            row["koszty_wersja"] = tag
            out["rows"].append(row)
            out["paths"][(name, tag)] = r.values
        out[f"dep_{tag}"] = dep
    df = pd.DataFrame(out["rows"])
    x1 = df[df.koszty_wersja == "x1"].set_index("wariant")
    cand = [*R.VARIANTS, "rowny_podzial_4", *[mm.variant_name(lb, p) for lb, p in mm.VARIANTS]]
    ex = pd.DataFrame({n: E.monthly(out["paths"][(n, "x1")]) - E.monthly(out["dep_x1"]) for n in cand})
    sr_m = (ex.mean() / ex.std(ddof=1)).to_numpy()
    dsr = {}
    for n in [*R.VARIANTS, *BENCH]:
        if n == "lokata":
            continue
        dsr[n] = E.deflated_sharpe(x1.loc[n, "sharpe"] / np.sqrt(12), int(x1.loc[n, "miesiace"]), x1.loc[n, "skosnosc"],
                                   x1.loc[n, "kurtoza"], sr_m)[0]
    df["dsr"] = [dsr.get(n) if t == "x1" else None for n, t in zip(df.wariant, df.koszty_wersja)]
    out["pbo"] = E.pbo(ex)
    out["n_trials"] = len(cand)
    out["sr0_ann"] = E.deflated_sharpe(0, len(ex), 0, 3, sr_m)[1] * np.sqrt(12)
    out["df"] = df
    win, why = E.select_winner(x1, df[df.koszty_wersja == "x2"].set_index("wariant"))
    out["winner"], out["why"] = win, why
    main = [*R.VARIANTS, *BENCH]
    out["windows"] = {n: E.windows(out["paths"][(n, "x1")], out["dep_x1"], windows) for n in main if n != "lokata"}
    sub = {}
    for n in (main if sub_from else []):
        v = out["paths"][(n, "x1")]
        v, d = v[v.index >= sub_from], out["dep_x1"][out["dep_x1"].index >= sub_from]
        sub[n] = {"sharpe": E.sharpe(E.monthly(v) - E.monthly(d)), "max_obsuniecie": E.max_drawdown(v),
                  "zwrot_roczny": (v.iloc[-1] / v.iloc[0]) ** (365.25 / (v.index[-1] - v.index[0]).days) - 1}
    out["sub"] = sub
    out["hash"] = h
    out["period"] = (s, e)
    return out


def save_dev(con, out: dict) -> None:
    df, h = out["df"], out["hash"]
    started = now()
    for r in df.itertuples(index=False):
        if r.wariant not in (*R.VARIANTS, *BENCH):
            continue   # próby 4P są już w runs (stage 4P); tu tylko liczone do N
        run_id = f"5-dev-{r.wariant}-{r.koszty_wersja}-{h}"
        if con.execute("SELECT count(*) FROM runs WHERE run_id=?", [run_id]).fetchone()[0]:
            continue
        params = {"wariant": r.wariant, "koszty": r.koszty_wersja, "okres": [str(R.DEV_START.date()), str(R.DEV_END.date())],
                  "hash": h if r.wariant in R.VARIANTS else "porównanie (ms.momentum, jak 4P)",
                  "sharpe": r.sharpe, "max_obsuniecie": r.max_obsuniecie, "na_reke": r.na_reke}
        con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                    [run_id, started, "PORTFEL", "5", json.dumps(params, default=float), int(r.miesiace),
                     f"etap 5 krok 3: część rozwojowa, koszty {r.koszty_wersja}"])
    con.register("d", df.assign(built_at=started, hash=h))
    con.execute("DROP TABLE IF EXISTS backtest_rules_dev")
    con.execute("CREATE TABLE backtest_rules_dev AS SELECT * FROM d")
    con.unregister("d")


def _f(x, kind="num"):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    if kind == "pct":
        return f"{x:+.1%}".replace(".", ",")
    if kind == "zl":
        return f"{x:,.0f} zł".replace(",", " ")
    if kind == "p":   # DSR/PBO: 3 miejsca — 0,9475 nie może wyglądać jak próg 0,95
        return f"{x:.3f}".replace(".", ",")
    return f"{x:.2f}".replace(".", ",")


def report(out: dict) -> Path:
    from datetime import date

    df = out["df"]
    main = [*R.VARIANTS, *BENCH]
    x1 = df[df.koszty_wersja == "x1"].set_index("wariant").loc[main]
    x2 = df[df.koszty_wersja == "x2"].set_index("wariant").loc[main]
    L = [f"# Etap 5 — portfel regułowy: część rozwojowa {R.DEV_START.date()} … {R.DEV_END.date()} (1000 zł)", "",
         f"> **Ostrzeżenia.** (1) Wynik backtestu NIE uprawnia do prawdziwych pieniędzy (D11). (2) Liczba prób w tej rodzinie: "
         f"**N = {out['n_trials']}** (8 momentum z 4P + równy podział + 3 warianty) — Deflated Sharpe to uwzględnia. "
         f"(3) Sharpe z backtestu na żywo spada zwykle 2–4× (ZASADY cz. 4) — patrz kolumny „po cięciu”. "
         f"(4) BTC/ETH wchodzą do portfela dopiero ~2018-08 (ceny od 2017-08-17), wcześniej portfel = XAG + WTI.", "",
         f"Reguły zamrożone przed liczeniem: prerejestracja `{out['hash']}` w runs. Dane odłożone (2024-10-06 … 2026-10-05) "
         "nie były liczone.", "",
         "## Wynik (koszty jak 4P)", "",
         "| wariant | na rękę | zwrot roczny | Sharpe | po cięciu 2× / 3× / 4× | t | Deflated Sharpe | maks. obsunięcie | najdłużej pod kreską | najgorszy miesiąc | najgorszy rok | rebalanse | koszty | podatek |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in x1.iterrows():
        L.append(f"| {n} | {_f(r.na_reke, 'zl')} | {_f(r.zwrot_roczny, 'pct')} | {_f(r.sharpe)} | "
                 f"{_f(r.sharpe_po_cieciu_2)} / {_f(r.sharpe_po_cieciu_3)} / {_f(r.sharpe_po_cieciu_4)} | {_f(r.t)} | "
                 f"{_f(r.dsr, 'p')} | {_f(r.max_obsuniecie, 'pct')} | {r.najdluzej_pod_kreska_dni} dni | "
                 f"{_f(r.najgorszy_miesiac, 'pct')} | {_f(r.najgorszy_rok, 'pct')} | {r.rebalanse} | {_f(r.koszty, 'zl')} | {_f(r.podatek, 'zl')} |")
    L += ["", "Sharpe = miesięczne zwroty konta w PLN ponad lokatę, w skali roku. t = Sharpe × √lat (próg z ZASAD: t > 3). "
          "Deflated Sharpe ≥ 0,95 = wynik odróżnialny od najlepszego z N prób bez przewagi. Na rękę = po sprzedaży wszystkiego "
          "i podatku za ostatni rok.", "",
          "## Koszty ×2", "", "| wariant | na rękę | zwrot roczny | Sharpe | maks. obsunięcie | koszty |", "|---|---|---|---|---|---|"]
    for n, r in x2.iterrows():
        L.append(f"| {n} | {_f(r.na_reke, 'zl')} | {_f(r.zwrot_roczny, 'pct')} | {_f(r.sharpe)} | {_f(r.max_obsuniecie, 'pct')} | {_f(r.koszty, 'zl')} |")
    p, nsplit = out["pbo"]
    L += ["", "## Przeuczenie wyboru (PBO)", "",
          f"PBO = **{_f(p, 'p')}** ({nsplit} podziałów CSCV, 8 bloków po ~12 mies., {out['n_trials']} kandydatów). Próg z ZASAD: < 0,5. "
          "Przy 12 kandydatach PBO jest zgrubne. Oczekiwany najlepszy Sharpe z N prób bez przewagi (SR*): "
          f"{_f(out['sr0_ann'])} rocznie.", "",
          "## Stabilność w czasie (okna 2-letnie, ta sama ścieżka konta)", "",
          "| wariant | " + " | ".join(w["okno"] for w in next(iter(out["windows"].values()))) + " |",
          "|---|" + "---|" * (len(WINDOWS) - 1)]
    for n, ws in out["windows"].items():
        L.append(f"| {n} | " + " | ".join(f"Sharpe {_f(w['sharpe'])}, obs. {_f(w['max_obsuniecie'], 'pct')}" for w in ws) + " |")
    L += ["", f"## Podokres z kompletem 4 aktywów ({FULL4_FROM[:7]} … {R.DEV_END.date()})", "",
          "| wariant | zwrot roczny | Sharpe | maks. obsunięcie |", "|---|---|---|---|"]
    for n, r in out["sub"].items():
        L.append(f"| {n} | {_f(r['zwrot_roczny'], 'pct')} | {_f(r['sharpe'])} | {_f(r['max_obsuniecie'], 'pct')} |")
    v3 = out["logs"][("iv_filtr_ovx", "x1")]
    share = (v3["sigma_src_WTI"] == "ovx").mean()
    L += ["", "## Zwycięzca wg reguły D7 (ustalonej przed wynikami)", ""] + [f"- {w}" for w in out["why"]] + [
          "", f"**Konto „system” będzie wykonywać: `{out['winner']}`** (po jednorazowym otwarciu danych odłożonych — krok 4).", "",
          "## Uwagi", "",
          f"- V3: σ ropy z OVX w {share:.0%} decyzji (reszta: σ z historii — brak OVX/k albo za krótka historia ilorazu).",
          "- **Ograniczenie wyceny ropy:** ETC ropy wyceniane ruchem ceny spot WTI (jak 4P). Prawdziwe ETC tracą na rolowaniu "
          "kontraktów (ZASADY cz. 2: USO vs BNO), a 2020-04-20 spot był ujemny (−36,98 USD; wycena obcięta do 0 — jednodniowy "
          "spadek konta, odrobiony w 3 dni). Warianty inverse-vol trzymają więcej ropy niż równy podział, więc to uproszczenie "
          "może je zawyżać bardziej. Nie zmieniane po zobaczeniu wyników.",
          "- Okna 2-letnie i podokres liczone na tej samej ścieżce konta (bez restartu); koszty i podatek jak w całości.",
          "- Uproszczenia jak w 4P: ETF/ETC wyceniane ruchem spot, podatek do potwierdzenia u doradcy (src/ms/tax.py)."]
    path = db.ROOT / "reports" / f"etap5-rozwoj-{date.today()}.md"
    path.write_text("\n".join(L) + "\n")
    return path


HOLD_WINDOWS = ["2024-10-06", "2025-10-06", "2026-10-06"]


def run_holdout(con, winner: str) -> dict:
    dev = con.execute("SELECT * FROM backtest_rules_dev").df()
    x1, x2 = (dev[dev.koszty_wersja == k].set_index("wariant") for k in ("x1", "x2"))
    d7, _ = E.select_winner(x1, x2)
    if winner != d7:
        raise SystemExit(f"zwycięzca {winner!r} niezgodny z regułą D7 na części rozwojowej ({d7!r}) — odmowa")
    key = R.open_holdout(con, winner)            # wpis w runs PRZED liczeniem
    out = run_period(con, R.HOLDOUT_START, R.HOLDOUT_END, key, windows=HOLD_WINDOWS, sub_from=None)
    out["dev"] = dev
    out["winner_d7"] = winner
    return out


def save_holdout(con, out: dict) -> None:
    df, h = out["df"], out["hash"]
    started = now()
    for r in df.itertuples(index=False):
        if r.wariant not in (*R.VARIANTS, *BENCH):
            continue
        run_id = f"5-odlozone-{r.wariant}-{r.koszty_wersja}-{h}"
        if con.execute("SELECT count(*) FROM runs WHERE run_id=?", [run_id]).fetchone()[0]:
            continue
        params = {"wariant": r.wariant, "koszty": r.koszty_wersja,
                  "okres": [str(R.HOLDOUT_START.date()), str(R.HOLDOUT_END.date())], "hash": h,
                  "sharpe": r.sharpe, "max_obsuniecie": r.max_obsuniecie, "na_reke": r.na_reke}
        con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                    [run_id, started, "PORTFEL", "5-odlozone", json.dumps(params, default=float), int(r.miesiace),
                     f"etap 5 krok 4: dane odłożone (jedyne otwarcie), koszty {r.koszty_wersja}"])
    con.register("d", df.assign(built_at=started, hash=h))
    con.execute("DROP TABLE IF EXISTS backtest_rules_holdout")
    con.execute("CREATE TABLE backtest_rules_holdout AS SELECT * FROM d")
    con.unregister("d")
    w = df[(df.koszty_wersja == "x1") & (df.wariant == out["winner_d7"])].iloc[0]
    R.close_holdout(con, {"zwyciezca": out["winner_d7"], "sharpe": w.sharpe, "max_obsuniecie": w.max_obsuniecie,
                          "na_reke": w.na_reke, "miesiace": int(w.miesiace)})


def report_holdout(out: dict) -> Path:
    from datetime import date

    df, dev = out["df"], out["dev"]
    main = [*R.VARIANTS, *BENCH]
    x1 = df[df.koszty_wersja == "x1"].set_index("wariant").loc[main]
    x2 = df[df.koszty_wersja == "x2"].set_index("wariant").loc[main]
    d1 = dev[dev.koszty_wersja == "x1"].set_index("wariant")
    w = out["winner_d7"]
    limit = {n: 1.5 * d1.loc[n, "max_obsuniecie"] for n in main if n != "lokata"}
    L = [f"# Etap 5 — dane odłożone {R.HOLDOUT_START.date()} … {R.HOLDOUT_END.date()} (1000 zł od nowa)", "",
         f"> **Jedyne otwarcie** (wpis `5-holdout` w runs przed liczeniem; reguły `{out['hash']}`). Zwycięzca wybrany regułą "
         f"D7 na części rozwojowej PRZED otwarciem: **`{w}`**. Po otwarciu żadnych zmian reguł. Wynik NIE uprawnia do prawdziwych "
         "pieniędzy (D11).", "",
         "> **Te 2 lata nie są dziewicze (D8):** backtest 4P (równy podział, momentum) i wybór mistrza OVX w 3A objęły ten okres. "
         "Nowe warianty V1–V3 nie były na nim liczone. Czysty test = konta „system” od 2026-10-07.", "",
         "## Wynik (koszty jak 4P) — obok część rozwojowa", "",
         "| wariant | na rękę | zwrot roczny | Sharpe | Sharpe (rozwój) | maks. obsunięcie | obsunięcie (rozwój) | próg wyłączenia D9 | najgorszy miesiąc | rebalanse | koszty | podatek |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in x1.iterrows():
        lim = limit.get(n)
        L.append(f"| {'**' + n + '**' if n == w else n} | {_f(r.na_reke, 'zl')} | {_f(r.zwrot_roczny, 'pct')} | {_f(r.sharpe)} | "
                 f"{_f(d1.loc[n, 'sharpe'])} | {_f(r.max_obsuniecie, 'pct')} | {_f(d1.loc[n, 'max_obsuniecie'], 'pct')} | "
                 f"{('nieosiągalny (> 100%)' if lim <= -1 else _f(lim, 'pct')) if lim is not None else '—'} | {_f(r.najgorszy_miesiac, 'pct')} | {r.rebalanse} | "
                 f"{_f(r.koszty, 'zl')} | {_f(r.podatek, 'zl')} |")
    L += ["", "Próg wyłączenia D9 = 1,5 × najgorsze obsunięcie z części rozwojowej (dla kont „system”).", "",
          "## Koszty ×2", "", "| wariant | na rękę | zwrot roczny | Sharpe | maks. obsunięcie |", "|---|---|---|---|---|"]
    for n, r in x2.iterrows():
        L.append(f"| {n} | {_f(r.na_reke, 'zl')} | {_f(r.zwrot_roczny, 'pct')} | {_f(r.sharpe)} | {_f(r.max_obsuniecie, 'pct')} |")
    L += ["", "## Okna roczne (ta sama ścieżka konta)", "",
          "| wariant | " + " | ".join(x["okno"] for x in next(iter(out["windows"].values()))) + " |",
          "|---|" + "---|" * (len(HOLD_WINDOWS) - 1)]
    for n, ws in out["windows"].items():
        L.append(f"| {n} | " + " | ".join(f"Sharpe {_f(x['sharpe'])}, zwrot {_f(x['zwrot'], 'pct')}, obs. "
                                          f"{_f(x['max_obsuniecie'], 'pct')}" for x in ws) + " |")
    _, why = out["winner"], out["why"]
    L += ["", "## Reguła D7 zastosowana do danych odłożonych (tylko informacja — wyboru to nie zmienia)", ""] + \
         [f"- {x}" for x in why] + [
         "", "## Uwagi", "",
         "- 24 miesiące to mało: Sharpe z 2 lat ma błąd standardowy ok. ±0,8 (przy Sharpe ~0,9) — różnice między wariantami w tej tabeli są w granicach "
         "szczęścia. Deflated Sharpe i PBO nie są tu liczone (za krótki okres).",
         "- Wycena ropy spotem (jak 4P i część rozwojowa) — ograniczenie opisane w raporcie części rozwojowej.",
         "- Każdy przebieg zaczyna od 1000 zł 2024-10-06 (σ i trend z historii sprzed startu)."]
    path = db.ROOT / "reports" / f"etap5-odlozone-{date.today()}.md"
    path.write_text("\n".join(L) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backfill-4p", "prereg", "dev", "holdout"])
    ap.add_argument("--winner")
    a = ap.parse_args()
    con = db.connect()
    if a.cmd == "backfill-4p":
        print(f"dopisano {backfill_4p(con)} przebiegów 4P do runs")
    elif a.cmd == "prereg":
        prereg(con)
    elif a.cmd == "holdout":
        if not a.winner:
            raise SystemExit("podaj --winner (zwycięzca reguły D7)")
        out = run_holdout(con, a.winner)
        save_holdout(con, out)
        print(report_holdout(out))
    else:
        out = run_dev(con)
        save_dev(con, out)
        print(report(out))
        print("zwycięzca (D7):", out["winner"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

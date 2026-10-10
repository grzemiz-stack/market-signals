"""Etap 4H: testy hipotez z mapy -> reports/hipotezy-{data}.md, tabela hypothesis_status, wpis w runs,
blok statusów w docs/MAPA-ZALEZNOSCI.md (między znacznikami; tekst z literatury nietknięty).

uv run src/test_hypotheses.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, hypotheses as hp  # noqa: E402

MAPA = db.ROOT / "docs" / "MAPA-ZALEZNOSCI.md"
# hipotezy jeszcze nietestowane — status wg planu (docs/ETAP4H-PLAN.md)
PENDING = {
    "G8": ("brak danych", "sankcje: GDELT ma kod 163, ale zamrożenie rezerw 2022 to jedno zdarzenie — do decyzji, czy testować sankcje ogólnie"),
    "O15": ("brak danych", "sankcje: jak G8; dyskonto Urals płatne"),
    "O6": ("brak danych", "konsensus płatny; badanie zdarzeń na proxy (zmiana − sezon) nie było w zakresie tej partii"),
    **{i: ("brak danych", "tylko ręcznie: skrzynka / lista do dostarczenia") for i in
       ("G7", "G9", "S7", "S9", "S11", "O17", "C2", "C3", "C8", "C10", "C16")},
    **{i: ("nie do sprawdzenia", "dane roczne albo ≤ 3 zdarzenia") for i in ("G12", "S4", "S5", "S6", "S8", "O11", "C15")},
}
ASSET_OF = {"G": "XAU", "S": "XAG", "O": "WTI/BRENT", "C": "BTC/ETH"}


def fmt(x, d=3):
    return "—" if x is None or not np.isfinite(x) else f"{x:+.{d}f}".replace(".", ",")


def pct(x):
    return "—" if x is None or not np.isfinite(x) else f"{x:.0%}"


def definitions_hash() -> str:
    """Hash PEŁNYCH definicji testów (ID, aktywo, typ, czynnik, cel, horyzont, zdarzenia, okno, progi) — zmiana definicji
    = nowa próba w `runs` (do korekty wielokrotnych testów), nie rerun."""
    from ms import hyp_events as he
    defs = [(s.id, s.asset, s.variant, s.kind, s.sign, s.factor, s.target, s.h, s.freq, s.events, s.k, s.start_offset)
            for s in hp.SPECS]
    cfg = {"defs": defs, "q_bh": hp.Q_BH, "last": hp.LAST, "spike_q": he.SPIKE_Q, "decluster": he.DECLUSTER}
    return hashlib.sha256(json.dumps(cfg, default=str).encode()).hexdigest()[:16]


def ids_in_map() -> list[str]:
    """ID hipotez z TEKSTU LITERATURY (bez generowanego bloku statusów — inaczej każdy przebieg dublował wiersze)."""
    text = re.sub(r"<!-- STATUS:START -->.*?<!-- STATUS:END -->", "", MAPA.read_text(encoding="utf-8"), flags=re.S)
    return list(dict.fromkeys(re.findall(r"^\| ([GSOC]\d+) \|", text, flags=re.M)))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--note", help="np. rerun_after_pit_fix_fred")
    args = ap.parse_args()
    con = db.connect()
    run_id = uuid.uuid4().hex[:12]
    today = date.today()
    from ms import hyp_events as he
    from ms.prices import price_frame

    assets = sorted({s.asset for s in hp.SPECS if s.kind != "T"})
    frames = {a: hp.weekly(con, a) for a in assets}
    monthly = {a: he.monthly_frame(con, a) for a in assets}
    pfs = {a: price_frame(con, a) for a in assets}
    results = []
    for sp in hp.SPECS:
        if sp.freq == "E":
            results.append(hp.test_event(sp, con, pfs[sp.asset]))
        else:
            results.append(hp.test_spec(sp, (monthly if sp.freq == "M" else frames).get(sp.asset, pd.DataFrame())))
    # BH na całej tabeli testów głównych (B, P, S, Z, ZR); N i T poza korektą. Zdarzenia: test główny = wszystkie zdarzenia.
    main_p = lambda r: r.p_full if r.spec.freq == "E" else r.p_last  # noqa: E731
    main_idx = [i for i, r in enumerate(results) if r.spec.kind in ("B", "P", "S", "Z", "ZR") and np.isfinite(main_p(r))]
    for i, p in zip(main_idx, hp.bh([main_p(results[i]) for i in main_idx])):
        results[i].p_bh = p
    for r in results:
        hp.classify(r)
        r.regime = hp.describe_event(r) if r.spec.freq == "E" else hp.describe_regime(r)
        if r.spec.freq == "M":
            r.extra = ("; ".join(x for x in (r.extra, "miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — "
                                             "jako cecha wymaga wersji PIT") if x))
        if r.spec.id in hp.CONSTRUCTIVE and r.status == "potwierdzona":
            r.status = "konstrukcyjna"
            r.extra = hp.CONSTRUCTIVE[r.spec.id]
    # kandydaci: tylko potwierdzone; predykcyjne (P) dodatkowo test poza próbą (estymacja do 2023, test 2024–2026)
    oos = {}
    for r in results:
        r.candidate = r.status == "potwierdzona" and r.spec.kind != "T"
        r.use = hp.candidate_use(r.spec)
        if r.candidate and r.use == "prognoza":
            o = (hp.oos_event(r.spec, con, pfs[r.spec.asset]) if r.spec.freq == "E" else hp.oos_test(r.spec, frames[r.spec.asset]))
            oos[(r.spec.id, r.spec.asset, r.spec.variant)] = o
            r.candidate = o["ok"]
            r.extra = "; ".join(x for x in (r.extra, f"test poza próbą: {'zaliczony' if o['ok'] else 'NIEZALICZONY — ' + o['why']}") if x)
        if r.spec.kind == "T" and r.status == "potwierdzona":
            r.extra += "; już w rejestrze jako model (iv_*), nie osobna cecha"
    # O18: przepisane z 3A
    for r in results:
        if r.spec.kind == "T":
            e = con.execute("SELECT bss, ci_lo, ci_hi FROM baseline_eval WHERE aktywo=? AND model LIKE 'iv_%' "
                            "AND wariant='wszystkie' ORDER BY bss DESC LIMIT 1", [r.spec.asset]).fetchone()
            if e:
                r.status = "potwierdzona" if e[1] > 0 else "niepotwierdzona"
                r.extra = f"z 3A: najlepszy model implied vol BSS {fmt(e[0])} [{fmt(e[1])}; {fmt(e[2])}] (wybór na okresie testowym)"
            else:
                r.status = "brak danych"
    tests = sorted(f"{results[i].spec.id}{':' + results[i].spec.variant if results[i].spec.variant else ''}:{results[i].spec.asset}"
                   for i in main_idx)
    tests_hash = definitions_hash()
    prev = con.execute("SELECT params FROM runs WHERE stage='4H' ORDER BY started_at DESC LIMIT 1").fetchone()
    note = "rerun (ta sama lista testów)" if prev and json.loads(prev[0]).get("hash") == tests_hash else "nowa lista testów"
    if args.note:
        note = f"{args.note}; {note}"
    con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                [run_id, pd.Timestamp.now(tz="UTC").tz_localize(None), "ALL", "4H",
                 json.dumps({"hash": tests_hash, "tests": tests, "q_bh": hp.Q_BH, "okno_glowne_tyg": hp.LAST}), len(tests), note])
    n_trials = con.execute("SELECT count(DISTINCT json_extract_string(params, '$.hash')) FROM runs WHERE stage='4H'").fetchone()[0]

    # tabela statusów
    con.execute("""CREATE TABLE IF NOT EXISTS hypothesis_status (id VARCHAR, asset VARCHAR, status VARCHAR, kind VARCHAR,
                   beta_3y DOUBLE, se_3y DOUBLE, p_3y DOUBLE, p_bh DOUBLE, beta_full DOUBLE, se_full DOUBLE, since DATE,
                   note VARCHAR, tested_at DATE, run_id VARCHAR)""")
    con.execute("ALTER TABLE hypothesis_status ADD COLUMN IF NOT EXISTS variant VARCHAR")
    con.execute("ALTER TABLE hypothesis_status ADD COLUMN IF NOT EXISTS candidate BOOLEAN")
    con.execute("ALTER TABLE hypothesis_status ADD COLUMN IF NOT EXISTS oos VARCHAR")
    rows = [(r.spec.id, r.spec.asset, r.status, r.spec.kind, r.beta_last, r.se_last, r.p_last, r.p_bh, r.beta_full,
             r.se_full, r.since.date() if r.since is not None else None, r.extra, today, run_id, r.spec.variant or None,
             bool(getattr(r, "candidate", False)),
             json.dumps(oos.get((r.spec.id, r.spec.asset, r.spec.variant)), default=float) if (r.spec.id, r.spec.asset, r.spec.variant) in oos else None)
            for r in results]
    tested = {r.spec.id for r in results}
    for i in ids_in_map():
        if i not in tested:
            st, nt = PENDING.get(i, ("brak danych", "nie zaplanowano"))
            rows.append((i, ASSET_OF[i[0]], st, "-", None, None, None, None, None, None, None, nt, today, run_id, None, False, None))
    con.executemany("""INSERT INTO hypothesis_status (id, asset, status, kind, beta_3y, se_3y, p_3y, p_bh, beta_full, se_full,
                       since, note, tested_at, run_id, variant, candidate, oos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)

    write_report(results, rows, today, run_id, len(tests), n_trials, note, oos)
    write_map_block(rows, results, today)
    return 0


def write_report(results, rows, today, run_id, n_tests, n_trials, note, oos):
    out = [f"# Hipotezy z mapy na naszych danych — {today}", "",
           f"Test główny: ostatnie {hp.LAST} tygodni; obok cała historia. Korekta Benjamini–Hochberg (q = {hp.Q_BH}) "
           f"na {n_tests} testach głównych (typy B, P, S). Liczba różnych list testów (prób) w `runs`: {n_trials} "
           f"(to uruchomienie: {note}, run_id `{run_id}`). Reguły statusów: docs/ETAP4H-PLAN.md. "
           "Typy: B współbieżna, P predykcyjna, S sezonowa, N „brak efektu”, T przepisana z 3A, Z badanie zdarzeń "
           "(CAR ponad losowe daty), ZR regresja CAR na wielkości zdarzenia. Zdarzenia: test główny na wszystkich zdarzeniach "
           "(w 3 latach za mało zdarzeń), obok podzbiór z 3 lat. Testy miesięczne (M): okna 12/36 mies., test główny 36 mies., "
           "wartości wg daty obserwacji. GDELT bez par USA–USA. Status `konstrukcyjna`: czynnik liczony z ceny aktywa "
           "(nie może być cechą).", "",
           "**Tylko `potwierdzona` może zostać kandydatem na cechę w rejestrze modeli (i nadal musi pobić mistrza).**", "",
           "Czas: kursy walut (DEX*) i VIX/GVZ/OVX znane w dniu notowania; rentowności Treasury (DGS*, DFII10, T10YIE) "
           "przy dacie publikacji (zwykle następny dzień roboczy) — w testach współbieżnych tydzień czynnika jest dla nich "
           "przesunięty o ok. 1 dzień względem tygodnia ceny (lekko zaniża bety G1, G2, S3).", "",
           "## Wyniki", "",
           "| ID | aktywo | hipoteza | typ | znak lit. | beta 3 lata [±2SE] | p | p po BH | beta cała historia [±2SE] | "
           "% okien 52 tyg. ze znakiem lit. (całość / 3 lata) | zmiana reżimu | **Status** |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        s = r.spec
        sign = {1: "+", -1: "−", 0: "±"}[s.sign] if s.kind != "N" else "≈0"
        b3 = f"{fmt(r.beta_last)} [{fmt(r.beta_last - 2 * r.se_last)}; {fmt(r.beta_last + 2 * r.se_last)}]" if np.isfinite(r.beta_last) else "—"
        bf = f"{fmt(r.beta_full)} [{fmt(r.beta_full - 2 * r.se_full)}; {fmt(r.beta_full + 2 * r.se_full)}]" if np.isfinite(r.beta_full) else "—"
        sh = f"{pct(r.share.get('52_cala_znak'))} / {pct(r.share.get('52_3lata_znak'))}" if s.sign else "—"
        reg = r.regime + (f"; {r.extra}" if r.extra else "")
        if s.freq == "E":
            b3 = f"{fmt(r.beta_last, 4)} ({r.n_last} zd.)" if np.isfinite(r.beta_last) else f"— ({r.n_last} zd.)"
            bf = (f"{fmt(r.beta_full, 4)} [{fmt(r.beta_full - 2 * r.se_full, 4)}; {fmt(r.beta_full + 2 * r.se_full, 4)}]"
                  if np.isfinite(r.se_full) else f"{fmt(r.beta_full, 4)} (p={fmt(r.p_full, 4)})")
        label = s.id + (f" ({s.variant})" if s.variant else "")
        cand = f" · kandydat ({r.use})" if getattr(r, "candidate", False) else ""
        out.append(f"| {label} | {s.asset} | {s.desc} | {s.kind} | {sign} | {b3} | {fmt(r.p_last if s.freq != 'E' else r.p_full, 4)} | "
                   f"{fmt(r.p_bh, 4)} | {bf} | {sh} | {reg} | **{r.status}**{cand} |")
    out += ["", "## Zmiana reżimu: beta 52-tygodniowa na koniec każdego roku", ""]
    for key in (("G1", "XAU"), ("G3", "XAU"), ("S1", "XAG"), ("O12", "WTI"), ("C1", "BTC"), ("C7", "BTC")):
        r = next((x for x in results if (x.spec.id, x.spec.asset) == key), None)
        if r is None or r.yearly is None:
            continue
        y = r.yearly
        scale = max(y["beta"].abs().max(), 1e-12)
        out += [f"### {key[0]} {key[1]} — {r.spec.desc}", "", "| rok | beta | ±2SE | istotna | |", "|---|---|---|---|---|"]
        for yr, row in y.iterrows():
            bar = ("█" * int(round(10 * abs(row.beta) / scale))) or "·"
            out.append(f"| {yr} | {fmt(row.beta)} | {fmt(2 * row.se)} | {'tak' if abs(row.beta) > 2 * row.se else 'nie'} | "
                       f"{'−' if row.beta < 0 else '+'}{bar} |")
        out.append("")
    out += ["## Kandydaci na cechy (tylko `potwierdzona`) i test poza próbą", "",
            "Predykcyjne (P i zdarzenia z oknem po dniu 0): estymacja do 2023, test 2024–2026 bez zmiany progów "
            "(znak z literatury, p < 0,10, R² poza próbą > 0; zdarzenia: >= 8 w okresie testowym).", "",
            "| ID | aktywo | beta do 2023 | beta 2024–2026 | p 2024–2026 | R² poza próbą | wynik |", "|---|---|---|---|---|---|---|"]
    for (i, a, v), o in oos.items():
        out.append(f"| {i} | {a} | {fmt(o.get('beta_train'))} | {fmt(o.get('beta_test'))} | {fmt(o.get('p_test'), 4)} | "
                   f"{fmt(o.get('r2_oos'), 4)} | {'zaliczony' if o['ok'] else 'NIEZALICZONY: ' + o['why']} |")
    cands = [r for r in results if getattr(r, "candidate", False)]
    out += ["", "Kandydaci po wszystkich filtrach (użycie: prognoza = czynnik znany przed oknem zwrotu; dekompozycja = "
            "zależność współbieżna, do pytania decomp_weekly): " + (", ".join(
                f"{r.spec.id}{' (' + r.spec.variant + ')' if r.spec.variant else ''} {r.spec.asset} [{r.use}]" for r in cands) or "brak") + ".", ""]
    out += ["## Pozostałe hipotezy z mapy (jeszcze nietestowane)", "", "| ID | aktywo | status | uwagi |", "|---|---|---|---|"]
    tested = {r.spec.id for r in results}
    out += [f"| {r[0]} | {r[1]} | {r[2]} | {r[11]} |" for r in rows if r[0] not in tested]
    p = db.ROOT / "reports" / f"hipotezy-{today}.md"
    p.write_text("\n".join(out) + "\n")
    print(p)


def write_map_block(rows, results, today):
    """Dopisuje/zastępuje tabelę statusów między znacznikami na końcu mapy. Nic poza blokiem się nie zmienia."""
    order = {i: k for k, i in enumerate(ids_in_map())}
    res = {(r.spec.id, r.spec.asset, r.spec.variant or None, r.spec.kind): r for r in results}
    lines = ["<!-- STATUS:START -->", "## Status testów (generowane przez src/test_hypotheses.py — nie edytować ręcznie)", "",
             f"Stan: {today}. Raport: reports/hipotezy-{today}.md. Test główny: ostatnie 3 lata; obok cała historia.", "",
             "| ID | aktywo | Status | beta 3 lata | beta cała historia | uwagi |", "|---|---|---|---|---|---|"]
    multi = pd.Series([(r[0], r[1], r[14]) for r in rows]).value_counts()
    for r in sorted(rows, key=lambda x: (order.get(x[0], 999), x[1], x[14] or "", x[3])):
        rr = res.get((r[0], r[1], r[14], r[3]))
        note = (rr.regime + (f"; {rr.extra}" if rr.extra else "")) if rr else r[11]
        # ta sama para ID × aktywo × wariant z kilkoma testami (np. G6: beta tygodniowa i zdarzenia) -> typ w etykiecie
        label = r[0] + (f" ({r[14]})" if r[14] else "") + (f" [{r[3]}]" if multi[(r[0], r[1], r[14])] > 1 else "")
        status = r[2] + (" · kandydat" if r[15] else "")
        lines.append(f"| {label} | {r[1]} | {status} | {fmt(r[4])} | {fmt(r[8])} | {note} |")
    lines.append("<!-- STATUS:END -->")
    text = MAPA.read_text(encoding="utf-8")
    block = "\n".join(lines) + "\n"
    pat = re.compile(r"<!-- STATUS:START -->.*?<!-- STATUS:END -->\n?", re.S)
    text = pat.sub(block, text) if pat.search(text) else text.rstrip("\n") + "\n\n" + block
    MAPA.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

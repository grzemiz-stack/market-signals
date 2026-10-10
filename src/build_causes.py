"""Etap 4N-etykiety: przyczyny dużych ruchów (docs/ETAP4N-PLAN.md). Uruchamiane na żądanie, nie w launchd.

    uv run --frozen src/build_causes.py fetch       # P1–P5, P7 + P8 (ref/crypto_events.csv) -> data/raw/causes + tabele
    uv run --frozen src/build_causes.py calendar    # duże ruchy + etykiety z kalendarza -> move_causes + raport pokrycia
    uv run --frozen src/build_causes.py e2-sheet    # ref/e2_gold_to_label.csv do oznaczenia (NIE nadpisuje istniejącego)
    uv run --frozen src/build_causes.py e2-xlsx     # z CSV -> ref/e2_gold_to_label.xlsx z listami rozwijanymi (NIE nadpisuje)
    uv run --frozen src/build_causes.py e2-check    # wczytuje oznaczony xlsx, sprawdza zgodność z CSV i kody

Etykiety przyczyn: tylko wyjaśnianie i badania zdarzeń, NIGDY cecha prognozy.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from ms import causes, db  # noqa: E402
from ms.cause_sources import REF, fetch_all  # noqa: E402

LOG = db.ROOT / "logs" / "causes.log"
REPORTS = db.ROOT / "reports"
E2_FILE = REF / "WYCOFANE" / "e2_gold_to_label.csv"   # WYCOFANE 2026-10-07 (arkusz usunięty z kopii publicznej)
E2_XLSX = REF / "WYCOFANE" / "e2_gold_to_label.xlsx"


def fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


def cmd_fetch(con) -> int:
    import snapshot_raw as sr

    n = fetch_all(con, sr.Store(date.today()))
    print(json.dumps(n, ensure_ascii=False))
    return 0


def cmd_calendar(con) -> int:
    h = causes.definitions_hash()
    run_id = f"4N-cal-{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%S}"
    prev = con.execute("SELECT params FROM runs WHERE stage='4N-cal' ORDER BY started_at DESC LIMIT 1").fetchone()
    before = con.execute("SELECT count(*) FROM move_causes").fetchone()[0]
    lab, mv = causes.label_calendar(con, run_id)
    added = con.execute("SELECT count(*) FROM move_causes").fetchone()[0] - before
    note = "rerun (te same definicje)" if prev and json.loads(prev[0]).get("hash") == h else "nowe definicje"
    if prev and json.loads(prev[0]).get("hash") != h:
        note += " (kalendarz -> kandydat, validated=false; decyzja 2026-10-06)"
    con.execute("INSERT INTO runs (run_id, started_at, asset, stage, params, n_eval, note) VALUES (?,?,?,?,?,?,?)",
                [run_id, pd.Timestamp.now(tz="UTC").tz_localize(None), "ALL", "4N-cal",
                 json.dumps({"hash": h, "defs": causes.DEFS}, default=str), len(lab), f"{note}; dopisano {added} wierszy"])
    report(con, lab, mv, added)
    return 0


def report(con, lab: pd.DataFrame, mv: pd.DataFrame, added: int) -> None:
    today = date.today().isoformat()
    L = [f"# Przyczyny dużych ruchów — kandydaci z kalendarza ({today})", "",
         "Etap 4N, krok 1–2 (bez LLM). Plan: docs/ETAP4N-PLAN.md. **Etykiety przyczyn to wiedza po fakcie: tylko do "
         "wyjaśniania i badań zdarzeń, nigdy cecha prognozy.**", "",
         f"Duży ruch: |log-zwrot| > {fmt(causes.Z_MIN, 1)} σ (σ z {causes.SIGMA_WIN} poprzednich sesji). Zdarzenie -> dzień 0 = "
         "pierwsze zamknięcie znane po zdarzeniu; trafienie w dniu 0 (pewność 1,0) lub +1 (0,6).", "",
         "**Każda etykieta z kalendarza to KANDYDAT** (`status='kandydat'`, `validated=false`): w statusie pokazywana jako "
         "„tego dnia było: …”, nigdy jako przyczyna. Przyczynę potwierdza tekst — zwalidowany Qwen albo człowiek.", "",
         f"Ten przebieg dopisał {added} wierszy do `move_causes` (0 = nic nowego, idempotencja).", "",
         "## Pokrycie na aktywo", "",
         "| aktywo | okres | duże ruchy | z kandydatem z kalendarza | % | w tym dzień 0 | bez kandydata |",
         "|---|---|---|---|---|---|---|"]
    for a in causes.ASSETS:
        m = mv[mv.asset == a]
        la = lab[lab.asset == a] if not lab.empty else lab
        n_lab = la["day"].nunique() if len(la) else 0
        n0 = la[la.offset == 0]["day"].nunique() if len(la) else 0
        per = f"{m['day'].min()}…{m['day'].max()}" if len(m) else "—"
        L.append(f"| {a} | {per} | {len(m)} | {n_lab} | {fmt(100 * n_lab / max(len(m), 1), 0)} | {n0} | {len(m) - n_lab} |")
    L += ["", "## Kandydaci wg typu zdarzenia (rank 1)", "", "| aktywo | typ | kod kandydata | dni |", "|---|---|---|---|"]
    r1 = lab[lab["rank"] == 1]
    for (a, k, c), g in r1.groupby(["asset", "kind", "cause"]):
        L.append(f"| {a} | {k} | `{c}` | {g['day'].nunique()} |")
    # chronologie ropy: dni z wpisem (kod przyczyny nada człowiek (złoto E2) albo zwalidowany Qwen)
    ch = con.execute("""SELECT source, event_date FROM cause_events WHERE source IN ('eia_chron','wiki_chron')
                        AND date_precision='day'""").df()
    ch["event_date"] = pd.to_datetime(ch["event_date"]).dt.date
    L += ["", "## Chronologie ropy (P4, P5): duże ruchy WTI/BRENT z wpisem tego samego dnia lub dzień wcześniej", "",
          "Wpisy nie mają kodu przyczyny — kod nada człowiek (złoto E2) albo zwalidowany Qwen. Tu tylko liczba dopasowań.", "",
          "| aktywo | źródło | lata wpisów | duże ruchy w tych latach | z wpisem |", "|---|---|---|---|---|"]
    for a in causes.OIL:
        m = mv[mv.asset == a]
        for src_ in ("eia_chron", "wiki_chron"):
            ds = set(ch[ch.source == src_]["event_date"])
            near = ds | {d + timedelta(days=1) for d in ds}
            y0, y1 = min(ds).year, max(ds).year
            m_in = m[[y0 <= d.year <= y1 for d in m["day"]]]
            L.append(f"| {a} | {src_} | {y0}–{y1} | {len(m_in)} | {sum(d in near for d in m_in['day'])} |")
    src = con.execute("""SELECT source, count(*) n, min(event_date)::VARCHAR od, max(event_date)::VARCHAR do_, any_value(license) lic
                         FROM cause_events GROUP BY 1 ORDER BY 1""").df()
    L += ["", "## Źródła w `cause_events`", "", "| źródło | wpisy | od | do | licencja |", "|---|---|---|---|---|"]
    for r in src.itertuples():
        L.append(f"| {r.source} | {r.n} | {r.od} | {r.do_} | {r.lic} |")
    nb = con.execute("SELECT count(*), count(DISTINCT date), min(date), max(date) FROM bbds_codings").fetchone()
    L.append(f"| bbds_codings | {nb[0]} kodowań, {nb[1]} dni | {nb[2]} | {nb[3]} | academic (niepotwierdzona) |")
    unv = con.execute("SELECT event_id, event_date::VARCHAR AS event_date, verified FROM cause_events WHERE source='manual' "
                      "AND NOT starts_with(verified, 'tak') ORDER BY event_date").df()
    L += ["", f"## Daty ręczne (P8) niesprawdzone w pełni u źródła: {len(unv)}", "",
          "Wchodzą do etykiet z dopiskiem w `evidence`; do sprawdzenia przy następnej okazji.", ""]
    L += [f"- {r.event_id} {r.event_date}: {r.verified}" for r in unv.itertuples()]
    L += ["", "## Jak to wygląda w statusie (`ms.causes.describe_day`)", ""]
    for a, d in (("XAU", "2013-04-15"), ("BTC", "2020-03-12"), ("WTI", "1991-01-17")):
        L.append(f"- {a} {d}: {causes.describe_day(con, a, d)}")
    L += ["", "## Dni kontrolne (ocena ręczna 2026-10-06 — to nie jest potwierdzenie tekstem)", "",
          "- BTC/ETH 12.03.2020 (−50% / −59%): `leverage_liquidations` (Black Thursday) — kandydat wiarygodny.",
          "- BTC/ETH 8–9.11.2022: FTX; 9.05.2022: krach UST — kandydaci wiarygodni.",
          "- WTI 6 i 9.03.2020: OPEC+ bez porozumienia (Känzig −8,0) — kandydat wiarygodny.",
          "- **XAU 15.04.2013 (−9,2%, z = −10,5): `sovmil` z AI-GPR (zamach w Bostonie tego dnia) — zbieg dat, NIE przyczyna** "
          "(krach złota miał inne powody). Przykład, dlaczego etykieta kalendarza to „zdarzenie tego dnia”, nie przyczyna.",
          "- **BTC/ETH 19.05.2021: `crypto_hack` (Venus Protocol, 100 mln USD) — raczej skutek krachu, nie przyczyna** "
          "(w tych dniach chińskie ostrzeżenia z 18.05 — tej daty nie ma w P8).",
          "- **WTI 17.01.1991 (−40% log, Pustynna Burza): brak etykiety kalendarza** — AI-GPR był wysoki od sierpnia 1990, "
          "więc nie ma „skoku” względem mediany 90 dni. Wpis jest w chronologii EIA (17.01) — to zadanie dla warstwy badań/Qwena.",
          "- WTI 20.04.2020 (cena ujemna): nie jest „dużym ruchem”, bo log-zwrot przy cenie ≤ 0 jest pusty (zasada z etapu 2).",
          "", "## Ograniczenia", "",
          "- FOMC: miara niespodzianki tylko do 2023-12 (SF Fed) / 2024-01 (JK); później etykieta bez wielkości.",
          "- Kalendarz zna jedną możliwą przyczynę: w dniu FOMC ruch mógł mieć inny powód. To etykieta „zdarzenie w tym dniu”, "
          "nie dowód przyczyny — dlatego pewność 1,0 / 0,6 to pewność dopasowania daty, nie przyczynowości.",
          "- AI-GPR: wartości przeliczane wstecz (najnowsze wydanie); dzień zdarzenia przyjęty jako d−1 względem gazet.",
          "- Metale: kalendarz ma dla nich tylko FOMC i AI-GPR — reszta czeka na Qwena / komentarze WGC (Priorytet 2).",
          "- P6 (typ decyzji OPEC) czeka na PDF w data/inbox/imf/."]
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"move-causes-coverage-{today}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out)


def cmd_e2_sheet(con) -> int:
    if E2_FILE.exists():
        print(f"{E2_FILE} już istnieje — nie nadpisuję (mogą tam być Twoje etykiety).")
        return 1
    s = causes.e2_sheet(con)
    s.to_csv(E2_FILE, index=False, encoding="utf-8")
    print(E2_FILE, len(s), s["data"].str[:3].value_counts().sort_index().to_dict())
    return 0


def cmd_e2_xlsx(con) -> int:
    if E2_XLSX.exists():
        print(f"{E2_XLSX} już istnieje — nie nadpisuję (mogą tam być Twoje etykiety).")
        return 1
    print(E2_XLSX, causes.e2_xlsx(E2_FILE, E2_XLSX), "wierszy")
    return 0


def cmd_e2_check(con) -> int:
    g = causes.load_e2_gold(E2_XLSX, E2_FILE)
    print(f"oznaczone: {len(g)} (w tym niejasne: {(g['niejasne'] == 'tak').sum()}); ciągły początek od lp 1: "
          f"{next((i for i in range(1, 151) if i not in set(g['lp'])), 151) - 1}")
    return 0


def main(argv: list[str]) -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
    def withdrawn(_args=None):
        raise SystemExit("E2 z etykiet użytkownika WYCOFANE 2026-10-07; wzorzec E2 = komentarze WGC (ref/e2_wgc_index.csv)")

    cmds = {"fetch": cmd_fetch, "calendar": cmd_calendar, "e2-sheet": withdrawn, "e2-xlsx": withdrawn, "e2-check": withdrawn}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 2
    con = db.connect()
    try:
        return cmds[argv[1]](con)
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

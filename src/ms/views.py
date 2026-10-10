"""Dane do wyświetlenia — jedyne źródło dla `paper.py status` i dashboardu (etap 4C, D2).

Funkcje niczego nie modelują: odtwarzają konto z dziennika (ms.paper.replay), czytają prognozy mistrzów, dekompozycję
i etykiety przyczyn zapisane przez joby (ms.paper.snapshot, ms.causes.describe_day). Formatowanie: ms.fmt.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ms import paper as pp
from ms.trading import INSTRUMENT_NAME, PriceBook


def account_view(pcon, mcon, book: PriceBook, acc_row: pd.Series, today=None) -> dict:
    """Stan konta na dziś: wartość, gotówka, koszty, pozycje, zlecenia oczekujące, porównania, ścieżka wartości.
    Tylko odczyt: status executed zapisuje nocny job (ms.paper.sync_all). Oczekujące = 'pending' w bazie bez wykonania
    w replay (cena z dnia wykonania już jest, a job jeszcze nie biegł -> zlecenie już w pozycjach, nie w oczekujących)."""
    today = pd.Timestamp(today or date.today())
    st = pp.replay(pcon, book, acc_row, today)
    val = st.values.iloc[-1] if len(st.values) else float(acc_row["start_cash"])
    executed = {int(o.id): (tr.date if tr is not None else None) for o, tr in st.executed}
    done = list(executed)
    pending = pcon.execute("SELECT id, decision_date, side, asset, amount_pln, units FROM paper_orders WHERE account_id=? "
                           "AND status='pending' AND NOT list_contains(?, id) ORDER BY id", [int(acc_row["id"]), done]).df()
    positions = []
    for a, p in st.acc.pos.items():
        v = p.units * book.value_on(a, today) * book.fx(today)
        positions.append({"asset": a, "instrument": INSTRUMENT_NAME[a], "units": p.units, "value": v, "cost": p.cost_pln,
                          "pnl": v - p.cost_pln})
    start_cash = float(acc_row["start_cash"])
    return {"id": int(acc_row["id"]), "name": acc_row["name"], "today": today, "start_date": str(acc_row["start_date"])[:10],
            "start_cash": start_cash, "value": val, "result_pln": val - start_cash, "result_pct": val / start_cash - 1,
            "cash": st.acc.cash, "costs": st.acc.costs_total, "tax": st.acc.tax_total, "interest": st.acc.interest_total,
            "positions": positions, "pending": pending, "benchmarks": pp.benchmarks(book, acc_row, today),
            "values": st.values, "executed": executed}


def decomp_text(s: dict) -> str | None:
    """„Co ruszyło ceną w tygodniu…” z karty aktywa (CLI i dashboard)."""
    from ms import fmt

    if not s["decomp"]:
        return None
    parts = ", ".join(f"{fmt.GROUP_PL.get(g, g)} {fmt.pp(c)}" for g, c in s["decomp"].items())
    return (f"Co ruszyło ceną w tygodniu {str(s['decomp_week'])[:10]}: zwrot {fmt.pp(s['decomp_ret'])} = {parts}, "
            f"niewyjaśnione {fmt.pp(s['decomp_unexplained'])}.")


def vol_text(s: dict) -> str:
    from ms import fmt

    return (f"Zmienność 20 dni {fmt.pct0(s['rv20'])} vs roczna {fmt.pct0(s['rv1y'])} (annualizowane)"
            + fmt.vol_label(s["rv20"], s["rv1y"]))


def asset_card(mcon, book: PriceBook, asset: str, t=None) -> dict:
    """Karta aktywa z danych znanych w t: migawka systemu (jak w statusie) + „tego dnia było” (move_causes)."""
    from ms import causes

    t = pd.Timestamp(t if t is not None else pp.now_utc())
    s = pp.snapshot(mcon, book, asset, t)
    has = mcon.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='move_causes'").fetchone()[0]
    s["that_day"] = causes.describe_day(mcon, asset, s["last_close_date"]) if has else ""   # świeży klon: brak tabeli
    return s


# --------------------------------------------------------------------------- dashboard (etap 4C)

import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from ms import db  # noqa: E402

def view_db() -> Path:
    """Kopia bazy (MS_VIEW_DB nadpisuje — testy). Czytane przy każdym wywołaniu, nie przy imporcie."""
    return Path(os.environ.get("MS_VIEW_DB", db.ROOT / "data" / "market_view.duckdb"))
BOOK_ASSETS = ("BTC", "ETH", "XAG", "WTI", "XAU", "BRENT")


def open_market_view():
    """Kopia bazy publikowana przez joby, TYLKO do odczytu (D1). Dashboard nie otwiera market.duckdb."""
    import duckdb

    con = duckdb.connect(str(view_db()), read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    return con


def view_meta() -> dict:
    meta = view_db().with_suffix(".json")
    return json.loads(meta.read_text()) if meta.exists() else {"published_at": "—"}


def load_book(mcon) -> PriceBook:
    return PriceBook(mcon, assets=BOOK_ASSETS)


def compare_paths(pcon, book: PriceBook, acc_row: pd.Series, today=None) -> dict[str, pd.Series]:
    """Wykres konta: ścieżka konta, porównania z paper.benchmark_paths, równy podział i pozostałe konta „system”."""
    from ms import momentum as mm

    today = pd.Timestamp(today or date.today())
    out = {f"konto {acc_row['name']}": pp.replay(pcon, book, acc_row, today).values}
    out.update(pp.benchmark_paths(book, acc_row, today))
    start = pd.Timestamp(acc_row["start_date"])
    out["rowny_podzial_4"] = mm.run_equal_weight(book, start, max(today, start), cash=float(acc_row["start_cash"])).values
    for _, a in system_accounts(pcon).iterrows():
        if int(a["id"]) != int(acc_row["id"]):
            out[f"konto {a['name']}"] = pp.replay(pcon, book, a, today).values
    return out


def system_accounts(pcon) -> pd.DataFrame:
    if not pcon.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='paper_system'").fetchone()[0]:
        return pd.DataFrame(columns=["id", "name"])
    return pcon.execute("""SELECT a.*, s.variant, s.dd_limit, s.note FROM paper_accounts a
                           JOIN paper_system s ON s.account_id = a.id ORDER BY a.id""").df()


EXECUTED_NOT_SAVED = "wykonane (zapis w bazie: nocny job)"


def journal_view(pcon, acc_row: pd.Series, executed: dict | None = None) -> dict:
    """Dziennik konta: zlecenia z powodami i poprawkami (gra) albo decyzje reguł (konta „system”).
    executed = account_view(...)["executed"] (replay): zlecenie 'pending' w bazie, które ma już cenę wykonania, ma status
    EXECUTED_NOT_SAVED i datę wykonania z replay — ten sam stan co pozycje i „oczekujące”. Bazy nie zmienia (zapis
    statusu wyłącznie job „system”: paper.py sync)."""
    from ms import system

    sysrow = system.system_row(pcon, int(acc_row["id"]))
    if sysrow is not None:
        dec = pcon.execute("""SELECT decision_date, exec_date, kind, why, target FROM paper_system_decisions
                              WHERE account_id=? ORDER BY decision_date""", [int(acc_row["id"])]).df()
        return {"system": True, "variant": sysrow["variant"], "dd_limit": float(sysrow["dd_limit"]), "decisions": dec}
    orders = pcon.execute("""SELECT id, decision_date, side, asset, amount_pln, units, status, exec_date, reason
                             FROM paper_orders WHERE account_id=? ORDER BY id""", [int(acc_row["id"])]).df()
    for oid, day in (executed or {}).items():
        m = (orders["id"] == oid) & (orders["status"] == "pending")
        orders.loc[m, "status"] = EXECUTED_NOT_SAVED
        if day is not None:
            orders.loc[m, "exec_date"] = pd.Timestamp(day)
    notes = pcon.execute("""SELECT j.order_id, j.logged_at, j.kind, j.text FROM paper_journal j
                            JOIN paper_orders o ON o.id = j.order_id WHERE o.account_id=? ORDER BY j.id""",
                         [int(acc_row["id"])]).df()
    return {"system": False, "orders": orders, "notes": notes}


def recommendations_view(mcon, pcon) -> dict:
    """Zalecenia reguł na dziś (tabela rules_today z joba) + konta „system” + stan etapu 5."""
    rt = mcon.execute("SELECT * FROM rules_today ORDER BY account_id, variant, asset").df()
    hold = mcon.execute("SELECT params FROM runs WHERE stage='5-holdout'").fetchone()
    return {"rules_today": rt, "system_accounts": system_accounts(pcon),
            "holdout_opened": json.loads(hold[0])["otwarte"] if hold else None,
            "winner_d7": json.loads(hold[0])["zwyciezca"] if hold else None}


def backtest_summary(mcon) -> dict:
    """Skrót wyników etapu 5 (część rozwojowa i odłożona; koszty x1) z tabel zapisanych przez backtest_rules."""
    cols = "wariant, na_reke, zwrot_roczny, sharpe, sharpe_po_cieciu_2, sharpe_po_cieciu_4, max_obsuniecie"
    dev = mcon.execute(f"SELECT {cols}, dsr FROM backtest_rules_dev WHERE koszty_wersja='x1'").df()
    hold = mcon.execute(f"SELECT {cols} FROM backtest_rules_holdout WHERE koszty_wersja='x1'").df()
    keep = ["iv_bez_filtra", "iv_filtr", "iv_filtr_ovx", "rowny_podzial_4", "kup_i_trzymaj_XAU", "momentum_1m"]
    return {"dev": dev[dev.wariant.isin(keep)].set_index("wariant").loc[keep].reset_index(),
            "holdout": hold[hold.wariant.isin(keep)].set_index("wariant").loc[keep].reset_index()}


def price_view(book: PriceBook, asset: str, t=None, years: int = 2) -> pd.Series:
    """Cena USD z zamknięć znanych w t (ostatnie `years` lat) — do wykresu karty."""
    t = pd.Timestamp(t if t is not None else pp.now_utc())
    f = book.frames[asset]
    s = f.loc[(f["known_at"] <= t) & (f["value"] > 0), "value"]
    return s[s.index > t - pd.DateOffset(years=years)]


def system_health() -> dict:
    """Wynik tools/health.sh (joby, usługi, konfiguracja na żywo) + czas publikacji kopii bazy."""
    r = subprocess.run([str(db.ROOT / "tools" / "health.sh")], capture_output=True, text=True, timeout=60)
    return {"ok": r.returncode == 0, "text": r.stdout + r.stderr, "view": view_meta()}


def news_view_db() -> Path:
    return Path(os.environ.get("MS_NEWS_VIEW_DB", db.ROOT / "data" / "news_view.duckdb"))


def news_for_asset(asset: str, n: int = 5, now=None) -> dict:
    """Wiadomości aktywa z kopii news_view.duckdb (tylko odczyt):
    own   — kanały RSS / GDELT DOC aktywa, najnowsze po czasie;
    gdelt — wpisy ze zdarzeń GDELT z ostatnich 24 h, wg liczby wzmianek (num_mentions) malejąco;
    macro — kanały RSS makro, najnowsze po czasie."""
    import duckdb

    from ms import news

    srcs = news.all_sources()
    ev = [k for k, v in srcs.items() if v["kind"] == "GDELT zdarzenia" and asset in v["assets"]]
    own = [k for k, v in srcs.items() if v["kind"] != "GDELT zdarzenia" and asset in v["assets"]]
    macro = [k for k, v in srcs.items() if v["kind"] != "GDELT zdarzenia" and "MAKRO" in v["assets"] and k not in own]
    empty = {"own": pd.DataFrame(), "gdelt": pd.DataFrame(), "macro": pd.DataFrame(), "sources": srcs}
    if not news_view_db().exists():
        return empty
    now = pd.Timestamp(now if now is not None else pd.Timestamp.now(tz="UTC").tz_localize(None))
    con = duckdb.connect(str(news_view_db()), read_only=True)
    by_time = """SELECT source, title, url, coalesce(published_at, known_at) AS czas, published_missing, mentions
                 FROM news_items WHERE source IN (SELECT unnest(?)) ORDER BY czas DESC LIMIT ?"""
    by_mentions = """SELECT source, title, url, coalesce(published_at, known_at) AS czas, published_missing, mentions
                     FROM news_items WHERE source IN (SELECT unnest(?)) AND coalesce(published_at, known_at) > ?
                     ORDER BY mentions DESC NULLS LAST, czas DESC LIMIT ?"""
    try:
        out = {"own": con.execute(by_time, [own, n]).df() if own else pd.DataFrame(),
               "gdelt": con.execute(by_mentions, [ev, (now - pd.Timedelta(hours=24)).to_pydatetime(), n]).df() if ev else pd.DataFrame(),
               "macro": con.execute(by_time, [macro, n]).df() if macro else pd.DataFrame(), "sources": srcs}
    finally:
        con.close()
    for k in ("own", "gdelt", "macro"):
        if len(out[k]):
            out[k]["zrodlo"] = out[k]["source"].map(lambda x: srcs[x]["name"])
    return out

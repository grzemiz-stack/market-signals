"""Gra na sucho: migawka bez przyszłości (zlecenie z D nie widzi ceny D+1), wykonanie po zamknięciu D+1,
konto bez transakcji = gotówka + odsetki, koszty zmniejszają wynik."""

import copy
import json
import shutil
import sys

import numpy as np
import pandas as pd
import pytest

from ms import db, momentum as mm, paper as pp
from ms.trading import Costs, PriceBook

pytestmark = pytest.mark.data
D = pd.Timestamp("2026-09-02")  # środa


@pytest.fixture(scope="module")
def book(real):
    return PriceBook(real)


@pytest.fixture
def pcon(tmp_path):
    return pp.connect(tmp_path / "paper.duckdb")


def _acc(pcon, real, start="2026-09-01"):
    return pp.account(pcon, pp.new_account(pcon, real, "test", 1000.0, start))


@pytest.fixture(scope="module")
def perturbed(tmp_path_factory, real):
    """Kopia bazy: wszystko znane po D 22:00 zmienione (ceny, prognozy, dekompozycja)."""
    copy_path = tmp_path_factory.mktemp("pp") / "m.duckdb"
    shutil.copy(db.DB_PATH, copy_path)
    con = db.connect(copy_path)
    t = D + pd.Timedelta(hours=22)
    con.execute("UPDATE observations SET value = value * 1.5 + 3 WHERE known_at > ?", [t])
    con.execute("UPDATE baseline_preds SET p_up = 0.99, p_down = 0.01 WHERE date > ?", [D.date()])
    con.execute("UPDATE decomp_weekly SET contribution = 9, unexplained = 9, ret = 9 WHERE week > ?", [D.date()])
    yield con
    con.close()


@pytest.mark.parametrize("asset", ["WTI", "BTC"])
def test_snapshot_at_d_does_not_see_future(real, book, perturbed, asset):
    t = D + pd.Timedelta(hours=22)
    s0 = pp.snapshot(real, book, asset, t)
    s1 = pp.snapshot(perturbed, PriceBook(perturbed), asset, t)
    assert json.dumps(s0, default=str, sort_keys=True) == json.dumps(s1, default=str, sort_keys=True)
    assert pd.Timestamp(s0["last_close_date"]) <= D  # zamknięcie D+1 nieznane przy składaniu
    t2 = t + pd.Timedelta(days=10)  # kontrola: później dane zaburzone są już znane -> migawka się różni
    assert pp.snapshot(real, book, asset, t2)["last_close_usd"] != pp.snapshot(perturbed, PriceBook(perturbed), asset, t2)["last_close_usd"]
    l0 = pp.bad_week_loss(book, asset, 300, t)
    assert l0 == pp.bad_week_loss(PriceBook(perturbed), asset, 300, t) and l0[0] > 0


def test_order_executes_at_close_of_d_plus_1(real, book, pcon):
    acc = _acc(pcon, real)
    for asset, amount in (("BTC", 200.0), ("WTI", 300.0)):
        pp.place(pcon, real, book, int(acc["id"]), "buy", asset, "test", amount_pln=amount, D=D)
    st = pp.replay(pcon, book, acc, "2026-09-30")
    trades = {tr.asset: tr for _, tr in st.executed}
    assert trades["BTC"].date == D + pd.Timedelta(days=1)       # krypto: D+1
    assert trades["WTI"].date == book.next_bday(D)              # ETC: następny dzień roboczy USA
    for a, tr in trades.items():
        assert tr.price_usd == book.close_on(a, tr.date)[0]


def test_account_without_trades_is_cash_plus_interest(real, book, pcon):
    acc = _acc(pcon, real, "2025-01-01")
    st = pp.replay(pcon, book, acc, "2026-06-30")
    dep = mm.run_deposit(book, "2025-01-01", "2026-06-30")
    assert abs(st.values.iloc[-1] - dep.values.iloc[-1]) < 1e-9 and st.values.iloc[-1] > 1000


def test_costs_reduce_result(real, book, pcon):
    acc = _acc(pcon, real, "2026-01-02")
    pp.place(pcon, real, book, int(acc["id"]), "buy", "BTC", "test", amount_pln=500, D="2026-01-05")
    pp.place(pcon, real, book, int(acc["id"]), "sell", "BTC", "test", D="2026-03-02")
    with_c = pp.replay(pcon, book, acc, "2026-04-30")
    no_c = pp.replay(pcon, book, acc, "2026-04-30", costs=Costs.zero())
    assert with_c.acc.costs_total > 0 and with_c.values.iloc[-1] < no_c.values.iloc[-1]


def test_reason_required(real, book, pcon):
    acc = _acc(pcon, real)
    with pytest.raises(ValueError):
        pp.place(pcon, real, book, int(acc["id"]), "buy", "BTC", "  ", amount_pln=100, D=D)


def test_liquidation_value_finite_without_todays_close(real, book, pcon):
    acc = _acc(pcon, real)
    pp.place(pcon, real, book, int(acc["id"]), "buy", "BTC", "test", amount_pln=300, D=D)
    st = pp.replay(pcon, book, acc, "2026-10-05")
    future = pd.Timestamp("2099-01-01")  # brak zamknięcia z tego dnia
    liq, costs, tax = st.acc.liquidation_value(future, book)
    assert np.isfinite(liq) and costs > 0 and liq < st.acc.value("2026-10-05", book)


def test_cancelled_order_does_not_execute(real, book, pcon):
    acc = _acc(pcon, real)
    oid, _ = pp.place(pcon, real, book, int(acc["id"]), "buy", "BTC", "test", amount_pln=200, D=D)
    pp.cancel(pcon, book, oid, now=D + pd.Timedelta(hours=23))  # przed zamknięciem D+1
    st = pp.replay(pcon, book, acc, "2026-09-30")
    assert st.executed == [] and st.acc.cash > 1000  # tylko odsetki
    j = pp.journal(pcon, oid)
    assert list(j["kind"]) == ["cancel"]
    assert pcon.execute("SELECT status FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "cancelled"
    assert pcon.execute("SELECT count(*) FROM paper_orders").fetchone()[0] == 1  # nic nie skasowane


def test_cancel_executed_order_fails(real, book, pcon):
    acc = _acc(pcon, real)
    oid, _ = pp.place(pcon, real, book, int(acc["id"]), "buy", "WTI", "test", amount_pln=200, D=D)
    moment = pp.execution_moment(book, "WTI", D)
    with pytest.raises(ValueError, match="wykonane"):
        pp.cancel(pcon, book, oid, now=moment)
    assert pcon.execute("SELECT status FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "pending"
    assert pp.journal(pcon, oid).empty
    st = pp.replay(pcon, book, acc, "2026-09-30")
    assert len(st.executed) == 1


def test_note_does_not_overwrite_reason(real, book, pcon):
    acc = _acc(pcon, real)
    oid, _ = pp.place(pcon, real, book, int(acc["id"]), "buy", "BTC", "pierwotny powód", amount_pln=100, D=D)
    pp.add_note(pcon, oid, "poprawka 1", now="2026-09-03")
    pp.add_note(pcon, oid, "poprawka 2", now="2026-09-04")
    assert pcon.execute("SELECT reason FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "pierwotny powód"
    j = pp.journal(pcon, oid)
    assert list(j["text"]) == ["poprawka 1", "poprawka 2"] and j["logged_at"].is_monotonic_increasing


def test_job_sync_marks_executed_without_dashboard(real, book, tmp_path):
    """Status executed zapisuje nocny job (paper.py sync w tools/system_daily.sh), nie widok/dashboard."""
    import subprocess

    path = tmp_path / "job.duckdb"
    con = pp.connect(path)
    acc = _acc(con, real)
    oid, _ = pp.place(con, real, book, int(acc["id"]), "buy", "BTC", "test", amount_pln=200, D=D)
    con.close()
    con = pp.connect(path, read_only=True)
    from ms import views
    v = views.account_view(con, real, book, acc, "2026-09-30")          # sam odczyt: baza bez zmian
    assert con.execute("SELECT status FROM paper_orders WHERE id=?", [oid]).fetchone()[0] == "pending"
    assert v["pending"].empty and [p["asset"] for p in v["positions"]] == ["BTC"]   # widok spójny przed jobem
    con.close()
    for expect in ("{'test': 1}", "{'test': 0}"):                        # job; drugi przebieg niczego nie zmienia
        r = subprocess.run([sys.executable, str(db.ROOT / "src" / "paper.py"), "--db", str(path), "sync"],
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0 and expect in r.stdout, r.stdout + r.stderr
    con = pp.connect(path, read_only=True)
    st, price, ed = con.execute("SELECT status, exec_price_usd, exec_date FROM paper_orders WHERE id=?", [oid]).fetchone()
    assert st == "executed" and pd.Timestamp(ed) == D + pd.Timedelta(days=1)
    assert price == book.close_on("BTC", D + pd.Timedelta(days=1))[0]


def test_system_job_runs_paper_sync():
    s = (db.ROOT / "tools" / "system_daily.sh").read_text()
    assert "src/paper.py sync" in s and "exit $fail" in s

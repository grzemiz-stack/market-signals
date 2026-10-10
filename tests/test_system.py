"""Konta „system”: prowadzone ścieżką na żywo dają dokładnie wynik backtestu (te same decyzje i wykonania), decyzja
dnia D dopiero następnego dnia, ręczne zlecenia odrzucane, próg D9 zatrzymuje konto."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ms import momentum as mm, paper as pp, rules as R, system

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = pytest.mark.data
S, END = pd.Timestamp("2023-01-03"), pd.Timestamp("2024-06-28")


@pytest.fixture(scope="module")
def data(real):
    return R.RuleData.load(real)


def _account(pcon, name, variant, dd_limit=-0.9, start=S):
    system.init(pcon)
    acc_id = pcon.execute("""INSERT INTO paper_accounts (name, created_at, start_date, start_cash, momentum_variant)
                             VALUES (?, now()::TIMESTAMP, ?, 1000.0, 'momentum_1m') RETURNING id""", [name, start.date()]).fetchone()[0]
    pcon.execute("INSERT INTO paper_system VALUES (?,?,?,?,?,now()::TIMESTAMP,'test')",
                 [acc_id, variant, R.definitions_hash(), dd_limit / 1.5, dd_limit])
    return pp.account(pcon, acc_id)


@pytest.mark.parametrize("variant", ["rowny_podzial_4", "iv_filtr_ovx"])
def test_live_path_equals_backtest(tmp_path, data, variant):
    pcon = pp.connect(tmp_path / "p.duckdb")
    acc = _account(pcon, "system_test", variant)
    system.run_account(pcon, data, acc, today=END + pd.Timedelta(days=3))
    live = system.replay(pcon, data.book, acc, until=END).values
    if variant == "rowny_podzial_4":
        bt = mm.run_equal_weight(data.book, S, END).values
    else:
        bt = R.run_rules(data, variant, S, END)[0].values
    assert len(live) == len(bt) and np.allclose(live.to_numpy(), bt.to_numpy(), rtol=0, atol=1e-9), \
        float(np.abs(live.to_numpy() - bt.to_numpy()).max())
    dec = pcon.execute("SELECT * FROM paper_system_decisions").df()
    assert len(dec) > 3 and (dec["kind"] != "stop").all()


def test_decision_waits_for_next_day_and_is_idempotent(tmp_path, data):
    pcon = pp.connect(tmp_path / "p.duckdb")
    acc = _account(pcon, "system_test", "iv_filtr_ovx", start=pd.Timestamp("2024-02-01"))
    D = pd.Timestamp("2024-02-29")
    system.run_account(pcon, data, acc, today=D)                 # w dniu D: decyzja z D jeszcze nie zapada
    days = set(pd.to_datetime(pcon.execute("SELECT decision_date FROM paper_system_decisions").df()["decision_date"]))
    assert D not in days and pd.Timestamp("2024-01-31") in days
    system.run_account(pcon, data, acc, today=D + pd.Timedelta(days=1))
    n = pcon.execute("SELECT count(*) FROM paper_system_decisions").fetchone()[0]
    system.run_account(pcon, data, acc, today=D + pd.Timedelta(days=1))
    assert pcon.execute("SELECT count(*) FROM paper_system_decisions").fetchone()[0] == n   # bez duplikatów


def test_manual_orders_refused(tmp_path, real, data):
    pcon = pp.connect(tmp_path / "p.duckdb")
    acc = _account(pcon, "system_test", "rowny_podzial_4")
    with pytest.raises(PermissionError):
        pp.place(pcon, real, data.book, int(acc["id"]), "buy", "BTC", "ręcznie", amount_pln=100.0, D="2024-01-02")


def test_d9_stop_per_account(tmp_path, data):
    pcon = pp.connect(tmp_path / "p.duckdb")
    tight = _account(pcon, "system_a", "rowny_podzial_4", dd_limit=-0.05)      # próg nie do utrzymania
    loose = _account(pcon, "system_b", "rowny_podzial_4", dd_limit=-0.95)
    for acc in (tight, loose):
        system.run_account(pcon, data, acc, today=END)
    kinds = pcon.execute("SELECT account_id, kind FROM paper_system_decisions WHERE kind='stop'").df()
    assert set(kinds["account_id"]) == {int(tight["id"])}
    st = system.replay(pcon, data.book, tight, until=END + pd.Timedelta(days=10))
    assert not st.acc.pos                                         # po stopie: tylko gotówka
    assert system.run_account(pcon, data, tight, today=END + pd.Timedelta(days=60)) == \
        ["konto zatrzymane regułą D9 — bez nowych decyzji"]


def test_alarms_are_information_only(tmp_path, data):
    idx = pd.date_range("2026-01-01", periods=30)
    flat = pd.Series(1000.0, index=idx)
    assert system.alarms(flat) == []
    dd = flat.copy(); dd.iloc[10:] = 690.0                        # −31% od szczytu, tydzień płasko
    assert [m.split(" ")[1] for m in system.alarms(dd)] == ["od"]
    wk = flat.copy(); wk.iloc[-1] = 840.0                        # −16% w tygodniu, −16% od szczytu (< 30%)
    assert [m.split(" ")[2] for m in system.alarms(wk)] == ["tygodniu"]
    assert system.alarms(pd.Series(dtype=float)) == []
    # alarm nie wchodzi do decyzji: run_account nie woła alarms (decyzje = reguły + D9)
    import inspect
    assert "alarms(" not in inspect.getsource(system.run_account)


def test_alarm_notifies_once_per_episode(tmp_path, monkeypatch):
    import subprocess
    import system_accounts as sa

    calls = []
    monkeypatch.setattr(sa, "ALARM_STATE", tmp_path / "alarms.json")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    sa.alarm("system", ["spadek od szczytu -31,0% (próg -30%)"])
    sa.alarm("system", ["spadek od szczytu -33,0% (próg -30%)"])      # ten sam epizod: tylko log
    assert len(calls) == 1
    sa.alarm("system", [])                                            # koniec epizodu
    sa.alarm("system", ["spadek od szczytu -31,0% (próg -30%)"])      # nowy epizod: powiadomienie
    assert len(calls) == 2

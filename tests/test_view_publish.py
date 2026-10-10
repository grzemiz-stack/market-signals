"""Etap 4C krok 3: kopia bazy dla dashboardu (atomowa, tylko do odczytu, nie blokuje joba) i zalecenia rules_today."""

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import publish_view as pv  # noqa: E402
import rules_today as rt  # noqa: E402
from ms import paper as pp, rules as R  # noqa: E402


def test_publish_is_complete_and_view_does_not_block_writer(tmp_path):
    src, dst, meta = tmp_path / "m.duckdb", tmp_path / "v.duckdb", tmp_path / "v.json"
    c = duckdb.connect(str(src))
    c.execute("CREATE TABLE t AS SELECT range AS x FROM range(1000)")
    c.close()
    pv.publish(src, dst, meta)
    view = duckdb.connect(str(dst), read_only=True)              # dashboard trzyma kopię otwartą…
    w = duckdb.connect(str(src))                                  # …a job dalej pisze do bazy roboczej
    w.execute("INSERT INTO t VALUES (1000)")
    w.close()
    assert view.execute("SELECT count(*) FROM t").fetchone()[0] == 1000
    with pytest.raises(duckdb.Error):
        view.execute("INSERT INTO t VALUES (1)")                   # kopia tylko do odczytu
    pv.publish(src, dst, meta)                                     # podmiana przy otwartej kopii (stary uchwyt działa)
    assert view.execute("SELECT count(*) FROM t").fetchone()[0] == 1000
    view.close()
    assert duckdb.connect(str(dst), read_only=True).execute("SELECT count(*) FROM t").fetchone()[0] == 1001
    assert json.loads(meta.read_text())["bytes"] == dst.stat().st_size


@pytest.mark.data
def test_rules_today_matches_rules(real):
    pcon = duckdb.connect(str(pp.PAPER_DB), read_only=True)        # krok joba czyta grę tylko do odczytu
    df = rt.build(real, pcon, today="2026-09-30")
    D = pd.Timestamp("2026-09-30")
    data = R.RuleData.load(real)
    for v in R.VARIANTS:
        w, _ = R.target_weights(data, D, v)
        sub = df[(df.variant == v) & (df.account_id == 1)].set_index("asset")["target_w"]
        assert sub.to_dict() == {a: w.get(a, 0.0) for a in sub.index}, v
    assert df["decision_day"].any() and (df["D"] == D.date()).all()          # 30.09 = koniec miesiąca i kwartału
    eq = df[(df.variant == "rowny_podzial_4") & (df.account_id == 1)]
    assert eq["rebalance"].all() and eq["target_w"].round(12).tolist() == [0.25] * 4
    assert R.definitions_hash() == "d9cb3a3a2da04caa"

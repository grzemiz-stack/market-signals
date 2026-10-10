"""Dzienne prognozy mistrzów: po dojściu nowych zamknięć status pokazuje liczby (nie „–%”), a dopisane prognozy są
identyczne z comiesięcznymi (te same modele i parametry, bez ponownego trenowania na nowych etykietach)."""

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ms import db, prob, registry, wf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import predict_daily as pdl  # noqa: E402

pytestmark = pytest.mark.data
CUT = "2026-09-21"   # dni od CUT udają „nowe zamknięcia”: prognoz brak, jak przed dziennym krokiem


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    path = tmp_path_factory.mktemp("pd") / "m.duckdb"
    shutil.copy(db.DB_PATH, path)
    c = db.connect(path)
    yield c
    c.close()


def test_new_days_get_same_predictions_and_status_shows_numbers(con):
    champs = {(a, registry.champion(con, a, q).model_id) for a in pdl.ASSETS for q in pdl.QUESTIONS}
    champs = {x for x in champs if x[1] not in pdl.NOT_STORED}
    orig = con.execute("SELECT asset, model, date, p_up, p_down FROM baseline_preds WHERE date >= ?", [CUT]).df()
    for a, m in champs:
        con.execute("DELETE FROM baseline_preds WHERE asset=? AND model=? AND date >= ?", [a, m, CUT])
    last = {a: con.execute("SELECT max(date) FROM labels WHERE asset=?", [a]).fetchone()[0] for a in pdl.ASSETS}
    # przed krokiem dziennym: brak prognozy -> „—” w statusie (tak wyglądał błąd)
    p0 = prob.probability(con, "XAG", last["XAG"])
    assert not np.isfinite(p0.p_up) and "—%" in prob.text(p0)

    for a in pdl.ASSETS:
        pdl.predict_asset(con, a)

    new = con.execute("SELECT asset, model, date, p_up, p_down FROM baseline_preds WHERE date >= ?", [CUT]).df()
    # wzorzec: pełne przeliczenie tymi samymi funkcjami modeli (nie wartości z tabeli — te mogły powstać przed
    # dojściem spóźnionych danych, np. GVZ z FRED; 2026-10-08)
    ref = []
    for a, m in champs:
        d = wf.load(con, a)
        r = pdl.model_preds(con, d, m, pd.Timestamp(CUT)).dropna()
        ref.append(r[r.index >= CUT].reset_index(names="date").assign(asset=a, model=m))
    ref = pd.concat(ref)
    ref["date"] = pd.to_datetime(ref["date"]); new["date"] = pd.to_datetime(new["date"])
    both = ref.merge(new, on=["asset", "model", "date"], suffixes=("_m", "_d"))
    assert len(both) >= 10 * len(champs), "za mało wspólnych dni do porównania"
    assert np.allclose(both.p_up_m, both.p_up_d, rtol=0, atol=1e-12), "dzienne != pełne przeliczenie (p_up)"
    assert np.allclose(both.p_down_m, both.p_down_d, rtol=0, atol=1e-12), "dzienne != pełne przeliczenie (p_down)"
    # drugi przebieg niczego nie dubluje
    n = con.execute("SELECT count(*) FROM baseline_preds").fetchone()[0]
    for a in pdl.ASSETS:
        assert set(pdl.predict_asset(con, a).values()) == {0}                 # okno przeliczane, nic nowego
    assert con.execute("SELECT count(*) FROM baseline_preds").fetchone()[0] == n

    for a in pdl.ASSETS:  # status dla najnowszego zamknięcia: liczby, nie „—%”
        p = prob.probability(con, a, last[a])
        assert np.isfinite(p.p_up) and np.isfinite(p.p_down), a
        assert "—%" not in prob.text(p), prob.text(p)


def test_recent_days_refreshed_after_late_data(con):
    """2026-10-08: prognoza XAU z 2026-10-06 policzona przed publikacją GVZ — okno 7 dni ją poprawia."""
    a, m = "XAU", registry.champion(con, "XAU", "prob_up_5d").model_id
    last = con.execute("SELECT max(date) FROM baseline_preds WHERE asset=? AND model=?", [a, m]).fetchone()[0]
    con.execute("UPDATE baseline_preds SET p_up = 0.999 WHERE asset=? AND model=? AND date=?", [a, m, last])
    pdl.predict_asset(con, a)
    assert con.execute("SELECT p_up FROM baseline_preds WHERE asset=? AND model=? AND date=?", [a, m, last]).fetchone()[0] < 0.5
    assert con.execute("SELECT count(*) FROM baseline_preds WHERE asset=? AND model=? AND date=?", [a, m, last]).fetchone()[0] == 1

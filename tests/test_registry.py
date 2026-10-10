"""Rejestr: reguły awansu/degradacji (deterministyczne), wynik miesiąca bez danych po M, fallback, liczenie prób."""

import numpy as np
import pandas as pd
import pytest

from ms import db, registry as rg
from ms.models.base import Model

MONTHS = [pd.Timestamp("2026-11-01") + pd.DateOffset(months=k) for k in range(6)]


def frame(p_fn, seed=0, start="2026-11-01", end="2027-04-30", base=0.1):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    y = (rng.random(len(days)) < 0.1).astype(float)
    return pd.DataFrame({"p": p_fn(y, rng), "y": y, "resolved_at": days, "b": base}, index=days)


def champion_noisy(y, rng):
    return np.full(len(y), 0.1)


def perfect(y, rng):
    return np.clip(y * 0.9 + 0.05, 0, 1)


def terrible(y, rng):
    return 1 - y


def test_promotion_when_challenger_clearly_better_and_deterministic():
    fr = {"iv_calibrated": frame(champion_noisy), "har_rv": frame(perfect), "base_rate": frame(champion_noisy)}
    d1, _ = rg.decide("prob_up_5d", "iv_calibrated", fr, MONTHS)
    d2, _ = rg.decide("prob_up_5d", "iv_calibrated", fr, MONTHS)
    assert d1 == d2  # deterministyczne
    assert d1[0][:2] == ("har_rv", "champion") and d1[1][:2] == ("iv_calibrated", "challenger")


def test_no_promotion_below_100_days():
    short = frame(perfect, end="2027-01-10")
    fr = {"iv_calibrated": frame(champion_noisy), "har_rv": short}
    n = len(rg.window_slice(short, MONTHS))
    assert n < 100
    assert rg.decide("prob_up_5d", "iv_calibrated", fr, MONTHS)[0] == []


def test_degradation_to_fallback_when_champion_worse_than_base():
    fr = {"iv_calibrated": frame(terrible), "base_rate": frame(champion_noisy)}
    dec, diag = rg.decide("prob_up_5d", "iv_calibrated", fr, MONTHS)
    assert dec[0][:2] == ("base_rate", "champion") and diag["champion_vs_fallback"][2] < 0


def test_rules_need_six_counted_months():
    fr = {"iv_calibrated": frame(champion_noisy), "har_rv": frame(perfect)}
    dec, diag = rg.decide("prob_up_5d", "iv_calibrated", fr, MONTHS[:5])
    assert dec == [] and "za mało" in diag["note"]
    # miesiące z okresu selekcji 3A nie są liczone
    assert rg.rule_months(pd.Timestamp("2026-12-01")) == [pd.Timestamp("2026-11-01"), pd.Timestamp("2026-12-01")]


def test_month_score_uses_no_data_after_month():
    df = frame(perfect, seed=3)
    m = pd.Timestamp("2027-01-01")
    s0 = rg.score_month(df, "prob_up_5d", m)
    df2 = df.copy()
    after = df2["resolved_at"] >= m + pd.offsets.MonthBegin(1)
    df2.loc[after, ["p", "y", "b"]] = np.random.default_rng(1).random((int(after.sum()), 3))
    assert rg.score_month(df2, "prob_up_5d", m) == s0
    assert s0["n"] == len(pd.bdate_range("2027-01-01", "2027-01-31"))


@pytest.fixture
def mem_reg():
    con = db.connect(":memory:")
    rg.init_schema(con)
    yield con
    con.close()


def test_fallback_when_no_champion(mem_reg):
    c = rg.champion(mem_reg, "XAU", "prob_up_5d")  # pusty rejestr
    assert c.model_id == "base_rate" and "częstość bazowa" in c.card
    rg.set_role(mem_reg, "XAU", "prob_up_5d", "base_rate", "fallback", "reguła: fallback zawsze")
    rg.set_role(mem_reg, "XAU", "prob_up_5d", "har_rv", "challenger", "start")
    assert rg.champion(mem_reg, "XAU", "prob_up_5d").model_id == "base_rate"


def test_role_change_requires_reason(mem_reg):
    with pytest.raises(ValueError):
        rg.set_role(mem_reg, "XAU", "prob_up_5d", "har_rv", "champion", "  ")


def test_adding_model_increases_trials(mem_reg):
    m = Model("new_model", "prob_up_5d", ("XAU",), {"a": 1})
    n0 = rg.n_trials(mem_reg)
    assert rg.register_trial(mem_reg, m) and rg.n_trials(mem_reg) == n0 + 1
    assert not rg.register_trial(mem_reg, m) and rg.n_trials(mem_reg) == n0 + 1      # ta sama konfiguracja
    assert rg.register_trial(mem_reg, Model("new_model", "prob_up_5d", ("XAU",), {"a": 2}))  # nowa konfiguracja = próba
    assert rg.n_trials(mem_reg) == n0 + 2


@pytest.mark.data
def test_real_registry_one_champion_and_fallback(real):
    r = rg.roles(real)
    assert len(r), "rejestr pusty — uv run src/eval_registry.py"
    for (a, q), g in r.groupby(["asset", "question"]):
        assert (g.role == "champion").sum() == 1, (a, q)
        assert (g.role == "fallback").sum() == 1 and g.loc[g.role == "fallback", "model_id"].item() == rg.FALLBACK[q]
        assert g["reason"].str.strip().str.len().gt(0).all()
    starts = r[(r.role == "champion") & r.question.str.startswith("prob_")]
    assert (starts.reason == rg.START_REASON).all()

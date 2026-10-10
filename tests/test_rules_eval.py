"""Statystyki oceny etapu 5 na danych syntetycznych (bez bazy): Deflated Sharpe, PBO, Sharpe, obsunięcie, reguła D7."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from ms import rules_eval as E


def test_sharpe_and_drawdown():
    ex = pd.Series([0.01, 0.03] * 24)
    assert E.sharpe(ex) == pytest.approx(0.02 / ex.std(ddof=1) * np.sqrt(12))
    v = pd.Series([100, 120, 90, 95, 130.0], index=pd.date_range("2020-01-01", periods=5))
    assert E.max_drawdown(v) == pytest.approx(-0.25)
    assert E.longest_underwater_days(v) == 2


def test_deflated_sharpe_penalises_many_trials():
    sr = 0.3  # miesięczny (~1,04 rocznie)
    one, _ = E.deflated_sharpe(sr, 96, 0.0, 3.0, np.array([sr]))
    many, sr0 = E.deflated_sharpe(sr, 96, 0.0, 3.0, np.linspace(-0.1, 0.3, 50))
    assert one == pytest.approx(stats.norm.cdf(sr * np.sqrt(95) / np.sqrt(1 + sr ** 2 / 2)))  # N=1, normalny: PSR vs 0
    assert many < one and sr0 > 0
    fat, _ = E.deflated_sharpe(sr, 96, -1.0, 9.0, np.array([sr]))
    assert fat < one                                                  # ujemna skośność i grube ogony obniżają


def test_pbo_noise_vs_real_edge():
    rng = np.random.default_rng(1)
    noise = pd.DataFrame(rng.normal(0, 0.04, (96, 12)))
    p_noise, n = E.pbo(noise)
    assert n == 70 and 0.25 < p_noise < 0.75                         # same szumy: wybór najlepszego to loteria
    edge = noise.copy()
    edge[0] += 0.03                                                   # jeden kandydat naprawdę lepszy
    assert E.pbo(edge)[0] < 0.1


def test_select_winner_rule_d7():
    cols = ["sharpe", "max_obsuniecie"]
    dev = pd.DataFrame([[0.5, -0.4], [0.6, -0.3], [0.7, -0.35], [0.4, -0.5]], columns=cols,
                       index=["iv_bez_filtra", "iv_filtr", "iv_filtr_ovx", "rowny_podzial_4"])
    w, _ = E.select_winner(dev, dev)
    assert w == "iv_filtr"                       # V3 ma wyższy Sharpe, ale gorsze obsunięcie niż V2
    x2 = dev.copy()
    x2.loc["iv_filtr", "sharpe"] = 0.3           # przy kosztach x2 przegrywa z równym podziałem
    assert E.select_winner(dev, x2)[0] == "rowny_podzial_4"

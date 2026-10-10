"""Etap 5: ocena wariantów (ZASADY cz. 4) — Sharpe ponad lokatę, Deflated Sharpe, PBO (CSCV), obsunięcia, okna.

Sharpe: miesięczne zwroty wartości konta w PLN (po kosztach i podatku rozliczanym 31.12) minus miesięczny zwrot lokaty,
× √12. Deflated Sharpe (Bailey & López de Prado 2014): prawdopodobieństwo, że prawdziwy Sharpe > 0 po uwzględnieniu
N prób, wariancji ich Sharpe'ów, skośności i kurtozy. PBO (Bailey i in. 2015, CSCV): odsetek podziałów, w których
najlepszy w próbie wariant ląduje poza próbą poniżej mediany.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

EULER = 0.5772156649015329


def monthly(values: pd.Series) -> pd.Series:
    """Zwroty miesięczne z dziennej wartości konta (ostatnia wartość miesiąca; pierwszy miesiąc od wartości startowej)."""
    m = values.resample("ME").last()
    return m.pct_change().fillna(m.iloc[0] / values.iloc[0] - 1)


def sharpe(excess: pd.Series) -> float:
    """Sharpe w skali roku z miesięcznych zwrotów ponad lokatę."""
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd * np.sqrt(12)) if sd > 0 else np.nan


def max_drawdown(values: pd.Series) -> float:
    return float((values / values.cummax() - 1).min())


def longest_underwater_days(values: pd.Series) -> int:
    under = (values < values.cummax()).astype(int)
    return int(under.groupby((under == 0).cumsum()).sum().max())


def deflated_sharpe(sr_m: float, T: int, skew: float, kurt: float, sr_trials_m: np.ndarray) -> tuple[float, float]:
    """(DSR, SR* w skali miesiąca). sr_m, sr_trials_m: Sharpe miesięczne (nieannualizowane); kurt = kurtoza (nie nadwyżka)."""
    N = len(sr_trials_m)
    v = float(np.var(sr_trials_m, ddof=1)) if N > 1 else 0.0
    sr0 = np.sqrt(v) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N) + EULER * stats.norm.ppf(1 - 1 / (N * np.e))) if N > 1 else 0.0
    den = np.sqrt(max(1e-12, 1 - skew * sr_m + (kurt - 1) / 4 * sr_m ** 2))
    return float(stats.norm.cdf((sr_m - sr0) * np.sqrt(T - 1) / den)), float(sr0)


def pbo(returns: pd.DataFrame, n_blocks: int = 8) -> tuple[float, int]:
    """PBO metodą CSCV: kolumny = kandydaci, wiersze = miesiące (zwroty ponad lokatę). (PBO, liczba podziałów)."""
    X = returns.dropna().to_numpy()
    T, N = X.shape
    blocks = np.array_split(np.arange(T), n_blocks)
    logits = []
    for ins in combinations(range(n_blocks), n_blocks // 2):
        i_idx = np.concatenate([blocks[b] for b in ins])
        o_idx = np.concatenate([blocks[b] for b in range(n_blocks) if b not in ins])
        sr_i = X[i_idx].mean(0) / X[i_idx].std(0, ddof=1)
        sr_o = X[o_idx].mean(0) / X[o_idx].std(0, ddof=1)
        best = int(np.nanargmax(sr_i))
        rank = stats.rankdata(sr_o)[best]          # 1 = najgorszy poza próbą
        w = rank / (N + 1)
        logits.append(np.log(w / (1 - w)))
    logits = np.array(logits)
    return float((logits <= 0).mean()), len(logits)


def summary(name: str, values: pd.Series, deposit: pd.Series, final_liq: float, costs: float, tax: float,
            trades: int, cash0: float = 1000.0) -> dict:
    ex = monthly(values) - monthly(deposit)
    years = (values.index[-1] - values.index[0]).days / 365.25
    sr = sharpe(ex)
    yearly = values.resample("YE").last()
    yr = yearly.pct_change().fillna(yearly.iloc[0] / values.iloc[0] - 1)
    return {"wariant": name, "na_reke": final_liq, "zwrot_roczny": (final_liq / cash0) ** (1 / years) - 1,
            "sharpe": sr, "sharpe_po_cieciu_2": sr / 2, "sharpe_po_cieciu_3": sr / 3, "sharpe_po_cieciu_4": sr / 4,
            "t": sr * np.sqrt(years), "max_obsuniecie": max_drawdown(values),
            "najdluzej_pod_kreska_dni": longest_underwater_days(values), "najgorszy_miesiac": float(monthly(values).min()),
            "najgorszy_rok": float(yr.min()), "rebalanse": trades, "koszty": costs, "podatek": tax,
            "skosnosc": float(stats.skew(ex, bias=False)), "kurtoza": float(stats.kurtosis(ex, fisher=False, bias=False)),
            "miesiace": len(ex)}


def windows(values: pd.Series, deposit: pd.Series, edges: list[str]) -> list[dict]:
    """Sharpe i obsunięcie w kolejnych oknach (ta sama ścieżka konta, bez restartu)."""
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        v = values[(values.index >= a) & (values.index < b)]
        d = deposit[(deposit.index >= a) & (deposit.index < b)]
        out.append({"okno": f"{a[:7]}…{b[:7]}", "sharpe": sharpe(monthly(v) - monthly(d)), "max_obsuniecie": max_drawdown(v),
                    "zwrot": float(v.iloc[-1] / v.iloc[0] - 1)})
    return out


def select_winner(dev: pd.DataFrame, dev_x2: pd.DataFrame, order=("iv_bez_filtra", "iv_filtr", "iv_filtr_ovx"),
                  benchmark: str = "rowny_podzial_4") -> tuple[str, list[str]]:
    """Reguła D7 (ustalona przed wynikami). dev/dev_x2: indeks = wariant, kolumny sharpe, max_obsuniecie."""
    why = []
    win = order[0]
    for cand in order[1:]:
        better = dev.loc[cand, "sharpe"] > dev.loc[win, "sharpe"]
        not_worse_dd = dev.loc[cand, "max_obsuniecie"] >= dev.loc[win, "max_obsuniecie"]   # obsunięcia ujemne
        why.append(f"{cand} vs {win}: Sharpe {'wyższy' if better else 'nie wyższy'}, obsunięcie "
                   f"{'nie gorsze' if not_worse_dd else 'gorsze'} -> {'awans' if better and not_worse_dd else 'zostaje ' + win}")
        if better and not_worse_dd:
            win = cand
    beats = [dev.loc[win, "sharpe"] > dev.loc[benchmark, "sharpe"], dev_x2.loc[win, "sharpe"] > dev_x2.loc[benchmark, "sharpe"]]
    why.append(f"{win} vs {benchmark}: koszty x1 {'lepszy' if beats[0] else 'NIE lepszy'}, koszty x2 "
               f"{'lepszy' if beats[1] else 'NIE lepszy'}")
    if not all(beats):
        why.append(f"-> konto system wykonuje {benchmark}")
        return benchmark, why
    return win, why

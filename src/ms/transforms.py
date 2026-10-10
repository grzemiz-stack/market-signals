"""Przekształcenia na seriach z as_of(). Bez ukrytych założeń: wartości <= 0 nie dają log-zwrotu."""

from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(values: pd.Series) -> pd.DataFrame:
    """Log-zwroty z flagą. Gdy bieżąca lub poprzednia wartość <= 0 (np. WTI 2020-04-20):
    logret = NaN, flag = 'nonpositive_input' — nie wyjątek, nie cichy NaN."""
    v = values.astype(float)
    prev = v.shift(1)
    bad = (v <= 0) | (prev <= 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.log(v / prev)
    lr = lr.where(~bad)
    flag = pd.Series(np.where(bad, "nonpositive_input", None), index=v.index, dtype=object)
    return pd.DataFrame({"value": v, "logret": lr, "flag": flag})


SEAM_COMMON_DAYS = 5


def stitch(stooq: pd.Series, yf: pd.Series, n_common: int = SEAM_COMMON_DAYS) -> pd.DataFrame:
    """Łączy szereg główny (Stooq spot / EIA spot; do jego ostatniego dnia) z futures Yahoo (dni po nim).
    Nazwy argumentów historyczne: stooq = szereg główny, yf = uzupełnienie.

    Poziomy: YF po szwie przeskalowane współczynnikiem bazy = mediana(close_stooq / close_yf) z ostatnich
    n_common wspólnych dni (<= koniec Stooq).
    Zwrot w dniu szwu: zamknięcia Stooq (spot, wieczór CET) i Yahoo (futures, settlement NY) są niesynchroniczne —
    stosunek spot/futures srebra skacze dziennie o ±1–2% (sprawdzone 2026-10-06), więc żaden stały współczynnik
    nie usuwa skoku. Dlatego gdy ostatni dzień Stooq jest też w YF, zwrot w dniu szwu = log(F[t1]/F[t0])
    (czysty ruch rynku, flaga 'seam_chained'); inaczej zwrot z poziomów skalowanych ('seam_scaled');
    brak wspólnych dni -> NaN, flaga 'seam'.
    Skutek: w dniu szwu zmiana poziomu != logret. Etykiety liczymy z kolumny logret, nie z poziomów.

    stooq, yf: close indeksowane datą. Zwraca: value, source (stooq|yahoo), logret, flag, basis_factor.
    Etykiety metali liczymy WYŁĄCZNIE z tej funkcji.
    """
    stooq = stooq.dropna().sort_index()
    yf = yf.dropna().sort_index()
    seam = stooq.index.max()
    common = stooq.index.intersection(yf.index)
    common = common[common <= seam][-n_common:]
    factor = float((stooq.loc[common] / yf.loc[common]).median()) if len(common) else np.nan

    tail = yf[yf.index > seam]
    out = pd.concat([
        pd.DataFrame({"value": stooq, "source": "stooq"}),
        pd.DataFrame({"value": tail * factor if len(common) else tail, "source": "yahoo"}),
    ])
    lr = log_returns(out["value"])
    out["logret"], out["flag"] = lr["logret"], lr["flag"]
    out["basis_factor"] = np.where(out["source"] == "yahoo", factor, np.nan)
    if len(tail):
        first = tail.index.min()
        if not len(common):
            out.loc[first, "logret"] = np.nan
            out.loc[first, "flag"] = "seam"
        elif out.loc[first, "flag"] is None:
            if seam in yf.index and yf[seam] > 0 and yf[first] > 0:
                out.loc[first, "logret"] = float(np.log(yf[first] / yf[seam]))
                out.loc[first, "flag"] = "seam_chained"
            else:
                out.loc[first, "flag"] = "seam_scaled"
    return out


def stitch_metals(stooq: pd.Series, yf: pd.Series, n_common: int = SEAM_COMMON_DAYS) -> pd.DataFrame:
    """Metale: Stooq spot + Yahoo GC=F/SI=F. Etykiety metali liczymy wyłącznie stąd (kolumna logret)."""
    return stitch(stooq, yf, n_common)

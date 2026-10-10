"""Prawdopodobieństwo dużego ruchu w 5 dni — model wskazuje REJESTR (ms.registry.champion), nie ten moduł.

Duży ruch = suma logret 5 dni > +1,5σ (w górę) / < −1,5σ (w dół), σ = std 252 dziennych logret do ostatniego
znanego zamknięcia × √5. Częstość bazowa = etykiety zakończone przed D.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ms import registry, wf
from ms.baselines import K_SIGMA
from ms.models import catalog


@dataclass
class Prob:
    asset: str
    date: pd.Timestamp            # dzień decyzji, którego dotyczy prognoza (<= zapytanie)
    model_up: str
    model_down: str
    p_up: float
    p_down: float
    base_up: float
    base_down: float
    card_up: str                  # wizytówka mistrza z rejestru
    card_down: str
    x_up_pct: float
    x_down_pct: float


def _model(model_id: str, question: str):
    return next(m for m in catalog.all_models() if m.id == model_id and m.question == question)


def probability(con, asset: str, when, d: wf.AssetData | None = None) -> Prob:
    d = d or wf.load(con, asset)
    t = d.table
    day = t.index[t.index <= pd.Timestamp(when).normalize()].max()
    out = {}
    for q, key in (("prob_up_5d", "up"), ("prob_down_5d", "down")):
        ch = registry.champion(con, asset, q)
        f = _model(ch.model_id, q).frame(con, asset)
        out[key] = (ch.model_id, float(f.get(day, np.nan)), ch.card)
    base = wf.base_rate(t).loc[day]
    pl = int(t.loc[day, "pos_l"])
    sigma = float(np.std(d.r[pl - 251 : pl + 1], ddof=1) * np.sqrt(5))  # do ostatniego znanego zamknięcia
    return Prob(asset, day, out["up"][0], out["down"][0], out["up"][1], out["down"][1],
                float(base["base_up"]), float(base["base_down"]), out["up"][2], out["down"][2],
                100 * np.expm1(K_SIGMA * sigma), 100 * -np.expm1(-K_SIGMA * sigma))


def _pl(x: float, fmt: str) -> str:
    return "—" if not np.isfinite(x) else format(x, fmt).replace(".", ",")


def text(p: Prob) -> str:
    up = f"Szansa na ruch >{_pl(p.x_up_pct, '.1f')}% w górę w 5 dni: {_pl(100 * p.p_up, '.1f')}% (zwykle {_pl(100 * p.base_up, '.1f')}%)."
    down = (f"Szansa na ruch >{_pl(p.x_down_pct, '.1f')}% w dół w 5 dni: {_pl(100 * p.p_down, '.1f')}% "
            f"(zwykle {_pl(100 * p.base_down, '.1f')}%).")
    if p.card_up == p.card_down:
        model = f"Model: {p.card_up}"
    else:
        model = f"Model w górę: {p.card_up} Model w dół: {p.card_down}"
    return f"{p.asset} ({p.date.date()}): {up} {down} {model}"

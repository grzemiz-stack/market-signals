import copy

import pandas as pd
import pytest

from ms import prob, registry, wf


def _p(**kw):
    base = dict(asset="WTI", date=pd.Timestamp("2026-10-05"), model_up="iv_calibrated", model_down="iv_calibrated",
                p_up=0.013, p_down=0.03, base_up=0.051, base_down=0.068, card_up="Odpowiada: OVX skalibrowany. X.",
                card_down="Odpowiada: OVX skalibrowany. X.", x_up_pct=13.04, x_down_pct=11.5)
    base.update(kw)
    return prob.Prob(**base)


def test_text_template():
    t = prob.text(_p())
    assert "Szansa na ruch >13,0% w górę w 5 dni: 1,3% (zwykle 5,1%)." in t
    assert "Szansa na ruch >11,5% w dół w 5 dni: 3,0% (zwykle 6,8%)." in t
    assert t.endswith("Model: Odpowiada: OVX skalibrowany. X.")
    assert "Model w dół:" in prob.text(_p(card_down="Odpowiada: HAR-RV."))


@pytest.mark.data
@pytest.mark.parametrize("asset,day", [("WTI", "2024-05-15"), ("BTC", "2025-02-12"), ("XAU", "2026-10-06")])
def test_probability_uses_registry_champion(real, asset, day):
    d = wf.load(real, asset)
    p = prob.probability(real, asset, day, d)
    for q, mid, card in (("prob_up_5d", p.model_up, p.card_up), ("prob_down_5d", p.model_down, p.card_down)):
        ch = registry.champion(real, asset, q)
        assert mid == ch.model_id and card == ch.card
    assert p.base_up == wf.base_rate(d.table).loc[p.date, "base_up"]
    d2 = copy.deepcopy(d)  # próg X tylko z danych do ostatniego znanego zamknięcia
    d2.r[int(d.table.loc[p.date, "pos_l"]) + 1:] = 0.5
    assert prob.probability(real, asset, day, d2).x_up_pct == p.x_up_pct

"""Wykresy dashboardu (dashboard.common): logika osi bez danych i bez serwera."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_time_axis_ticks_follow_range_length():
    """Podziałka osi X wg długości zakresu: dni (do 31 dni), miesiące (do roku), co 3 miesiące (dłużej)."""
    from dashboard.common import time_axis

    assert time_axis(4) == ({"interval": "day", "step": 1}, "%Y-%m-%d")
    assert time_axis(31) == ({"interval": "day", "step": 1}, "%Y-%m-%d")
    assert time_axis(32) == ({"interval": "month", "step": 1}, "%Y-%m")
    assert time_axis(365) == ({"interval": "month", "step": 1}, "%Y-%m")
    assert time_axis(730) == ({"interval": "month", "step": 3}, "%Y-%m")



def test_daily_chart_axes_without_data():
    """daily_chart na syntetycznych seriach: oś Y nie od zera, podziałka wg zakresu (5 dni -> dni, 2 lata -> kwartały)."""
    from dashboard.common import daily_chart

    for days, ticks in ((5, {"interval": "day", "step": 1}), (730, {"interval": "month", "step": 3})):
        s = pd.Series(1000.0, index=pd.date_range("2024-01-01", periods=days + 1, freq="D"), name="x")
        enc = daily_chart(s).to_dict()["encoding"]
        assert enc["y"]["scale"]["zero"] is False and enc["x"]["timeUnit"] == "yearmonthdate"
        assert enc["x"]["axis"]["tickCount"] == ticks

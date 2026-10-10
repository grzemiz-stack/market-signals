"""Jedno formatowanie liczb do wyświetlenia (CLI paper.py i dashboard): zł, %, punkty procentowe, przecinek dziesiętny."""

from __future__ import annotations

import numpy as np

GROUP_PL = {"koszt_alternatywny": "koszt alternatywny", "ryzyko": "ryzyko", "momentum_pozycje": "momentum/pozycje",
            "ropa_podaz": "podaż ropy", "krzyzowe": "krzyżowe"}


def zl(x: float) -> str:
    return f"{x:,.2f} zł".replace(",", " ").replace(".", ",")


def pct(x: float) -> str:
    return "—" if not np.isfinite(x) else f"{x:+.1%}".replace(".", ",")


def pp(x: float) -> str:
    """Udział w zwrocie w punktach procentowych."""
    return f"{100 * x:+.2f}".replace(".", ",") + " pp"


def pct0(x: float) -> str:
    return f"{x:.0%}"


def units(x: float) -> str:
    return f"{x:.6f}"


def vol_label(rv20: float, rv1y: float) -> str:
    return " — **podwyższona**." if rv20 > 1.25 * rv1y else " — obniżona." if rv20 < 0.8 * rv1y else "."


def num2(x: float) -> str:
    return "—" if not np.isfinite(x) else f"{x:.2f}".replace(".", ",")


def num3(x: float) -> str:
    return "—" if not np.isfinite(x) else f"{x:.3f}".replace(".", ",")

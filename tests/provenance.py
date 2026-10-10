"""Pochodzenie liczb na ekranie (etap 4C): każda liczba w wydruku/na stronie musi pochodzić z ms.views
(sformatowana przez ms.fmt albo zawarta w gotowym tekście z widoku). Wspólne dla testów CLI i dashboardu."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ms import fmt

NUM = re.compile(r"(?<![\w.])[+\-−]?\d[\d  ]*(?:,\d+)?(?:\s?(?:zł|%|pp))?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
FORMATTERS = (fmt.zl, fmt.pct, fmt.pp, fmt.pct0, fmt.units, fmt.num2, fmt.num3)


def allowed_strings(*views) -> tuple[set[str], list[str]]:
    """(sformatowane liczby z widoków, gotowe teksty z widoków). Przechodzi rekurencyjnie po słownikach/listach/tabelach."""
    nums, texts = set(), []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, pd.DataFrame):
            texts.append(x.to_markdown(index=False))
            for col in x.columns:
                for v in x[col].tolist():
                    walk(v)
        elif isinstance(x, pd.Series):
            return  # ścieżki (wykresy) nie są drukowane jako tekst
        elif isinstance(x, str):
            texts.append(x)
            texts.extend(DATE.findall(x))          # data z godziną w widoku, w wydruku sam dzień
        elif isinstance(x, pd.Timestamp):
            texts.append(str(x.date()))
        elif isinstance(x, (int, float, np.floating, np.integer)) and np.isfinite(x):
            for f in FORMATTERS:
                try:
                    nums.add(f(float(x)).strip())
                except (ValueError, TypeError):
                    pass
            nums.add(str(int(x)) if float(x).is_integer() else str(x))

    for v in views:
        walk(v)
    return nums, texts


def foreign_numbers(text: str, *views) -> list[str]:
    """Liczby z `text`, których nie da się wyprowadzić z widoków. Pusta lista = wszystko z ms.views."""
    nums, texts = allowed_strings(*views)
    for t in sorted(texts, key=len, reverse=True):     # usuń gotowe teksty z widoków (np. prob_text, tabela zleceń)
        if t and len(t) > 3:
            text = text.replace(t, " ")
    found = [m.group(0).strip() for m in NUM.finditer(text)]
    return [n for n in found if n and n not in nums and not re.fullmatch(r"\d{1,2}", n)]

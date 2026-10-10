"""Interfejs modelu dla rejestru."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import pandas as pd

QUESTIONS = ("prob_up_5d", "prob_down_5d", "decomp_weekly", "event_response")


@dataclass
class Model:
    id: str
    question: str
    assets: tuple[str, ...]
    params: dict = field(default_factory=dict)
    display: str = ""

    def __post_init__(self):
        assert self.question in QUESTIONS, self.question

    @property
    def params_hash(self) -> str:
        return hashlib.sha256(json.dumps({"id": self.id, **self.params}, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def frame(self, con, asset: str) -> pd.Series:
        """Prognozy walk-forward (indeks: dzień decyzji). Dla prob_*: prawdopodobieństwo; dla decomp: ŷ tygodnia."""
        raise NotImplementedError

    def predict(self, con, asset: str, D) -> float:
        f = self.frame(con, asset)
        f = f[f.index <= pd.Timestamp(D)]
        return float(f.iloc[-1]) if len(f) else float("nan")

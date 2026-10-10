"""Modele odpowiadające na pytania rejestru. Każdy: id, question, assets, params, predict(con, asset, D),
frame(con, asset) (prognozy walk-forward na dniach decyzji — tylko dane znane w D)."""

from ms.models.base import Model  # noqa: F401
from ms.models.catalog import all_models  # noqa: F401

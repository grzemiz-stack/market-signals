"""Karty moich aktywów (aktywa gry)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dashboard import cards  # noqa: E402
from dashboard.common import header  # noqa: E402
from ms.trading import GAME_ASSETS  # noqa: E402

header("Karty moich aktywów")
cards.render(GAME_ASSETS)

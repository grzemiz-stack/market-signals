"""Pozostałe aktywa (obserwowane, poza grą)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dashboard import cards  # noqa: E402
from dashboard.common import header  # noqa: E402

header("Pozostałe aktywa")
cards.render(("XAU", "BRENT"))

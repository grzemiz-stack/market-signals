"""Analogie historyczne dla aktywa i daty.

uv run src/analogs.py --asset XAU --date 2026-10-06 [--k 20]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import analogs, db  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True, choices=["XAU", "XAG", "WTI", "BRENT", "BTC", "ETH"])
    ap.add_argument("--date", required=True)
    ap.add_argument("--k", type=int, default=analogs.K)
    a = ap.parse_args()
    con = db.connect(db.DB_PATH, read_only=True)
    print(analogs.to_markdown(analogs.find(con, a.asset, a.date, a.k)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Przebudowa w całości: features_daily i labels w data/market.duckdb (osobne tabele).

uv run src/build_features.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, features, labels  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "features.log"), logging.StreamHandler()])
    t0 = time.time()
    con = db.connect()
    df = features.build(con)
    features.write(con, df)
    logging.getLogger("features").info("features_daily: %d wierszy, %.0f s", len(df), time.time() - t0)
    lab = labels.build(con)
    labels.write(con, lab)
    logging.getLogger("features").info("labels: %d wierszy\n%s", len(lab), labels.base_rates(con).to_string())
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Import/aktualizacja warstwy danych (data/market.duckdb).

uv run src/collect.py                 # wszystkie, przyrostowo
uv run src/collect.py fred cot        # wybrane
uv run src/collect.py --full fred     # pełna historia od nowa (ingest i tak idempotentny)
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db  # noqa: E402

COLLECTORS: list[str] = [  # kolejność = kolejność uruchamiania
    "metals_stooq",
    "binance_klines",
    "funding",
    "binance_metrics",
    "dvol",
    "eia_spot",
    "eia_wpsr",
    "yf_oil",
    "yf_metals",
    "curve",
    "fred",
    "cot",
    "fng",
    "nbp",
    "nbp_rates",
    "eia_steo",
    "coinmetrics_stables",
    "bh_shocks",
    "events_calendar",
    "gpr_tpu",
    "coinmetrics",
    "inbox",
]

LOG = db.ROOT / "logs" / "collect.log"


def main(argv: list[str]) -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
    for noisy in ("yfinance", "urllib3", "cot_reports"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger("collect")
    full = "--full" in argv
    names = [a for a in argv[1:] if not a.startswith("--")] or COLLECTORS
    unknown = set(names) - set(COLLECTORS)
    if unknown:
        log.error("nieznane kolektory: %s", unknown)
        return 2
    con = db.connect()
    failed = []
    for name in names:
        try:
            mod = importlib.import_module(f"ms.collectors.{name}")
            n = mod.collect(con, full=full)
            log.info("%s: +%d wierszy", name, n)
        except Exception:
            log.exception("kolektor %s padł", name)
            failed.append(name)
    con.close()
    log.info("koniec; padły: %s", failed or "brak")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

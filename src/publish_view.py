"""Publikuje kopię bazy dla dashboardu: data/market_view.duckdb (etap 4C, D1).

uv run src/publish_view.py   # ostatni krok jobów piszących do market.duckdb (snapshot, registry)

Dashboard nie otwiera market.duckdb (blokady DuckDB między procesami wywróciłyby joby) — czyta tę kopię tylko do
odczytu. CHECKPOINT (wszystko w pliku głównym) -> kopia do pliku tymczasowego -> podmiana jednym rename (atomowo).
Metadane: data/market_view.json (czas publikacji, rozmiar).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db  # noqa: E402

VIEW = db.ROOT / "data" / "market_view.duckdb"
META = db.ROOT / "data" / "market_view.json"


def publish(src: Path = db.DB_PATH, dst: Path = VIEW, meta: Path = META) -> dict:
    import duckdb

    con = duckdb.connect(str(src))       # bez db.connect: nie tworzyć tabel rynkowych w obcej bazie (np. news.duckdb)
    con.execute("CHECKPOINT")
    con.close()
    tmp = dst.with_suffix(".duckdb.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    info = {"published_at": str(pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")), "bytes": dst.stat().st_size,
            "source": str(src)}
    tmpm = meta.with_suffix(".json.tmp")
    tmpm.write_text(json.dumps(info))
    os.replace(tmpm, meta)
    return info


if __name__ == "__main__":
    print(publish())

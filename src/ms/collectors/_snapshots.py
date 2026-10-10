"""Wspólne: pliki snapshotów z data/raw/ + czas pobrania z manifestu (= known_at)."""

from __future__ import annotations

import json

import pandas as pd

from ms.common import RAW


def snapshot_files(source: str) -> list[tuple[pd.Timestamp, "Path", dict]]:  # noqa: F821
    """[(fetched_at UTC naive, ścieżka, wpis manifestu)] posortowane po fetched_at.
    Ten sam path zapisany ponownie z identyczną treścią -> liczy się najwcześniejsze pobranie."""
    best: dict[str, tuple[pd.Timestamp, dict]] = {}
    for line in (RAW / "manifest.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e.get("source") != source or not e.get("path"):
            continue
        t = pd.Timestamp(e["fetched_at"]).tz_convert("UTC").tz_localize(None)
        if e["path"] not in best or t < best[e["path"]][0]:
            best[e["path"]] = (t, e)
    root = RAW.parent.parent
    return sorted(((t, root / p, e) for p, (t, e) in best.items() if (root / p).exists()), key=lambda x: x[0])


def done(con, path) -> bool:
    return con.execute("SELECT count(*) FROM ingest_log WHERE path=?", [str(path)]).fetchone()[0] > 0


def mark(con, path) -> None:
    from ms.db import utcnow

    con.execute("INSERT OR REPLACE INTO ingest_log VALUES (?, ?)", [str(path), utcnow()])

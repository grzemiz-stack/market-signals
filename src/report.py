"""Raport pokrycia: per seria start, koniec, wiersze, % dziur, licencja -> reports/coverage-{data}.md

% dziur = brakujące punkty oczekiwanej siatki / liczność siatki, gdzie siatka zależy od częstotliwości:
  1d_all: każdy dzień; 1d_bday: pn–pt bez świąt federalnych USA (dla NBP/Stooq to przybliżenie);
  8h / 5min: równa siatka; 1w / 1m / 1q: liczba okresów między startem a końcem.
Liczone na as_of(teraz) — bez forward-fill, brak = brak.
Wiersze sparse_history (rzadka wczesna historia, np. Stooq przed notowaniami dziennymi) są poza siatką:
`start` = początek notowań dziennych, `start_danych` = najstarszy wiersz, `rzadkie` = ich liczba.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db  # noqa: E402
from ms.common import us_holidays  # noqa: E402


def expected(freq: str, start: pd.Timestamp, end: pd.Timestamp, obs: pd.Series | None) -> tuple[int, int]:
    """(oczekiwane, brakujące)."""
    if freq == "1d_bday":
        hol = {pd.Timestamp(d) for d in us_holidays()}
        grid = [d for d in pd.bdate_range(start.normalize(), end.normalize()) if d not in hol]
        have = set(pd.to_datetime(obs).dt.normalize())
        return len(grid), sum(d not in have for d in grid)
    step = {"1d_all": "1D", "8h": "8h", "5min": "5min"}.get(freq)
    if step:
        n = int((end - start) / pd.Timedelta(step)) + 1
    elif freq == "1w":
        n = int(round((end - start).days / 7)) + 1
    elif freq == "1m":
        n = (end.year - start.year) * 12 + end.month - start.month + 1
    elif freq == "1q":
        n = (end.year - start.year) * 4 + (end.quarter - start.quarter) + 1
    else:
        return 0, 0
    return n, max(0, n - len(obs) if obs is not None else 0)


def build(con) -> pd.DataFrame:
    stats = con.execute("""
        WITH cur AS (SELECT * FROM as_of(now()::TIMESTAMP))
        SELECT s.source, s.series_id, s.frequency, s.license,
               min(c.observed_at) AS start_danych,
               min(c.observed_at) FILTER (WHERE NOT contains(coalesce(c.flags, ''), 'sparse_history')) AS start,
               max(c.observed_at) AS koniec,
               count(c.observed_at) FILTER (WHERE NOT contains(coalesce(c.flags, ''), 'sparse_history')) AS obserwacje,
               count(c.observed_at) FILTER (WHERE contains(coalesce(c.flags, ''), 'sparse_history')) AS rzadkie,
               (SELECT count(*) FROM observations o WHERE o.source = s.source AND o.series_id = s.series_id) AS wersje,
               count(*) FILTER (WHERE contains(coalesce(c.flags, ''), 'known_at_')) AS reguła
        FROM series s LEFT JOIN cur c USING (source, series_id)
        GROUP BY ALL ORDER BY s.source, s.series_id
    """).df()
    gaps = []
    for r in stats.itertuples():
        if pd.isna(r.start):
            gaps.append(None)
            continue
        obs = None
        if r.frequency == "1d_bday":
            obs = con.execute("SELECT observed_at FROM as_of(now()::TIMESTAMP) WHERE source=? AND series_id=? "
                              "AND NOT contains(coalesce(flags, ''), 'sparse_history')",
                              [r.source, r.series_id]).df()["observed_at"]
        else:
            obs = pd.Series(range(r.obserwacje))
        n, miss = expected(r.frequency, r.start, r.koniec, obs)
        gaps.append(round(100 * miss / n, 2) if n else None)
    stats["dziury_%"] = gaps
    stats["known_at_reguła_%"] = (100 * stats["reguła"] / stats["obserwacje"].where(stats["obserwacje"] > 0)).round(1)
    return stats.drop(columns=["reguła"])


def main() -> int:
    con = db.connect(db.DB_PATH, read_only=True)
    df = build(con)
    out = db.ROOT / "reports" / f"coverage-{date.today()}.md"
    out.parent.mkdir(exist_ok=True)
    df["start"] = df["start"].astype(str).str[:16]
    df["start_danych"] = df["start_danych"].astype(str).str[:16]
    df["koniec"] = df["koniec"].astype(str).str[:16]
    head = (f"# Pokrycie danych — {date.today()}\n\n"
            f"Serie: {len(df)}, obserwacje (as_of teraz): {int(df.obserwacje.sum()):,}, wiersze z wersjami: {int(df.wersje.sum()):,}.\n\n"
            "dziury_% wg kalendarza częstotliwości (1d_bday = pn–pt bez świąt federalnych USA). "
            "known_at_reguła_% = udział obserwacji z known_at z reguły (nie z daty publikacji podanej przez źródło).\n\n")
    out.write_text(head + df.to_markdown(index=False) + "\n")
    print(out)
    by_source = df.groupby("source").agg(serie=("series_id", "count"), obserwacje=("obserwacje", "sum"),
                                         wersje=("wersje", "sum"), max_dziury=("dziury_%", "max"))
    print(by_source.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

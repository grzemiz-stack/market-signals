"""Kolektory. Każdy moduł: NAME, collect(con, full: bool) -> int (liczba nowych wierszy)."""

from __future__ import annotations

import pandas as pd

from ms import db
from ms.common import validate_output


def write(con, df: pd.DataFrame) -> int:
    """Walidacja schematu wyjścia (pandera, twardy błąd) + wersjonujący ingest."""
    if df is None or df.empty:
        return 0
    return db.ingest(con, validate_output(df))


def write_exact(con, df: pd.DataFrame) -> int:
    """Walidacja + zapis bez deduplikacji po wartości (wersje równoległe, np. known_at_approx)."""
    if df is None or df.empty:
        return 0
    return db.insert_exact(con, validate_output(df))


def approx_versions(df: pd.DataFrame, lag: pd.Timedelta) -> pd.DataFrame:
    """Przybliżona wersja historyczna: known_at = observed_at + lag, flaga known_at_approx.
    Tylko gdy przybliżenie jest WCZEŚNIEJSZE niż właściwa wersja (inaczej cofnęłoby późniejszą rewizję)."""
    a = df[df["observed_at"] + lag < df["known_at"]].copy()
    a["known_at"] = a["observed_at"] + lag
    a["flags"] = "known_at_approx"
    if "vintage" in a:
        a["vintage"] = None
    return a


def first_seen(con, df: pd.DataFrame) -> pd.DataFrame:
    """Wiersze, których obserwacja NIE ma wcześniejszej (nie-przybliżonej) wersji w bazie.
    Wersja przybliżona może pochodzić tylko z pierwszego snapshotu z daną obserwacją — z późniejszego
    przeniosłaby rewizję wstecz w czasie (wyciek)."""
    if df.empty:
        return df
    con.register("fs_df", df[["source", "series_id", "observed_at", "known_at"]])
    keep = con.execute("""
        SELECT f.source, f.series_id, CAST(f.observed_at AS TIMESTAMP) AS observed_at FROM fs_df f
        WHERE NOT EXISTS (SELECT 1 FROM observations o
                          WHERE o.source = f.source AND o.series_id = f.series_id
                            AND o.observed_at = CAST(f.observed_at AS TIMESTAMP)
                            AND o.known_at < CAST(f.known_at AS TIMESTAMP)
                            AND NOT contains(coalesce(o.flags, ''), 'known_at_approx'))
    """).df()
    con.unregister("fs_df")
    return df.merge(keep, on=["source", "series_id", "observed_at"])

"""DuckDB: schemat, wersjonujący ingest i zapytania point-in-time.

Konwencje:
- observed_at, known_at, ingested_at: TIMESTAMP bez strefy, zawsze UTC.
- Wiersz = jedna wersja wartości. Ta sama obserwacja może mieć wiele wierszy
  z różnym known_at (rewizje, vintage ALFRED, kolejne snapshoty).
- Model czyta wyłącznie przez as_of(ts) / panel_asof() — nigdy wprost z observations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("MS_DB", ROOT / "data" / "market.duckdb"))  # MS_DB: baza robocza do prób

LICENSES = ("public_domain", "cc_by", "cc_by_nc", "tos_restricted")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS observations (
    source      VARCHAR   NOT NULL,
    series_id   VARCHAR   NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    known_at    TIMESTAMP NOT NULL,
    value       DOUBLE    NOT NULL,
    vintage     DATE,
    ingested_at TIMESTAMP NOT NULL,
    license     VARCHAR   NOT NULL CHECK (license IN {LICENSES}),
    flags       VARCHAR,
    PRIMARY KEY (source, series_id, observed_at, known_at)
);

CREATE TABLE IF NOT EXISTS series (
    source      VARCHAR NOT NULL,
    series_id   VARCHAR NOT NULL,
    frequency   VARCHAR NOT NULL,   -- 5min | 8h | 1d_all | 1d_bday | 1w | 1m | 1q | irregular
    description VARCHAR,
    license     VARCHAR NOT NULL CHECK (license IN {LICENSES}),
    PRIMARY KEY (source, series_id)
);

CREATE TABLE IF NOT EXISTS releases (
    source       VARCHAR NOT NULL,
    release_id   VARCHAR NOT NULL,
    release_name VARCHAR,
    release_date DATE    NOT NULL,
    PRIMARY KEY (source, release_id, release_date)
);

CREATE TABLE IF NOT EXISTS events (
    source       VARCHAR   NOT NULL,
    event_id     VARCHAR   NOT NULL,
    observed_at  TIMESTAMP NOT NULL,
    known_at     TIMESTAMP NOT NULL,
    event_code   VARCHAR,
    root_code    VARCHAR,
    actor1       VARCHAR,
    actor2       VARCHAR,
    goldstein    DOUBLE,
    num_mentions INTEGER,
    avg_tone     DOUBLE,
    action_geo   VARCHAR,
    source_url   VARCHAR,
    ingested_at  TIMESTAMP NOT NULL,
    license      VARCHAR   NOT NULL CHECK (license IN {LICENSES}),
    PRIMARY KEY (source, event_id)
);

CREATE TABLE IF NOT EXISTS series_gaps (   -- luki oznaczone, NIE wypełniane
    series_id VARCHAR NOT NULL, gap_from DATE NOT NULL, gap_to DATE NOT NULL, reason VARCHAR NOT NULL,
    PRIMARY KEY (series_id, gap_from)
);

CREATE TABLE IF NOT EXISTS events_calendar (   -- daty zdarzeń do badań zdarzeń (FOMC, OPEC, huragany)
    source VARCHAR NOT NULL, event_type VARCHAR NOT NULL, event_id VARCHAR NOT NULL,
    event_date DATE NOT NULL, known_at TIMESTAMP NOT NULL, value DOUBLE, note VARCHAR, license VARCHAR NOT NULL,
    PRIMARY KEY (source, event_id)
);

-- Etap 4N: przyczyny dużych ruchów. TYLKO wyjaśnianie i badania zdarzeń, NIGDY cecha prognozy (test w bramce).
CREATE TABLE IF NOT EXISTS cause_events (   -- zdarzenia z opisem: chronologie ropy, hacki, daty krypto, niespodzianki FOMC
    source VARCHAR NOT NULL, event_id VARCHAR NOT NULL, event_date DATE NOT NULL, date_precision VARCHAR NOT NULL,
    category VARCHAR, assets VARCHAR, value DOUBLE, text VARCHAR, url VARCHAR, verified VARCHAR,
    license VARCHAR NOT NULL, raw_sha VARCHAR,
    PRIMARY KEY (source, event_id)
);

CREATE TABLE IF NOT EXISTS bbds_codings (   -- BBDS: ludzkie kodowania przyczyn skoków akcji USA (zbiór E1)
    date DATE NOT NULL, row_no INTEGER NOT NULL, coder VARCHAR, ret DOUBLE, primary_cat VARCHAR, secondary_cat VARCHAR,
    ease DOUBLE, journalist_conf DOUBLE, title VARCHAR, passage VARCHAR, newspaper VARCHAR, license VARCHAR NOT NULL,
    PRIMARY KEY (row_no)
);

CREATE TABLE IF NOT EXISTS move_causes (   -- jedna przypisana przyczyna dużego ruchu; tylko dopisywanie
    asset VARCHAR NOT NULL, day DATE NOT NULL, ret DOUBLE NOT NULL, sigma DOUBLE NOT NULL, z DOUBLE NOT NULL,
    cause VARCHAR NOT NULL, rank TINYINT NOT NULL, label_source VARCHAR NOT NULL CHECK (label_source IN ('calendar', 'study', 'llm')),
    source_ref VARCHAR NOT NULL, evidence VARCHAR, model VARCHAR NOT NULL DEFAULT '', prompt_version VARCHAR,
    prompt_hash VARCHAR NOT NULL DEFAULT '', confidence DOUBLE NOT NULL, validated BOOLEAN NOT NULL, license VARCHAR,
    run_id VARCHAR NOT NULL, known_at TIMESTAMP NOT NULL,
    status VARCHAR DEFAULT 'kandydat' CHECK (status IN ('kandydat', 'potwierdzona')),
    PRIMARY KEY (asset, day, cause, label_source, source_ref, model, prompt_hash)
);
-- 4N (2026-10-06): kalendarz daje tylko KANDYDATA przyczyny („tego dnia było: …”); potwierdza tekst
-- (zwalidowany Qwen albo człowiek). Migracja dla bazy sprzed kolumny status.
ALTER TABLE move_causes ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'kandydat';

CREATE TABLE IF NOT EXISTS ingest_log (   -- przetworzone pliki snapshotów
    path        VARCHAR PRIMARY KEY,
    ingested_at TIMESTAMP NOT NULL
);

-- Równość z tolerancją szumu float (parsowanie CSV); prawdziwe rewizje są o rzędy większe.
CREATE OR REPLACE MACRO close_enough(a, b) AS abs(a - b) <= 1e-9 * greatest(1.0, abs(b));

-- Stan wiedzy na chwilę ts: dla każdej obserwacji ostatnia wersja znana do ts.
CREATE OR REPLACE MACRO as_of(ts) AS TABLE
    SELECT source, series_id, observed_at,
           arg_max(value, known_at)   AS value,
           max(known_at)              AS known_at,
           arg_max(vintage, known_at) AS vintage,
           arg_max(license, known_at) AS license,
           arg_max(flags, known_at)   AS flags
    FROM observations
    WHERE known_at <= ts
    GROUP BY source, series_id, observed_at;

-- Strumień "najnowsza obserwacja serii": tylko wiersze, które w chwili known_at
-- dotyczą najpóźniejszej znanej obserwacji (nowy punkt albo rewizja ostatniego).
-- Wejście dla ASOF JOIN po known_at (panel_asof).
CREATE OR REPLACE VIEW latest_stream AS
    SELECT * FROM (
        SELECT *, max(observed_at) OVER (
                      PARTITION BY source, series_id ORDER BY known_at
                      RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS max_obs
        FROM observations
    ) WHERE observed_at = max_obs;
"""


def connect(path: Path | str = DB_PATH, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if not read_only:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    con.execute("SET TimeZone = 'UTC'")
    if not read_only:
        con.execute(SCHEMA)
    return con


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def register_series(con, source: str, rows: list[tuple[str, str, str]], license: str) -> None:
    """rows: (series_id, frequency, description)."""
    con.executemany(
        "INSERT OR REPLACE INTO series VALUES (?, ?, ?, ?, ?)",
        [(source, sid, freq, desc, license) for sid, freq, desc in rows],
    )


def ingest(con, df: pd.DataFrame) -> int:
    """Wersjonujący, idempotentny zapis do observations. Zwraca liczbę nowych wierszy.

    df: source, series_id, observed_at, known_at, value, license, [vintage], [flags].
    Wiersz jest pomijany, gdy ostatnia wersja znana w jego known_at ma tę samą wartość
    (dotyczy też wierszy wcześniejszych w tej samej partii).
    Gdy pod tym samym kluczem i known_at już jest INNA wartość (korekta źródła przy
    known_at z reguły), nowa wersja dostaje known_at = teraz i flagę 'revised'.
    """
    if df.empty:
        return 0
    df = df.copy()
    for c in ("vintage", "flags"):
        if c not in df:
            df[c] = None
    df = df[["source", "series_id", "observed_at", "known_at", "value", "vintage", "license", "flags"]]
    df = df[pd.notna(df["value"]) & ~df["value"].isin([float("inf"), float("-inf")])]
    if df.empty:
        return 0
    now = utcnow()
    before = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    con.register("stage_df", df)
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE stage AS
        SELECT source, series_id,
               CAST(observed_at AS TIMESTAMP) AS observed_at,
               CAST(known_at AS TIMESTAMP)    AS known_at,
               CAST(value AS DOUBLE)          AS value,
               CAST(vintage AS DATE)          AS vintage,
               CAST(license AS VARCHAR) AS license, CAST(flags AS VARCHAR) AS flags
        FROM stage_df
        QUALIFY row_number() OVER (PARTITION BY source, series_id, observed_at, known_at ORDER BY value) = 1
        """
    )
    con.unregister("stage_df")
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE stage2 AS
        WITH s AS (  -- odrzuć powtórzenia wewnątrz partii
            SELECT * FROM (
                SELECT *, lag(value) OVER (PARTITION BY source, series_id, observed_at ORDER BY known_at) AS prev_in_batch
                FROM stage)
            WHERE prev_in_batch IS NULL OR NOT close_enough(prev_in_batch, value)
        )
        SELECT s.*, o.value AS prev_value, o.known_at AS prev_known_at
        FROM s ASOF LEFT JOIN observations o
          ON s.source = o.source AND s.series_id = o.series_id
         AND s.observed_at = o.observed_at AND s.known_at >= o.known_at
        """
    )
    con.execute(
        """
        INSERT INTO observations
        SELECT source, series_id, observed_at,
               CASE WHEN prev_known_at = known_at THEN greatest(?::TIMESTAMP, known_at + INTERVAL 1 SECOND) ELSE known_at END,
               value, vintage, ?::TIMESTAMP, license,
               CASE WHEN prev_known_at = known_at THEN concat_ws(',', flags, 'revised') ELSE flags END
        FROM stage2
        WHERE prev_value IS NULL OR NOT close_enough(prev_value, value)
        ON CONFLICT DO NOTHING
        """,
        [now, now],
    )
    con.execute("DROP TABLE stage; DROP TABLE stage2")
    return con.execute("SELECT count(*) FROM observations").fetchone()[0] - before


def as_of(con, ts, series_ids: list[str] | None = None) -> pd.DataFrame:
    q = "SELECT * FROM as_of(?::TIMESTAMP)"
    params: list = [ts]
    if series_ids:
        q += " WHERE series_id IN (SELECT unnest(?))"
        params.append(series_ids)
    return con.execute(q + " ORDER BY source, series_id, observed_at", params).df()


def panel_asof(con, series_ids: list[str], times: list) -> pd.DataFrame:
    """Dla każdej chwili decyzji t i serii: ostatnia obserwacja (w ostatniej wersji) znana w t.
    ASOF JOIN po known_at na latest_stream."""
    grid = pd.DataFrame([(s, pd.Timestamp(t)) for s in series_ids for t in times], columns=["series_id", "t"])
    con.register("grid_df", grid)
    out = con.execute(
        """
        SELECT g.series_id, g.t, l.observed_at, l.known_at, l.value, l.flags
        FROM grid_df g ASOF LEFT JOIN latest_stream l
          ON g.series_id = l.series_id AND g.t >= l.known_at
        ORDER BY g.series_id, g.t
        """
    ).df()
    con.unregister("grid_df")
    return out


def insert_exact(con, df: pd.DataFrame) -> int:
    """Zapis BEZ porównania wartości z poprzednią wersją (tylko klucz: ON CONFLICT DO NOTHING).
    Dla dodatkowych wersji, które mają istnieć obok innych (np. known_at_approx obok snapshotu)."""
    if df.empty:
        return 0
    df = df.copy()
    for c in ("vintage", "flags"):
        if c not in df:
            df[c] = None
    df["ingested_at"] = utcnow()
    df = df[["source", "series_id", "observed_at", "known_at", "value", "vintage", "ingested_at", "license", "flags"]]
    before = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    con.register("exact_df", df)
    con.execute("""INSERT INTO observations
                   SELECT source, series_id, CAST(observed_at AS TIMESTAMP), CAST(known_at AS TIMESTAMP),
                          CAST(value AS DOUBLE), CAST(vintage AS DATE), CAST(ingested_at AS TIMESTAMP),
                          CAST(license AS VARCHAR), CAST(flags AS VARCHAR)
                   FROM exact_df ON CONFLICT DO NOTHING""")
    con.unregister("exact_df")
    return con.execute("SELECT count(*) FROM observations").fetchone()[0] - before


GDELT_PATH = Path(os.environ.get("GDELT_DB", ROOT / "data" / "gdelt.duckdb"))


def attach_gdelt(con, alias: str = "gdelt") -> bool:
    """ATTACH data/gdelt.duckdb tylko do odczytu (zdarzenia: gdelt.events, pliki: gdelt.files).
    Wołane jawnie, nie w connect(): w czasie backfillu plik ma pisarza i ATTACH się nie uda -> False, bez wyjątku.
    Zdarzenia: observed_at = SQLDATE, known_at = DATEADDED; w zapytaniach PIT filtruj known_at <= ts."""
    if not GDELT_PATH.exists():
        return False
    try:
        con.execute(f"ATTACH '{GDELT_PATH}' AS {alias} (READ_ONLY)")
        return True
    except duckdb.IOException:
        return False

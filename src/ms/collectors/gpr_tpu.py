"""GPR dzienny (Caldara–Iacoviello) i TPU dzienny z snapshotów data/raw/{gpr,tpu}/.

Ostatnie wartości są wstępne i rewidowane -> każdy snapshot to vintage:
known_at = czas pobrania snapshotu, vintage = data snapshotu; ingest zapisuje tylko zmiany.
Konsekwencja: historia sprzed pierwszego snapshotu (2026-10-06) jest w as_of() widoczna dopiero od tej daty.
Dlatego dodatkowo wersja przybliżona: known_at = observed_at + 7 dni, flaga known_at_approx, wartość z
najwcześniejszego snapshotu zawierającego obserwację (może być już zrewidowana). Wersje snapshotowe zostają.
Średnie kroczące (MA7/MA30) pomijamy — to pochodne.
"""

from __future__ import annotations

import logging

import pandas as pd
import pandera.pandas as pa

from ms import db
from ms.collectors import approx_versions, first_seen, write, write_exact
from ms.collectors._snapshots import done, mark, snapshot_files

NAME = "gpr_tpu"
LICENSE = "cc_by"
APPROX_LAG = pd.Timedelta(days=7)
log = logging.getLogger("collect")

GPR_COLS = {"GPRD": "GPR.GPRD", "GPRD_ACT": "GPR.GPRD_ACT", "GPRD_THREAT": "GPR.GPRD_THREAT", "N10D": "GPR.N10D"}
TPU_COLS = {"TPUD_index": "TPU.TPUD_index", "TPUD_ARTICLES": "TPU.TPUD_ARTICLES", "NUMBER_ARTICLES": "TPU.NUMBER_ARTICLES"}

GPR_SCHEMA = pa.DataFrameSchema(
    {"date": pa.Column(pa.DateTime), **{c: pa.Column(float, nullable=True) for c in GPR_COLS}},
    coerce=True, strict=False,
)
TPU_SCHEMA = pa.DataFrameSchema(
    {"DATE": pa.Column(pa.DateTime), **{c: pa.Column(float, nullable=True) for c in TPU_COLS}},
    coerce=True, strict=False,
)


def frame(raw: pd.DataFrame, date_col: str, cols: dict, source: str, known: pd.Timestamp) -> pd.DataFrame:
    raw = raw[raw[date_col] <= known]
    parts = [pd.DataFrame({"source": source, "series_id": sid, "observed_at": raw[date_col].values, "known_at": known,
                           "value": raw[c].values, "vintage": known.date(), "license": LICENSE}).dropna(subset=["value"])
             for c, sid in cols.items()]
    return pd.concat(parts, ignore_index=True)


def parse_gpr(path) -> pd.DataFrame:
    return GPR_SCHEMA.validate(pd.read_excel(path))


def parse_tpu(path) -> pd.DataFrame:
    return TPU_SCHEMA.validate(pd.read_excel(path, sheet_name="TPU_DAILY"))


def collect(con, full: bool = False) -> int:
    db.register_series(con, "gpr", [(s, "1d_all", f"GPR daily {c}") for c, s in GPR_COLS.items()], LICENSE)
    db.register_series(con, "tpu", [(s, "1d_all", f"TPU daily {c}") for c, s in TPU_COLS.items()], LICENSE)
    n = 0
    for source, parse, date_col, cols in (("gpr", parse_gpr, "date", GPR_COLS), ("tpu", parse_tpu, "DATE", TPU_COLS)):
        for known, path, _ in snapshot_files(source):
            if not full and done(con, path):
                continue
            df = frame(parse(path), date_col, cols, source, known)
            approx = approx_versions(first_seen(con, df), APPROX_LAG)  # przed zapisem snapshotu
            added = write(con, df)
            added += write_exact(con, approx)
            log.info("%s %s: +%d", source, path.parent.name, added)
            n += added
            mark(con, path)
    return n

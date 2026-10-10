"""Wersje przybliżone (known_at_approx): tylko z pierwszego snapshotu, bez wycieku rewizji."""

import pandas as pd

from ms import db
from ms.collectors import approx_versions, first_seen, write, write_exact

LAG = pd.Timedelta(days=7)


def snap(known, values):
    return pd.DataFrame({"source": "gpr", "series_id": "GPR.X", "observed_at": pd.to_datetime(list(values)),
                         "known_at": pd.Timestamp(known), "value": list(values.values()), "license": "cc_by"})


def run(con, s):
    a = approx_versions(first_seen(con, s), LAG)
    return write(con, s) + write_exact(con, a)


def test_approx_from_first_snapshot_only(mem):
    run(mem, snap("2026-10-06", {"2026-01-01": 1.0, "2026-10-04": 5.0}))
    run(mem, snap("2026-10-20", {"2026-01-01": 1.5, "2026-10-04": 6.0}))  # rewizje
    # stara obserwacja: przybliżenie 2026-01-08 z pierwszego snapshotu
    assert db.as_of(mem, "2026-01-09")["value"].item() == 1.0
    # świeża obserwacja (2026-10-04 + 7 d > pierwszy snapshot) -> brak przybliżenia, rewizja 6.0 NIE cofa się
    v = db.as_of(mem, "2026-10-12")
    assert v.loc[v.observed_at == "2026-10-04", "value"].item() == 5.0
    flags = mem.execute("SELECT flags FROM observations WHERE observed_at='2026-10-04'").fetchall()
    assert ("known_at_approx",) not in flags
    # snapshotowe wersje zostają obok przybliżonych
    assert mem.execute("SELECT count(*) FROM observations WHERE observed_at='2026-01-01'").fetchone()[0] == 3


def test_approx_idempotent(mem):
    s = snap("2026-10-06", {"2026-01-01": 1.0})
    assert run(mem, s) == 2
    assert run(mem, s) == 0

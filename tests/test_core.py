"""Rdzeń: ingest wersjonujący, as_of, panel_asof — na danych syntetycznych."""

import pandas as pd

from ms import db


def frame(rows, source="t", license="public_domain"):
    df = pd.DataFrame(rows, columns=["series_id", "observed_at", "known_at", "value"])
    df["source"], df["license"] = source, license
    for c in ("observed_at", "known_at"):
        df[c] = pd.to_datetime(df[c])
    return df


def count(con):
    return con.execute("SELECT count(*) FROM observations").fetchone()[0]


def test_ingest_idempotent(mem):
    df = frame([("A", "2024-01-01", "2024-01-02", 1.0), ("A", "2024-01-02", "2024-01-03", 2.0)])
    assert db.ingest(mem, df) == 2
    assert db.ingest(mem, df) == 0
    assert count(mem) == 2


def test_snapshot_versions_only_on_change(mem):
    # trzy snapshoty: drugi bez zmian, trzeci z rewizją jednego punktu
    s1 = frame([("A", "2024-01-01", "2024-02-01", 1.0), ("A", "2024-01-02", "2024-02-01", 2.0)])
    s2 = frame([("A", "2024-01-01", "2024-02-02", 1.0), ("A", "2024-01-02", "2024-02-02", 2.0)])
    s3 = frame([("A", "2024-01-01", "2024-02-03", 1.0), ("A", "2024-01-02", "2024-02-03", 2.5)])
    for s in (s1, s2, s3):
        db.ingest(mem, s)
    assert count(mem) == 3
    v = db.as_of(mem, "2024-02-02 12:00")
    assert v.loc[v.observed_at == "2024-01-02", "value"].item() == 2.0
    v = db.as_of(mem, "2024-02-03")
    assert v.loc[v.observed_at == "2024-01-02", "value"].item() == 2.5
    for s in (s1, s2, s3):  # ponowny import całości
        assert db.ingest(mem, s) == 0


def test_correction_at_same_known_at_gets_new_known_at(mem):
    db.ingest(mem, frame([("A", "2024-01-01", "2024-01-02", 1.0)]))
    assert db.ingest(mem, frame([("A", "2024-01-01", "2024-01-02", 1.1)])) == 1
    rows = mem.execute("SELECT known_at, value, flags FROM observations ORDER BY known_at").fetchall()
    assert rows[0][1] == 1.0 and rows[1][1] == 1.1 and "revised" in rows[1][2]
    assert rows[1][0] > rows[0][0]
    # stan wiedzy z 2024-01-02 nie widzi korekty
    assert db.as_of(mem, "2024-01-03")["value"].item() == 1.0


def test_as_of_excludes_future_known(mem):
    db.ingest(mem, frame([("A", "2024-01-01", "2024-01-05", 1.0)]))
    assert db.as_of(mem, "2024-01-04").empty
    assert len(db.as_of(mem, "2024-01-05")) == 1


def test_panel_asof_latest_observation_not_old_revision(mem):
    db.ingest(mem, frame([
        ("A", "2024-01-01", "2024-01-02", 1.0),
        ("A", "2024-02-01", "2024-02-02", 2.0),
        ("A", "2024-01-01", "2024-02-10", 1.5),  # rewizja starego punktu
    ]))
    p = db.panel_asof(mem, ["A"], ["2024-01-15", "2024-02-05", "2024-02-11"])
    assert list(p["value"]) == [1.0, 2.0, 2.0]
    assert pd.isna(db.panel_asof(mem, ["A"], ["2023-12-31"])["value"].item())


def test_license_required(mem):
    import duckdb, pytest
    with pytest.raises(duckdb.ConstraintException):
        db.ingest(mem, frame([("A", "2024-01-01", "2024-01-02", 1.0)], license="whatever"))


def test_float_noise_is_not_a_revision(mem):
    db.ingest(mem, frame([("A", "2024-01-01", "2024-01-02", 96.05000305175781)]))
    assert db.ingest(mem, frame([("A", "2024-01-01", "2024-01-03", 96.0500030517578)])) == 0
    assert db.ingest(mem, frame([("A", "2024-01-01", "2024-01-03", 96.06)])) == 1

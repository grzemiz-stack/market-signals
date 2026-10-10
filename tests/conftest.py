import os

import pytest

from ms import db

NO_DB = ("requires data/market.duckdb — data is not distributed (DATA_SOURCES.md); "
         "collect it with the collectors, or set MS_REQUIRE_DB=1 to make this a failure")


def _require_db() -> bool:
    """Brak bazy: domyślnie skip z powodem (kopia publiczna, świeży klon bez danych). MS_REQUIRE_DB=1 -> błąd, nie skip
    (brak sygnału ≠ dowód) — tak biegnie pełna bramka na maszynie z danymi."""
    return os.environ.get("MS_REQUIRE_DB") == "1"


def pytest_collection_modifyitems(config, items):
    """Testy oznaczone `data` (prawdziwa baza, kopie widoków, baza gry) bez danych -> skip z powodem."""
    if db.DB_PATH.exists() or _require_db():
        return
    skip = pytest.mark.skip(reason=NO_DB)
    for it in items:
        if "data" in it.keywords:
            it.add_marker(skip)


@pytest.fixture
def mem():
    con = db.connect(":memory:")
    yield con
    con.close()


@pytest.fixture(scope="session")
def real():
    """Prawdziwa baza. Brak: skip z powodem (NO_DB) albo błąd przy MS_REQUIRE_DB=1."""
    if not db.DB_PATH.exists():
        if not _require_db():
            pytest.skip(NO_DB)
        pytest.fail(f"brak {db.DB_PATH} — uruchom uv run src/collect.py")
    con = db.connect(db.DB_PATH, read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    yield con
    con.close()

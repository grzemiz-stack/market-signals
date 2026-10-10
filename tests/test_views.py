"""ms.views = jedyne źródło liczb w `paper.py status` (i w dashboardzie, etap 4C); ms.paper.order wspólne dla CLI."""

import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from ms import paper as pp, views
from ms.trading import GAME_ASSETS, PriceBook

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import paper as cli  # noqa: E402
from provenance import foreign_numbers  # noqa: E402

pytestmark = pytest.mark.data


@pytest.fixture
def pcon(tmp_path):
    shutil.copy(pp.PAPER_DB, tmp_path / "p.duckdb")
    c = pp.connect(tmp_path / "p.duckdb")
    yield c
    c.close()


@pytest.fixture(scope="module")
def book(real):
    return PriceBook(real)


@pytest.mark.parametrize("acc_id", [1, 2, 3])
def test_status_numbers_come_from_views(pcon, real, book, acc_id):
    acc = pp.account(pcon, acc_id)
    t = pp.now_utc()
    text = cli.status(pcon, real, book, acc, t=t)
    v = views.account_view(pcon, real, book, acc)
    cards = [views.asset_card(real, book, a, t) for a in GAME_ASSETS]
    bad = foreign_numbers(text, v, *cards, {"id": acc_id, "date": str(v["today"].date())})
    assert not bad, f"liczby spoza ms.views: {bad}"


def test_provenance_detects_foreign_number(pcon, real, book):
    acc = pp.account(pcon, 1)
    v = views.account_view(pcon, real, book, acc)
    assert foreign_numbers(f"Wartość konta: {v['value'] * 1.01:,.2f} zł".replace(",", " ").replace(".", ","), v)


def test_order_shared_and_validated(pcon, real, book):
    acc = pp.account(pcon, 1)
    with pytest.raises(ValueError, match="powód"):
        pp.order(pcon, real, book, acc, "buy", "XAG", "  ", amount_pln=100.0, D="2026-10-06")
    r = pp.order(pcon, real, book, acc, "buy", "XAG", "test", amount_pln=100.0, D="2026-10-06")
    row = pcon.execute("SELECT side, asset, amount_pln, reason, decision_date FROM paper_orders WHERE id=?", [r["id"]]).fetchone()
    assert row[:4] == ("buy", "XAG", 100.0, "test") and pd.Timestamp(row[4]) == pd.Timestamp("2026-10-06")
    assert r["exec_date"] == book.exec_date("XAG", "2026-10-06")
    with pytest.raises(PermissionError):
        pp.order(pcon, real, book, pp.account(pcon, 2), "buy", "XAG", "x", amount_pln=100.0)

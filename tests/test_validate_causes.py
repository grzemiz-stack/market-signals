"""4N walidacja (bez uruchamiania LLM): maskowanie, zbiory E1/E4, przykłady tylko 1900–1949, progi zamrożone."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import validate_causes as V  # noqa: E402
from ms import classify as C  # noqa: E402


def test_mask_consistent_and_removes_years():
    out = V.mask(["Saudi Arabia and Iran met at OPEC in March 1974; Saudi output fell.", "Iraqi troops entered Kuwait in 1990."])
    assert "Saudi" not in " ".join(out) and "1974" not in out[0] and "March" not in out[0] and "OPEC" not in out[0]
    assert out[0].count("[KRAJ_A]") == 2                                   # „Saudi Arabia” i „Saudi” = ten sam znacznik


def test_thresholds_frozen():
    assert V.THRESHOLDS == {"E1_kappa": 0.695, "E2_acc": 0.75, "E2_kappa": 0.60, "E3_hits": 14, "E4_agree": 0.60}


@pytest.mark.data
def test_e1_units_and_fewshots_do_not_overlap(real):
    u = V.e1_units(real)
    assert len(u) == 492 and pd.to_datetime(u["date"]).dt.year.between(1950, 2022).all()
    ex = C.bbds_fewshots(real)
    passages = set(u["passage"].str.strip())
    assert len(ex) == 12 and not any(t[4:] in passages for _, t in ex)   # przykłady tylko z 1900–1949
    days = V.e4_days(real)
    assert len(days) == 42


def test_e2_wgc_index_frozen_without_quotes():
    """Kopia publiczna: wzorzec E2 bez cytatów WGC (miesiąc, URL, kod, położenie + SHA-256); te same liczby co wzorzec."""
    import e2_wgc_restore as W

    g = pd.read_csv(W.INDEX, comment="#")
    assert "cytat" not in g.columns
    inc = g[g["wlaczony"] == "tak"]
    assert len(g) == 54 and len(inc) == 30
    assert "corporate_foreign" not in set(inc["kod"])                       # apetyt na ryzyko poza taksonomią (2026-10-07)
    assert int(inc["konwencja"].notna().sum()) == 19
    assert not {"2021-05", "2021-07", "2023-04", "2024-04", "2025-09", "2025-10", "2026-02"} & set(inc["miesiac"])   # kierunek A
    assert set(inc["kod"]) <= set(V.taxonomy_codes())
    assert (g.loc[g["wlaczony"] == "nie", "kod"].isna()).all()            # wyłączone bez kodu, z powodem
    assert g.loc[g["wlaczony"] == "nie", "uwaga"].notna().all()
    assert inc["sha256"].str.fullmatch(r"[0-9a-f]{64}").all() and (inc["length"] > 0).all()
    chk = pd.read_csv(V.db.ROOT / "ref" / "e2_wgc_check20_agent.csv", comment="#")   # runda 3 (bramka E2)
    assert "cytat" not in chk.columns and len(chk) == 20 and set(chk["miesiac"]) <= set(inc["miesiac"])
    assert int((chk["TAK/NIE"].str.upper() == "NIE").sum()) == 0


def test_e2_wgc_restore_roundtrip_and_hash_guard(tmp_path, monkeypatch):
    """Odtworzenie zdania z zapisanej strony (spacja tylko na granicy bloków) i odmowa przy innej wersji strony."""
    import e2_wgc_restore as W

    page = "<html><script>x()</script><p>Intro.</p><p>Gold rose on <a href='#'>weaker</a> data (<b>Chart 1</b>).1</p></html>"
    (tmp_path / "gold-market-commentary-may-2099.html").write_text(page)
    monkeypatch.setattr(W, "RAW", tmp_path)
    text = W.page_text(page)
    q = "Gold rose on weaker data (Chart 1).1"
    assert text == "Intro. " + q
    row = {"miesiac": "2099-05", "url": "https://example.test/gold-market-commentary-may-2099", "kod": "macro",
           "wlaczony": "tak", "uwaga": None, "konwencja": None, "start": text.index(q), "length": len(q), "sha256": W.sha(q)}
    assert W.restore(pd.DataFrame([row]))["cytat"].iloc[0] == q
    (tmp_path / "gold-market-commentary-may-2099.html").write_text(page.replace("rose", "fell"))
    with pytest.raises(SystemExit, match="hash"):
        W.restore(pd.DataFrame([row]))


def test_conventions_in_production_definitions():
    d = C.code_descriptions(["fx_capital", "monetary", "macro"])
    assert "US dollar" in d["fx_capital"] and "central-bank gold purchases" in d["monetary"] and "bond yields" in d["monetary"]
    assert "inflation" in d["macro"]
    t = C.taxonomy()
    assert t["prompt"].notna().all()                                        # każdy kod ma definicję produkcyjną


def test_e4hist_pool_rank_and_no_usa_filter(tmp_path):
    import duckdb
    import e4hist_gdelt as G
    g = duckdb.connect(str(tmp_path / "g.duckdb"))
    g.execute(G.SCHEMA)
    ev = [(1, "2026-01-28 18:15:00", "USA", "USA", "0841", "08", 500, "https://n.test/fed-holds-rates-steady-statement", "f"),
          (2, "2026-01-28 10:00:00", "IRN", "USA", "1123", "11", 50, "https://n.test/iran-criticizes-washington-today", "f"),
          (3, "2026-01-26 10:00:00", "RUS", "UKR", "190", "19", 999, "https://n.test/outside-window-old-event", "f")]
    g.executemany("INSERT INTO ev VALUES (?,?,?,?,?,?,?,?,?)", ev)
    g.executemany("INSERT INTO men VALUES (?,?,?,?,?)", [(3, "2026-01-28 12:00:00", 1, "https://m.test/war-coverage-mention-later", "f"),
                                                       (1, "2026-01-28 12:00:00", 2, "https://m.test/not-web-mention-type", "f")])
    txt, usa = V.e4hist_text(g, "2026-01-28")
    assert txt[0].startswith("outside window old event") is False
    assert txt[0] == "war coverage mention later | CAMEO 190 RUS→UKR"            # wzmianka w oknie o starszym zdarzeniu (999)
    assert txt[1] == "fed holds rates steady statement | CAMEO 0841 USA→USA"     # USA–USA NIE jest wycinane
    assert len(txt) == 3 and not any("not web" in t for t in txt) and usa == 1 / 3

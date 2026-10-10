"""Etap 4N: źródła przyczyn dużych ruchów (Priorytet 1 z docs/ZRODLA-PRZYCZYN.md). Tylko do wyjaśniania i badań
zdarzeń — NIGDY jako cecha prognozy (docs/ETAP4N-PLAN.md, pkt 0).

Każdy plik -> data/raw/causes/<dzień>/ + manifest (Store z snapshot_raw), potem parser -> cause_events / bbds_codings.
Parsery przyjmują bajty (testowalne na zapisanych próbkach). Źródła sprawdzone 2026-10-06:
- P1 BBDS (Google Sheet, eksport xlsx): zakładka wsj_codings — skoki akcji USA 1900–2022, kodowania ludzi.
- P2 AI-GPR (CSV dzienny, w tym Oil GPR): tylko surowy plik; skoki liczy ms.causes z najnowszego pliku (latest_vintage).
- P3 niespodzianki FOMC: SF Fed Bauer–Swanson (MPS, do 2023-12) i Jarociński–Karadi (MP/CBI, do 2024-01).
- P4 chronologia EIA 1970–2003+: ORYGINAŁ eia.doe.gov z Wayback (zrzut 2005-11-12), nie kopia z laohamutuk.
- P5 Wikipedia „Chronology of world oil market events” (wikitext, wersja przypięta przez revid).
- P7 DefiLlama hacks API.
- P8 ref/crypto_events.csv (ręcznie, w repo; kolumna verified mówi, co sprawdzono u źródła).
P6 (IMF) — skrzynka data/inbox/imf/ (403 na stronie, blokady nie obchodzimy).
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import logging
import re
from datetime import date

import pandas as pd

from ms.common import Http
from ms.db import ROOT

log = logging.getLogger("causes")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WIKI_UA = "market-signals-research/0.1 (private research script)"
REF = ROOT / "ref"

UNCONFIRMED = " (niepotwierdzona)"  # decyzja D5: licencja bez podanych warunków, użytek prywatny
URLS = {
    "bbds.xlsx": "https://docs.google.com/spreadsheets/d/1fkIIishR6LsAtZSv-_cpvyJtuSytemiVYjGUiRgYvNI/export?format=xlsx",
    "ai_gpr_data_daily.csv": "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv",
    "sffed_mps.xlsx": "https://www.frbsf.org/wp-content/uploads/monetary-policy-surprises-data.xlsx",
    "jk_shocks_t.csv": "https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed_202401/main/shocks_fed_jk_t.csv",
    "eia_chron.html": "https://web.archive.org/web/20051112061236id_/http://www.eia.doe.gov/emeu/cabs/chron.html",
    "wiki_oil_chron.wikitext": "https://en.wikipedia.org/w/index.php?title=Chronology_of_world_oil_market_events&action=raw&oldid={revid}",
    "defillama_hacks.json": "https://api.llama.fi/hacks",
}
LICENSE = {
    "bbds": "academic" + UNCONFIRMED,
    "aigpr": "academic" + UNCONFIRMED,
    "sffed": "public_domain",
    "jk": "academic" + UNCONFIRMED,
    "eia_chron": "public_domain",
    "wiki_chron": "cc_by_sa",
    "defillama": "defillama_terms" + UNCONFIRMED,
    "manual": "public_facts",
}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def wiki_revid(http: Http) -> int:
    r = http.get("https://en.wikipedia.org/w/api.php", params={
        "action": "query", "prop": "revisions", "titles": "Chronology of world oil market events",
        "rvprop": "ids", "format": "json"}, headers={"User-Agent": WIKI_UA})
    page = next(iter(r.json()["query"]["pages"].values()))
    return int(page["revisions"][0]["revid"])


# --------------------------------------------------------------------------- parsery (bajty -> ramki)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _md(tok: str) -> tuple[int | None, int | None]:
    """'Mar 11-12' -> (3, 11); 'Nov' -> (11, None); 'June 3' -> (6, 3)."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s*(\d{1,2})?", tok.strip())
    if not m or m.group(1).lower() not in MONTHS:
        return None, None
    return MONTHS[m.group(1).lower()], int(m.group(2)) if m.group(2) else None


def parse_eia_chron(content: bytes) -> pd.DataFrame:
    """Sekcje <H2><A name=aRRRR> + wpisy <DT><B>Mies D</B> <DD>tekst. Dokładność: dzień albo miesiąc.
    <DT> bez daty = ciąg dalszy poprzedniego wpisu (ta sama data). Etykiety sezonowe („Spring”) pomijane."""
    t = content.decode("latin-1")
    rows = []
    for ym in re.finditer(r"<A name=a(\d{4})>.*?(?=<A name=a\d{4}>|$)", t, flags=re.S | re.I):
        year, prev = int(ym.group(1)), (None, None)
        sec = re.split(r"</DL>", ym.group(0), flags=re.I)[0]  # po ostatnim roku jest sekcja 2004 bez kotwicy
        for k, chunk in enumerate(re.split(r"<DT>", sec, flags=re.I)[1:]):
            b = re.match(r"\s*<B>(.*?)</B>", chunk, flags=re.S | re.I)
            dd = re.search(r"<DD>(.*)", chunk, flags=re.S | re.I)
            text = _clean(re.sub(r"<I\s*>\(.*?\)</I>", "", dd.group(1), flags=re.S | re.I)) if dd else ""
            label = _clean(b.group(1)) if b else ""
            mon, day = _md(label) if label else prev
            if not label and prev[0] is None:
                continue
            if mon is None or not text:
                continue
            prev = (mon, day)
            rows.append({"event_id": f"eia-{year}-{mon:02d}-{k:03d}", "event_date": date(year, mon, day or 1),
                         "date_precision": "day" if day else "month", "text": text,
                         "label": label or "(ciąg dalszy)"})
    return pd.DataFrame(rows)


def parse_wiki_chron(content: bytes) -> pd.DataFrame:
    """Wikitext: ===RRRR=== + *'''Mies D''': tekst (przypisy <ref> i szablony usunięte)."""
    rows, year = [], None
    for line in content.decode("utf-8").splitlines():
        y = re.match(r"^===\s*(\d{4})\s*===", line)
        if y:
            year = int(y.group(1))
            continue
        m = re.match(r"^\*\s*'''(.*?)'''\s*:?\s*(.*)", line)
        if not (m and year):
            continue
        mon, day = _md(m.group(1))
        if mon is None:
            continue
        text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|\{\{.*?\}\}", "", m.group(2))
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text).replace("'''", "").replace("''", "")
        text = _clean(text)
        if text:
            rows.append({"event_id": f"wiki-{year}-{mon:02d}-{day or 0:02d}-{len(rows):03d}",
                         "event_date": date(year, mon, day or 1), "date_precision": "day" if day else "month",
                         "text": text, "label": m.group(1)})
    return pd.DataFrame(rows)


def parse_defillama(content: bytes) -> pd.DataFrame:
    rows = []
    for e in json.loads(content):
        d = pd.Timestamp(int(e["date"]), unit="s").date()
        key = f"{e.get('defillamaId') or ''}-{e['name']}-{d}"
        rows.append({"event_id": "hack-" + hashlib.sha1(key.encode()).hexdigest()[:12], "event_date": d,
                     "date_precision": "day", "category": "hack", "value": float(e.get("amount") or 0) or None,
                     "text": f"{e['name']}: {e.get('classification') or ''} / {e.get('technique') or ''}; "
                             f"łańcuchy {', '.join(e.get('chain') or [])}; bridge={e.get('bridgeHack')}",
                     "url": e.get("source") or None})
    return pd.DataFrame(rows).drop_duplicates("event_id")


def parse_sffed(content: bytes) -> pd.DataFrame:
    d = pd.read_excel(io.BytesIO(content), sheet_name="FOMC (update 2023)")
    if not {"Date", "MPS", "Unscheduled"} <= set(d.columns):
        raise ValueError("format SF Fed: brak kolumn Date/MPS/Unscheduled")
    d = d.dropna(subset=["Date"]).assign(day=lambda x: pd.to_datetime(x["Date"]).dt.date,
                                         MPS=lambda x: pd.to_numeric(x["MPS"], errors="coerce"))
    # kilka komunikatów jednego dnia (1988–1991) -> suma niespodzianek dnia (etykiety są dzienne)
    g = d.groupby("day").agg(value=("MPS", lambda s: s.sum(min_count=1)), n=("MPS", "size"), uns=("Unscheduled", "max")).reset_index()
    return pd.DataFrame({"event_id": "sffed-" + pd.to_datetime(g["day"]).dt.strftime("%Y-%m-%d"), "event_date": g["day"],
                         "date_precision": "day", "category": "fomc_mps", "value": g["value"],
                         "text": "niespodzianka FOMC Bauer–Swanson (MPS)" + g["uns"].map({1: ", nadzwyczajne", 0: ""}).fillna("")
                                 + g["n"].map(lambda k: f", suma {k} komunikatów dnia" if k > 1 else "")})


def parse_jk(content: bytes) -> pd.DataFrame:
    d = pd.read_csv(io.BytesIO(content))
    if not {"start", "MP_median", "CBI_median"} <= set(d.columns):
        raise ValueError("format JK: brak kolumn start/MP_median/CBI_median")
    d["day"] = pd.to_datetime(d["start"]).dt.date
    g = d.groupby("day").agg(MP=("MP_median", "sum"), CBI=("CBI_median", "sum"), n=("start", "size")).reset_index()
    t = pd.to_datetime(g["day"])
    out = []
    for col, cat, txt in (("MP", "fomc_mp", "szok stopy (JK)"), ("CBI", "fomc_cbi", "szok informacyjny (JK)")):
        out.append(pd.DataFrame({"event_id": f"jk-{cat}-" + t.dt.strftime("%Y-%m-%d"), "event_date": g["day"],
                                 "date_precision": "day", "category": cat, "value": g[col].astype(float),
                                 "text": txt + g["n"].map(lambda k: f", suma {k} komunikatów dnia" if k > 1 else "")}))
    return pd.concat(out, ignore_index=True)


BBDS_COLS = {"date": "date", "Return": "ret", "Coder": "coder", "Primary Category": "primary_cat",
             "Secondary Category": "secondary_cat", "(#) Ease of Coding": "ease", "(#) Journalist Confidence": "journalist_conf",
             "Article Title": "title", "Key Passage": "passage", "Newspaper": "newspaper"}


def parse_bbds(content: bytes) -> pd.DataFrame:
    d = pd.read_excel(io.BytesIO(content), sheet_name="wsj_codings")
    missing = set(BBDS_COLS) - set(d.columns)
    if missing:
        raise ValueError(f"format BBDS: brak kolumn {missing}")
    d = d[list(BBDS_COLS)].rename(columns=BBDS_COLS)
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d["row_no"] = range(len(d))
    for c in ("ease", "journalist_conf", "ret"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("coder", "primary_cat", "secondary_cat", "title", "passage", "newspaper"):
        d[c] = d[c].astype("string").str.strip().replace("", pd.NA)
    return d


def load_manual() -> pd.DataFrame:
    d = pd.read_csv(REF / "crypto_events.csv", comment="#", dtype=str)
    d["event_date"] = pd.to_datetime(d["event_date"]).dt.date
    return d.assign(value=None)


# --------------------------------------------------------------------------- zapis


def _upsert_events(con, source: str, df: pd.DataFrame, sha: str) -> int:
    if df.empty:
        return 0
    df = df.copy()
    for c in ("category", "value", "text", "url", "assets", "verified"):
        if c not in df:
            df[c] = None
    df["source"], df["license"], df["raw_sha"] = source, LICENSE[source], sha
    cols = ["source", "event_id", "event_date", "date_precision", "category", "assets", "value", "text", "url", "verified",
            "license", "raw_sha"]
    con.execute("DELETE FROM cause_events WHERE source = ?", [source])  # pełne przeładowanie źródła z jednego pliku
    con.register("_ce", df[cols])
    con.execute(f"INSERT INTO cause_events SELECT {', '.join(cols)} FROM _ce")
    con.unregister("_ce")
    return len(df)


def fetch_all(con, store, http: Http | None = None) -> dict:
    """Pobiera P1–P5, P7 do data/raw/causes/ i ładuje tabele. Zwraca liczby wierszy na źródło."""
    http = http or Http(min_interval=1.0)
    urls = dict(URLS)
    revid = wiki_revid(http)
    urls["wiki_oil_chron.wikitext"] = urls["wiki_oil_chron.wikitext"].format(revid=revid)
    raw = {}
    for name, url in urls.items():
        r = http.get(url, headers={"User-Agent": WIKI_UA if "wikipedia" in url else UA})
        if r.status_code != 200:
            store.fail("causes", name, url, r.status_code, "HTTP " + str(r.status_code))
            raise RuntimeError(f"{name}: HTTP {r.status_code}")
        extra = {"wiki_revid": revid} if name.startswith("wiki") else {}
        e = store.save("causes", name, r.content, url, r.status_code, **extra)
        raw[name] = (r.content, e["sha256"])
    n = {}
    n["eia_chron"] = _upsert_events(con, "eia_chron", parse_eia_chron(raw["eia_chron.html"][0]), raw["eia_chron.html"][1])
    n["wiki_chron"] = _upsert_events(con, "wiki_chron", parse_wiki_chron(raw["wiki_oil_chron.wikitext"][0]).assign(
        url=f"https://en.wikipedia.org/w/index.php?oldid={revid}"), raw["wiki_oil_chron.wikitext"][1])
    n["defillama"] = _upsert_events(con, "defillama", parse_defillama(raw["defillama_hacks.json"][0]), raw["defillama_hacks.json"][1])
    n["sffed"] = _upsert_events(con, "sffed", parse_sffed(raw["sffed_mps.xlsx"][0]), raw["sffed_mps.xlsx"][1])
    n["jk"] = _upsert_events(con, "jk", parse_jk(raw["jk_shocks_t.csv"][0]), raw["jk_shocks_t.csv"][1])
    man = load_manual()
    n["manual"] = _upsert_events(con, "manual", man, hashlib.sha256((REF / "crypto_events.csv").read_bytes()).hexdigest())
    b = parse_bbds(raw["bbds.xlsx"][0]).assign(license=LICENSE["bbds"])
    con.execute("DELETE FROM bbds_codings")
    con.register("_b", b)
    con.execute("INSERT INTO bbds_codings SELECT date, row_no, coder, ret, primary_cat, secondary_cat, ease, journalist_conf, "
                "title, passage, newspaper, license FROM _b")
    con.unregister("_b")
    n["bbds"] = len(b)
    # AI-GPR: tylko kontrola formatu; skoki liczy ms.causes z najnowszego pliku
    g = pd.read_csv(io.BytesIO(raw["ai_gpr_data_daily.csv"][0]), nrows=5)
    need = {"Date", "GPR_AI", "ACTS_GPR_AI", "GPR_OIL", "GPR_OIL_ACTS"}
    if not need <= set(g.columns):
        raise ValueError(f"format AI-GPR: brak kolumn {need - set(g.columns)}")
    n["aigpr"] = raw["ai_gpr_data_daily.csv"][0].count(b"\n") - 1
    for k, v in n.items():
        log.info("źródło %s: %d wierszy", k, v)
    return n

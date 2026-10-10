"""FRED/ALFRED: stopy, inflacja, dolar, płynność Fed, warunki finansowe, zmienność.

known_at = data publikacji, nie data obserwacji:
1. ALFRED (wszystkie serie): każdy vintage = wiersz z known_at = realtime_start + godzina publikacji ET.
   Pierwszy vintage obserwacji = faktyczna data jej publikacji; kolejne = rewizje (CPI, M2, NFCI, …).
   Serie dzienne mają > 2000 vintage -> zapytania w oknach realtime (≤ 1900 dat vintage);
   powtórzenia z granic okien odrzuca wersjonujący ingest.
2. Obserwacje sprzed początku archiwum ALFRED (ich pierwszy realtime_start = start archiwum,
   nie publikacja): known_at = pierwsza data wydania (tabela releases, FRED release/dates)
   ŚCIŚLE po końcu okresu; brak dat wydań -> koniec okresu + mediana opóźnienia z okresu
   pokrytego ALFRED. Flaga known_at_rule. Wartość = najstarsza znana (możliwa rewizja).
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from ms import db
from ms.collectors import write
from ms.common import ET, Http, env, local_series_to_utc

NAME = "fred"
SOURCE = "fred"
log = logging.getLogger("collect")
API = "https://api.stlouisfed.org/fred"

# series_id: (godzina publikacji ET, licencja)
SERIES = {
    "DFII10": ("16:15", "public_domain"), "DGS2": ("16:15", "public_domain"), "DGS10": ("16:15", "public_domain"),
    "FEDFUNDS": ("16:15", "public_domain"), "EFFR": ("09:00", "public_domain"),
    "T10YIE": ("16:15", "public_domain"), "T5YIFR": ("16:15", "public_domain"),
    "THREEFYTP10": ("17:00", "public_domain"), "DTWEXBGS": ("16:15", "public_domain"),
    "DEXUSEU": ("16:15", "public_domain"), "DEXJPUS": ("16:15", "public_domain"),
    "DEXCHUS": ("16:15", "public_domain"), "DEXUSAL": ("16:15", "public_domain"),
    "CPIAUCSL": ("08:30", "public_domain"), "M2SL": ("13:00", "public_domain"),
    "WALCL": ("16:30", "public_domain"), "WTREGEN": ("16:30", "public_domain"),
    "RRPONTSYD": ("13:15", "public_domain"), "USEPUINDXD": ("17:00", "cc_by"),
    "NFCI": ("08:30", "public_domain"), "STLFSI4": ("10:00", "public_domain"),
    "GVZCLS": ("17:00", "tos_restricted"), "OVXCLS": ("17:00", "tos_restricted"), "VIXCLS": ("17:00", "tos_restricted"),
    "GDPNOW": ("17:00", "public_domain"),
    # etap 4H (zgoda 2026-10-06): Nasdaq (bez SP500 — licencja, 10 lat), aktywność globalna, miedź, produkcja przemysłowa
    "NASDAQCOM": ("17:00", "tos_restricted"), "IGREA": ("17:00", "cc_by"),
    "PCOPPUSDM": ("17:00", "cc_by"), "INDPRO": ("09:15", "public_domain"),
}
FREQ = {"D": "1d_bday", "W": "1w", "M": "1m", "Q": "1q"}
FREQ_OVERRIDE = {"USEPUINDXD": "1d_all"}  # indeks z newsów: także weekendy
MAX_VINTAGES = 1900
MAX_LAG_DAYS = {"D": 7, "W": 14, "M": 45, "Q": 120}
# Bezpośrednie obserwacje rynku: wartość jest publiczna w dniu notowania (decyzja 2026-10-06) -> pierwsza wersja
# obserwacji ma known_at = dzień notowania o tej godzinie ET, flaga known_at_market_close. Rewizje: daty ALFRED.
MARKET_CLOSE = {"DEXUSEU": "12:00", "DEXJPUS": "12:00", "DEXCHUS": "12:00", "DEXUSAL": "12:00",  # kurs z 12:00 ET
                "VIXCLS": "16:15", "GVZCLS": "16:15", "OVXCLS": "16:15",                        # zamknięcie CBOE
                "NASDAQCOM": "16:00"}                                                            # zamknięcie Nasdaq
# Rentowności Treasury to wartości WYLICZANE (krzywa z kwotowań ~15:30 ET); publikacja przed 22:00 UTC w dniu
# notowania niepotwierdzona (2026-10-06) -> zostają przy dacie publikacji, z flagą. T10YIE/T5YIFR liczone z nich.
PUBLICATION_UNVERIFIED = ("DGS2", "DGS10", "DFII10", "T10YIE", "T5YIFR")  # wiarygodne opóźnienie publikacji od końca okresu


class Fred:
    def __init__(self):
        self.key = env("FRED_API_KEY")
        self.http = Http(min_interval=0.6)  # limit FRED: 120 zapytań/min

    def get(self, path: str, **params) -> dict:
        params.update(api_key=self.key, file_type="json")
        j = self.http.get(f"{API}/{path}", params=params).json()
        if "error_code" in j:
            raise RuntimeError(f"FRED {path} {params.get('series_id', '')}: {j.get('error_message')}")
        return j

    def paged(self, path: str, key: str, **params) -> list[dict]:
        out, offset = [], 0
        while True:
            j = self.get(path, limit=params.pop("limit", 100000), offset=offset, **params)
            out += j[key]
            offset += len(j[key])
            if not j[key] or offset >= int(j.get("count", 0)):
                return out


def vintage_windows(vdates: list[str]) -> list[tuple[str, str]]:
    """Okna realtime po ≤ MAX_VINTAGES dat vintage; ostatnie otwarte do 9999-12-31."""
    out = []
    for i in range(0, len(vdates), MAX_VINTAGES):
        chunk = vdates[i : i + MAX_VINTAGES]
        end = vdates[i + MAX_VINTAGES] if i + MAX_VINTAGES < len(vdates) else "9999-12-31"
        end = (pd.Timestamp(end) - pd.Timedelta(days=1)).date().isoformat() if end != "9999-12-31" else end
        out.append((chunk[0], end))
    return out


def period_end(dates: pd.Series, freq: str) -> pd.Series:
    if freq == "M":
        return dates + pd.offsets.MonthEnd(0)
    if freq == "Q":
        return dates + pd.offsets.QuarterEnd(0)
    return dates  # D, W: data FRED = dzień/koniec tygodnia


def first_release_after(ends: pd.Series, release_dates: pd.Series) -> pd.Series:
    rd = pd.Series(sorted(pd.to_datetime(release_dates).unique()))
    idx = rd.searchsorted(ends + pd.Timedelta(days=1), side="left")  # ściśle po końcu okresu
    return pd.Series([rd.iloc[i] if i < len(rd) else pd.NaT for i in idx], index=ends.index)


def fetch_vintages(fr: Fred, sid: str, since: str | None = None) -> pd.DataFrame:
    """since: tylko vintage od tej daty (tryb przyrostowy; realtime_start obcięte do since)."""
    vd = fr.paged("series/vintagedates", "vintage_dates", series_id=sid, limit=10000)
    if since:
        vd = [d for d in vd if d >= since] or vd[-1:]
    rows = []
    for rs, re_ in vintage_windows(vd):
        obs = fr.paged("series/observations", "observations", series_id=sid, realtime_start=rs, realtime_end=re_)
        rows += obs
    df = pd.DataFrame(rows)
    df = df[df["value"] != "."]
    df["value"] = df["value"].astype(float)
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    return df[["date", "realtime_start", "value"]].drop_duplicates()


def build(sid: str, vint: pd.DataFrame, freq: str, hhmm: str, license: str, release_dates: pd.Series,
          incremental: bool = False, since: str | None = None) -> pd.DataFrame:
    vint = vint.sort_values(["date", "realtime_start"])
    archive_start = vint["realtime_start"].min()
    ends = period_end(vint["date"], freq)
    # pierwsza publikacja = start archiwum ALFRED -> artefakt (obserwacja starsza niż archiwum)
    first_rt = vint.groupby("date")["realtime_start"].transform("min")
    lag = (vint["realtime_start"] - ends).dt.days
    max_lag = pd.Timedelta(days=MAX_LAG_DAYS[freq])
    covered = (first_rt > archive_start) | (lag <= max_lag.days)
    med_lag = int(math.ceil(lag[covered & (vint["realtime_start"] == first_rt)].median())) if covered.any() else 1

    # ALFRED potrafi podać realtime_start < data obserwacji (np. VIX w święta: obs 2026-05-25, vintage 05-22)
    # -> known_at nie wcześniej niż dzień obserwacji, flaga known_at_clamped.
    clamped = vint["realtime_start"] < vint["date"]
    out = pd.DataFrame({"observed_at": vint["date"], "value": vint["value"], "vintage": vint["realtime_start"].dt.date,
                        "known_at": local_series_to_utc(vint["realtime_start"].where(~clamped, vint["date"]), hhmm, ET),
                        "flags": clamped.map({True: "known_at_clamped", False: None})})
    # obserwacje sprzed archiwum: dodatkowy wiersz z known_at z dat wydań (reguła)
    pre = vint[~covered & (vint["realtime_start"] == first_rt)] if not incremental else vint.iloc[0:0]
    if len(pre):
        pe = period_end(pre["date"], freq)
        rel = first_release_after(pe, release_dates) if len(release_dates) else pd.Series(pd.NaT, index=pe.index)
        # data wydania tylko, gdy wiarygodna (tabela wydań często zaczyna się lata po obserwacji)
        rel = rel.where(rel - pe <= max_lag).fillna(pe + pd.Timedelta(days=med_lag))
        rel = rel.where(rel < pre["realtime_start"], pre["realtime_start"])
        out = pd.concat([out, pd.DataFrame({"observed_at": pre["date"], "value": pre["value"], "vintage": None,
                                            "known_at": local_series_to_utc(rel, hhmm, ET), "flags": "known_at_rule"})])
    if sid in MARKET_CLOSE:
        # pierwsza wersja obserwacji -> dzień notowania; w trybie przyrostowym tylko dla NOWYCH obserwacji
        # (rewizja starej obserwacji nie może dostać wczesnej daty — to byłby przeciek)
        first = out["known_at"] == out.groupby("observed_at")["known_at"].transform("min")
        if incremental and since:
            first &= out["observed_at"] >= pd.Timestamp(since)
        out.loc[first, "known_at"] = local_series_to_utc(out.loc[first, "observed_at"], MARKET_CLOSE[sid], ET).values
        out.loc[first, "flags"] = "known_at_market_close"
        out = out.drop_duplicates(subset=["observed_at", "known_at"], keep="first")
    elif sid in PUBLICATION_UNVERIFIED:
        out["flags"] = out["flags"].fillna("").map(lambda f: ",".join(x for x in (f, "known_at_publication_unverified_close") if x))
    out["source"], out["series_id"], out["license"] = SOURCE, f"FRED.{sid}", license
    return out.sort_values(["observed_at", "known_at"])


def collect(con, full: bool = False) -> int:
    fr = Fred()
    n = 0
    for sid, (hhmm, license) in SERIES.items():
        info = fr.get("series", series_id=sid)["seriess"][0]
        freq = info["frequency_short"]
        db.register_series(con, SOURCE, [(f"FRED.{sid}", FREQ_OVERRIDE.get(sid, FREQ[freq]), info["title"])], license)
        rel = fr.get("series/release", series_id=sid)["releases"][0]
        rdates = fr.paged("release/dates", "release_dates", release_id=rel["id"], limit=10000,
                          include_release_dates_with_no_data="false", sort_order="asc")
        rd = pd.DataFrame(rdates)
        if len(rd):
            con.executemany("INSERT OR IGNORE INTO releases VALUES ('fred', ?, ?, ?)",
                            [(str(rel["id"]), rel["name"], d) for d in rd["date"]])
        since = None
        if not full:
            last = con.execute("SELECT max(vintage) FROM observations WHERE series_id=?", [f"FRED.{sid}"]).fetchone()[0]
            since = (pd.Timestamp(last) - pd.Timedelta(days=7)).date().isoformat() if last is not None else None
        vint = fetch_vintages(fr, sid, since)
        df = build(sid, vint, freq, hhmm, license, rd["date"] if len(rd) else pd.Series(dtype=str),
                   incremental=since is not None, since=since)
        added = write(con, df)
        n += added
        log.info("FRED %s (%s): %d obs, %d wersji, release %s od %s, +%d", sid, freq, vint["date"].nunique(), len(vint),
                 rel["id"], rd["date"].min() if len(rd) else "-", added)
    return n

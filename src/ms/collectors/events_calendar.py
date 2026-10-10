"""Kalendarz zdarzeń do badań zdarzeń (tabela events_calendar). Wszystkie źródła darmowe (zgoda 2026-10-06).

- FOMC: daty komunikatów (monetaryRRRRMMDDa.htm) z federalreserve.gov, od 2000 (posiedzenia planowe i nadzwyczajne).
  known_at = dzień 14:15 ET (komunikat 14:00 ET, wcześniej 14:15).
- OPEC: 169 komunikatów 1983–2025 z danych Känziga (oilSupplyNewsShocks, arkusz Daily); value = niespodzianka
  (1. składowa główna zmian futures w dniu komunikatu). known_at = początek dnia (godzina komunikatu nieznana;
  dzień 0 = zamknięcie tego dnia, jak u Känziga). Tylko do badań zdarzeń, nie jako cecha PIT.
- Huragany: HURDAT2 (NOAA, public domain) — pierwszy zapis o statusie HU wewnątrz Zatoki Meksykańskiej
  (18–31°N, 98–80°W) dla każdego sztormu; known_at = czas zapisu (UTC); value = wiatr maks. (kt).
"""

from __future__ import annotations

import io
import logging
import re

import pandas as pd

from ms.common import ET, Http, local_to_utc

NAME = "events_calendar"
log = logging.getLogger("collect")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
FED = "https://www.federalreserve.gov/monetarypolicy/"
KANZIG = "https://raw.githubusercontent.com/dkaenzig/oilsupplynews/master/oilSupplyNewsShocks_2025M12.xlsx"
NHC = "https://www.nhc.noaa.gov/data/"
GOM = (18.0, 31.0, -98.0, -80.0)


def fomc_dates(http: Http) -> list[pd.Timestamp]:
    pages = [http.get(FED + "fomccalendars.htm", headers={"User-Agent": UA}).text]
    cur = sorted({int(d[:4]) for d in re.findall(r"monetary(\d{8})a\.htm", pages[0])})
    for y in range(2000, (min(cur) if cur else 2021)):
        r = http.get(FED + f"fomchistorical{y}.htm", headers={"User-Agent": UA})
        if r.status_code == 200:
            pages.append(r.text)
    ds = set()
    for p in pages:
        ds |= {pd.Timestamp(d) for d in re.findall(r"monetary(\d{8})a\.htm", p)}
        # strony historyczne: link z tekstem „Statement” (format adresu zmieniał się w czasie)
        for h in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:Press\s+)?Statement\s*</a>', p, re.I):
            m = re.search(r"(\d{8})", h)
            if m:
                ds.add(pd.Timestamp(m.group(1)))
    return sorted(d for d in ds if d.year >= 2000)


def opec(http: Http) -> pd.DataFrame:
    d = pd.read_excel(io.BytesIO(http.get(KANZIG).content), sheet_name="Daily")
    if "Date/Contract" not in d or "PC" not in d:
        raise ValueError("format Känzig: brak kolumn Date/Contract, PC")
    return pd.DataFrame({"date": pd.to_datetime(d["Date/Contract"]), "pc": pd.to_numeric(d["PC"])}).dropna()


def hurricanes(http: Http) -> pd.DataFrame:
    idx = http.get(NHC).text
    name = sorted(set(re.findall(r"hurdat2-1851-\d{4}-\d+\.txt", idx)))[-1]
    txt = http.get(NHC + "hurdat/" + name).text
    rows, storm = [], None
    for line in txt.splitlines():
        f = [x.strip() for x in line.split(",")]
        if f[0][:2] == "AL" and len(f) >= 3 and not f[0][2:].isalpha() and len(f[0]) == 8:
            storm, seen = f[0] + " " + f[1], False
            continue
        if storm is None or len(f) < 7 or seen:
            continue
        lat = float(f[4][:-1]) * (1 if f[4][-1] == "N" else -1)
        lon = float(f[5][:-1]) * (-1 if f[5][-1] == "W" else 1)
        if f[3] == "HU" and GOM[0] <= lat <= GOM[1] and GOM[2] <= lon <= GOM[3]:
            rows.append((storm, pd.Timestamp(f[0] + f[1].zfill(4)), int(f[6])))
            seen = True
    return pd.DataFrame(rows, columns=["storm", "time", "wind"]).assign(file=name)


def collect(con, full: bool = False) -> int:
    http = Http(min_interval=0.5)
    rows = []
    for d in fomc_dates(http):
        rows.append(("fed", "fomc", f"fomc-{d.date()}", d.date(), local_to_utc(d, "14:15", ET), None, "komunikat FOMC", "public_domain"))
    o = opec(http)
    for r in o.itertuples():
        rows.append(("kanzig", "opec", f"opec-{r.date.date()}", r.date.date(), r.date, float(r.pc),
                     "niespodzianka OPEC (PC zmian futures w dniu komunikatu)", "cc_by"))
    h = hurricanes(http)
    for r in h.itertuples():
        rows.append(("noaa", "hurricane_gom", f"hu-{r.storm.replace(' ', '_')}", r.time.date(), r.time, float(r.wind),
                     f"{r.storm}: wejście huraganu do Zatoki Meksykańskiej ({r.file})", "public_domain"))
    con.executemany("INSERT OR REPLACE INTO events_calendar VALUES (?,?,?,?,?,?,?,?)", rows)
    log.info("kalendarz: FOMC %d (%s..), OPEC %d, huragany w Zatoce %d", sum(r[1] == "fomc" for r in rows),
             min(r[3] for r in rows if r[1] == "fomc"), len(o), len(h))
    return 0

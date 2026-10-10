"""yfinance GC=F / SI=F — bieżące dni metali między ręcznymi aktualizacjami Stooq (raz na kwartał).

Okno 6 mies. > kwartał, więc luka Stooq -> Yahoo nie powstaje nawet przy kilku pominiętych przebiegach.
Uwaga: GC=F/SI=F to kontrakty terminowe (front, z rollem), Stooq XAUUSD/XAGUSD to spot —
poziomy różnią się o bazę; to uzupełnienie dat, nie ta sama seria.
"""

from ms.collectors._yahoo import collect_symbols

NAME = "yf_metals"
SYMBOLS = {"GC=F": ("YF.GC=F.close", "Yahoo GC=F close (COMEX gold front, z rollem)"),
           "SI=F": ("YF.SI=F.close", "Yahoo SI=F close (COMEX silver front, z rollem)")}


def collect(con, full: bool = False) -> int:
    return collect_symbols(con, SYMBOLS, "6mo")

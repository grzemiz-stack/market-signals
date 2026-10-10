"""yfinance CL=F / BZ=F — TYLKO uzupełnienie bieżących dni, których EIA jeszcze nie opublikowało (EIA: co tydzień)."""

from ms.collectors._yahoo import collect_symbols

NAME = "yf_oil"
SYMBOLS = {"CL=F": ("YF.CL=F.close", "Yahoo CL=F close (ciągły, z rollem)"),
           "BZ=F": ("YF.BZ=F.close", "Yahoo BZ=F close (ciągły, z rollem)")}


def collect(con, full: bool = False) -> int:
    return collect_symbols(con, SYMBOLS, "1mo")

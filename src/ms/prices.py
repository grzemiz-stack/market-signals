"""Ceny bazowe aktywów: poziom, logret, flagi, źródło i known_at każdego zamknięcia.

XAU/XAG: stitch_metals(Stooq spot, Yahoo GC=F/SI=F). WTI/BRENT: stitch(EIA spot, Yahoo CL=F/BZ=F) —
ta sama logika szwu. BTC/ETH: Binance spot close.
Wartość <= 0 -> logret NaN z flagą (log_returns), nigdy cicho. Szereg z pierwszych publikacji (pit.first_release).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ms.pit import first_release
from ms.transforms import log_returns, stitch, stitch_metals

ASSETS = {
    "XAU": ("XAUUSD.close", "YF.GC=F.close"),
    "XAG": ("XAGUSD.close", "YF.SI=F.close"),
    "WTI": ("EIA.RWTC", "YF.CL=F.close"),
    "BRENT": ("EIA.RBRTE", "YF.BZ=F.close"),
    "BTC": ("BTCUSDT.close", None),
    "ETH": ("ETHUSDT.close", None),
}


def price_frame(con, asset: str) -> pd.DataFrame:
    """Indeks: observed_at. Kolumny: value, logret, flag, source, known_at.
    Wiersze sparse_history (rzadka wczesna historia Stooq) są pomijane — to nie są notowania dzienne."""
    primary, secondary = ASSETS[asset]
    fr = first_release(con, [s for s in (primary, secondary) if s])
    fr = fr[~fr["flags"].fillna("").str.contains("sparse_history")]
    p = fr[fr.series_id == primary].set_index("observed_at")
    if secondary is None:
        lr = log_returns(p["value"])
        out = pd.DataFrame({"value": p["value"], "logret": lr["logret"], "flag": lr["flag"], "source": primary})
    else:
        s = fr[fr.series_id == secondary].set_index("observed_at")
        fn = stitch_metals if asset in ("XAU", "XAG") else stitch
        out = fn(p["value"], s["value"])
        out["source"] = np.where(out["source"] == "yahoo", secondary, primary)
        out = out.drop(columns=["basis_factor"])
    known = pd.concat([p["known_at"].rename("k").to_frame().assign(src=primary),
                       fr[fr.series_id == secondary].set_index("observed_at")["known_at"].rename("k").to_frame().assign(src=secondary)
                       if secondary else None])
    known = known.reset_index().set_index(["observed_at", "src"])["k"]
    out["known_at"] = [known.get((d, src)) for d, src in zip(out.index, out["source"])]
    out.index.name = "observed_at"
    return out.sort_index()

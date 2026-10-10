"""Etap 4H, część 2–3: badania zdarzeń i testy miesięczne. Reguły statusów: ms.hypotheses.classify (wspólne).

Badanie zdarzeń: zdarzenie znane w chwili T; dzień 0 = pierwsze zamknięcie aktywa ZNANE po T; CAR[0,+k] =
log(P[d0+k] / P[d0−1]). Punkt odniesienia: 2000 losowań N dat losowych (z tego samego okresu, ≥ 20 dni od zdarzeń)
-> p dwustronne dla średniej CAR. Regresja na wielkości zdarzenia (ZR): CAR na wartości zdarzenia (HC1).
Test główny = wszystkie zdarzenia (przy zdarzeniach 3 lata to za mało obserwacji — adaptacja opisana w raporcie);
obok podzbiór z ostatnich 3 lat.
Skoki (GPR, GDELT): wartość dzienna w górnych 5% względem mediany z 90 poprzednich dni (krachy Nasdaq: 1% najgorszych dni),
co najmniej 20 dni odstępu między zdarzeniami.
GDELT: zdarzenia z data/gdelt.duckdb (READ_ONLY), BEZ par USA–USA (decyzja 2026-10-06), dzień = data DATEADDED (UTC).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ms import db
from ms.hypotheses import ols_uni
from ms.prices import price_frame

N_RANDOM = 2000
DECLUSTER = 20
SPIKE_Q = 0.95  # plan 4H: skoki > 95. percentyla
PRODUCERS = ("SAU", "IRN", "IRQ", "ARE", "KWT", "LBY", "NGA", "VEN", "RUS")
HORMUZ = (24.0, 28.0, 54.0, 58.0)
RED_SEA = (11.0, 20.0, 38.0, 45.0)


# --------------------------------------------------------------------------- zdarzenia


def decluster(times: pd.Series, gap_days: int = DECLUSTER) -> pd.Series:
    out, last = [], None
    for t in sorted(times):
        if last is None or (t - last).days >= gap_days:
            out.append(t)
            last = t
    return pd.Series(out)


def spikes(daily: pd.Series, q: float = SPIKE_Q, min_count: float | None = None) -> pd.Series:
    """Dni skoku: log((x+1)/(mediana z 90 poprzednich dni + 1)) w górnym (1−q); zwraca czasy T = koniec dnia."""
    base = daily.shift(1).rolling(90, min_periods=60).median()
    z = np.log((daily + 1) / (base + 1))
    thr = z.quantile(q)
    sel = z[(z >= thr) & ((daily >= min_count) if min_count else True)].index
    return decluster(pd.Series(sel) + pd.Timedelta(days=1))  # znane po zakończeniu dnia (UTC)


def gdelt_daily(category: str) -> pd.Series:
    """Dzienna liczba zdarzeń GDELT danej kategorii (data DATEADDED, UTC), bez par USA–USA."""
    import duckdb

    con = duckdb.connect(str(db.GDELT_PATH), read_only=True)
    prod = ", ".join(f"'{p}'" for p in PRODUCERS)
    base = ("NOT (coalesce(actor1_country,'') = 'USA' AND coalesce(actor2_country,'') = 'USA')")
    cond = {
        "all": "TRUE",
        "producers": f"(actor1_country IN ({prod}) OR actor2_country IN ({prod}))",
        "nonenergy": f"NOT (coalesce(actor1_country,'') IN ({prod}) OR coalesce(actor2_country,'') IN ({prod}))",
        "chokepoints": (f"((action_geo_lat BETWEEN {HORMUZ[0]} AND {HORMUZ[1]} AND action_geo_long BETWEEN {HORMUZ[2]} AND {HORMUZ[3]})"
                        f" OR (action_geo_lat BETWEEN {RED_SEA[0]} AND {RED_SEA[1]} AND action_geo_long BETWEEN {RED_SEA[2]} AND {RED_SEA[3]}))"),
    }[category]
    df = con.execute(f"SELECT CAST(known_at AS DATE) AS d, count(*) AS n FROM events WHERE {base} AND {cond} GROUP BY 1 ORDER BY 1").df()
    con.close()
    s = pd.Series(df["n"].to_numpy(dtype=float), index=pd.to_datetime(df["d"]))
    return s.reindex(pd.date_range(s.index.min(), s.index.max()), fill_value=0.0)


def event_times(con, name: str) -> pd.DataFrame:
    """Kolumny: T (chwila, od której zdarzenie jest znane), x (wielkość, jeśli jest)."""
    if name in ("fomc", "opec", "hurricane_gom"):
        df = con.execute("SELECT known_at AS T, value AS x, event_date FROM events_calendar WHERE event_type=? ORDER BY 1",
                         [name]).df()
        if name == "fomc":  # wielkość: zmiana DGS2 w dniu komunikatu (wartości wg daty obserwacji)
            d = con.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id='FRED.DGS2' ORDER BY 1").df()
            s = pd.Series(d["value"].to_numpy(), index=pd.to_datetime(d["observed_at"])).diff()
            df["x"] = [s.get(pd.Timestamp(e), np.nan) for e in df["event_date"]]
        return df[["T", "x"]]
    if name == "gpr_spikes":
        d = con.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id='GPR.GPRD' ORDER BY 1").df()
        return pd.DataFrame({"T": spikes(pd.Series(d["value"].to_numpy(), index=pd.to_datetime(d["observed_at"]))), "x": np.nan})
    if name == "nasdaq_crash":
        d = con.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id='FRED.NASDAQCOM' ORDER BY 1").df()
        r = np.log(pd.Series(d["value"].to_numpy(), index=pd.to_datetime(d["observed_at"]))).diff()
        sel = r[r <= r.quantile(0.01)].index
        return pd.DataFrame({"T": decluster(pd.Series(sel) + pd.Timedelta(hours=21)), "x": np.nan})  # po zamknięciu NY
    if name.startswith("gdelt_"):
        return pd.DataFrame({"T": spikes(gdelt_daily(name[6:]), min_count=10), "x": np.nan})
    raise KeyError(name)


# --------------------------------------------------------------------------- CAR i punkt odniesienia


def car_table(pf: pd.DataFrame, T: pd.Series, k: int, start_offset: int = -1) -> np.ndarray:
    """CAR[0,+k] = log(P[d0+k]/P[d0+start_offset]) (start_offset=-1: od zamknięcia przed zdarzeniem; 0: od dnia 0)."""
    p = pf[pf["value"] > 0]
    known = p["known_at"].to_numpy()
    v = np.log(p["value"].to_numpy())
    out = np.full(len(T), np.nan)
    for i, t in enumerate(pd.to_datetime(T)):
        d0 = np.searchsorted(known, np.datetime64(t), side="right")  # pierwsze zamknięcie znane po T
        a, b = d0 + start_offset, d0 + k
        if a >= 0 and b < len(v):
            out[i] = v[b] - v[a]
    return out


def event_study(pf: pd.DataFrame, events: pd.DataFrame, k: int, start_offset: int = -1, seed: int = 0) -> dict:
    T = pd.to_datetime(events["T"])
    T = T[(T > pf["known_at"].min() + pd.Timedelta(days=30)) & (T < pf["known_at"].max() - pd.Timedelta(days=2 * k + 10))]
    car = car_table(pf, T, k, start_offset)
    ok = np.isfinite(car)
    car, T = car[ok], T[ok]
    if len(car) < 5:
        return {"n": len(car)}
    # punkt odniesienia: losowe chwile z tego samego okresu, >= 20 dni od zdarzeń
    rng = np.random.default_rng(seed)
    days = pd.date_range(T.min() - pd.Timedelta(days=365), T.max(), freq="D") + pd.Timedelta(hours=12)
    ev = np.sort(T.to_numpy())
    pos = np.searchsorted(ev, days.to_numpy())
    near = np.zeros(len(days), bool)
    for off in (pos - 1, pos):
        okk = (off >= 0) & (off < len(ev))
        near[okk] |= np.abs((days.to_numpy()[okk] - ev[off[okk]]) / np.timedelta64(1, "D")) < DECLUSTER
    pool = car_table(pf, pd.Series(days[~near]), k, start_offset)
    pool = pool[np.isfinite(pool)]
    means = np.array([rng.choice(pool, len(car), replace=False).mean() for _ in range(N_RANDOM)])
    m = car.mean()
    p = 2 * min((means >= m).mean(), (means <= m).mean())
    return {"n": len(car), "mean": m, "mean_random": means.mean(), "abn": m - means.mean(), "p": max(p, 1 / N_RANDOM),
            "car": pd.Series(car, index=T.to_numpy())}


def event_regression(pf: pd.DataFrame, events: pd.DataFrame, k: int, start_offset: int = -1) -> dict:
    ev = events.dropna(subset=["x"])
    car = car_table(pf, pd.to_datetime(ev["T"]), k, start_offset)
    ok = np.isfinite(car)
    ev, car = ev[ok], car[ok]
    b, se, p, n = ols_uni(ev["x"].to_numpy(dtype=float), car)
    return {"n": n, "beta": b, "se": se, "p": p, "car": pd.Series(car, index=pd.to_datetime(ev["T"]).to_numpy()),
            "x": pd.Series(ev["x"].to_numpy(dtype=float), index=pd.to_datetime(ev["T"]).to_numpy())}


# --------------------------------------------------------------------------- miesięczne (wartości wg daty obserwacji)


def monthly_frame(con, asset: str) -> pd.DataFrame:
    """Zwrot miesięczny aktywa (ostatnie zamknięcie miesiąca) + czynniki miesięczne wg DATY OBSERWACJI.
    To test zależności ekonomicznej, NIE cecha PIT (serie makro publikowane z opóźnieniem — flaga w raporcie)."""
    pf = price_frame(con, asset)
    px = pf["value"].where(pf["value"] > 0).resample("ME").last()
    M = pd.DataFrame({"mret": np.log(px).diff()})

    def ser(sid):
        d = con.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id=? ORDER BY 1", [sid]).df()
        s = pd.Series(d["value"].to_numpy(dtype=float), index=pd.to_datetime(d["observed_at"]))
        return s.resample("ME").last()

    M["copper_chg"] = np.log(ser("FRED.PCOPPUSDM")).diff()
    M["indpro_chg"] = np.log(ser("FRED.INDPRO")).diff()
    M["igrea_chg"] = ser("FRED.IGREA").diff()
    M["bh_supply"] = ser("BH.SUPPLY")
    M["bh_inv_demand"] = ser("BH.INV_DEMAND")
    M["oecd_stocks_chg"] = ser("EIA.STEO_OECD_STOCKS").diff()
    return M.replace([np.inf, -np.inf], np.nan)

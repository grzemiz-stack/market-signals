"""Analogie historyczne: dni o podobnym układzie cech (z-score) i co działo się po nich.

- Wektor: z-score cech dostępnych w dniu zapytania (bez short_history).
- Odległość: w każdej grupie RMS różnic z-score po cechach obecnych u obu dni (grupa waży tyle samo bez względu
  na liczbę cech); wynik = średnia po grupach. Kandydat musi mieć WSZYSTKIE grupy obecne w zapytaniu
  oraz >= 70% cech zapytania (bez tego okresy ubogie w dane wychodziły sztucznie blisko).
- Kandydat: data <= zapytanie − 60 dni ORAZ cała 60-dniowa ścieżka kończy się przed zapytaniem (path_end < zapytanie).
- Wybór: k najbliższych z odstępem >= 20 dni między analogiami.
- Punkt odniesienia: losowe daty z tego samego tercyla rv_60d (wśród kandydatów); rozkład zerowy z 1000 losowań ->
  percentyl statystyk analogii. Wszystkie 4 kluczowe statystyki w 2,5–97,5 percentylu = „nie różnią się od losowych”.
  (Próg 10–90 dawałby przy 4 statystykach ~59% fałszywych „różnic” na czystym szumie; 2,5–97,5 -> ~19%.)
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

K = 20
MIN_GAP_DAYS = 20
EXCLUDE_DAYS = 60
MIN_FEATURE_SHARE = 0.70
N_NULL = 1000
KEY_STATS = ("up_rate", "down_rate", "median_ret_20d", "median_ret_60d")
NULL_LO, NULL_HI = 2.5, 97.5


@dataclass
class Result:
    asset: str
    query: pd.Timestamp
    analogs: pd.DataFrame
    random: pd.DataFrame
    stats: dict
    random_stats: dict
    null_pct: dict
    tercile: int
    n_candidates: int
    groups_used: list[str]
    oldest_candidate: pd.Timestamp | None
    base_up: float
    base_down: float


@dataclass
class Data:
    """Wszystko, czego potrzebuje wybór analogii — ładowane raz na aktywo."""
    asset: str
    z: pd.DataFrame
    groups: dict[str, str]
    lab: pd.DataFrame
    rv: pd.Series  # rv_60d (surowe) na dniach decyzji — także dla dni bez etykiet


def load(con, asset: str) -> Data:
    f = con.execute("""SELECT date, feature, grp, value_z FROM features_daily
                       WHERE asset = ? AND NOT short_history""", [asset]).df()
    groups = dict(f[["feature", "grp"]].drop_duplicates().values)
    z = f.pivot(index="date", columns="feature", values="value_z")
    z.index = pd.to_datetime(z.index)
    rv = con.execute("SELECT date, value_raw FROM features_daily WHERE asset=? AND feature='rv_60d'", [asset]).df()
    lab = con.execute("SELECT * EXCLUDE (asset, built_at) FROM labels WHERE asset = ?", [asset]).df()
    lab["date"] = pd.to_datetime(lab["date"])
    rv = rv.assign(date=pd.to_datetime(rv["date"])).set_index("date")["value_raw"].rename("rv_60d")
    lab = lab.set_index("date").join(rv)
    return Data(asset, z, groups, lab, rv)


def distances(z: pd.DataFrame, q: pd.Series, groups: dict[str, str]) -> pd.DataFrame:
    """Kolumny: distance, n_groups. Cechy z NaN pomijane (w zapytaniu i u kandydata)."""
    qf = q.dropna()
    per_group = {}
    n_feat = z[qf.index].notna().sum(axis=1)
    for g in sorted({groups[c] for c in qf.index}):
        cols = [c for c in qf.index if groups[c] == g]
        diff2 = (z[cols] - qf[cols]) ** 2
        per_group[g] = np.sqrt(diff2.mean(axis=1, skipna=True))  # RMS: grupa waży tyle samo bez względu na liczbę cech
    d = pd.DataFrame(per_group)
    return pd.DataFrame({"distance": d.mean(axis=1, skipna=True), "n_groups": d.notna().sum(axis=1), "n_features": n_feat})


def pick_spaced(dates: pd.DatetimeIndex, k: int, gap_days: int = MIN_GAP_DAYS) -> list[pd.Timestamp]:
    """Kolejno z podanej kolejności (np. po odległości), z odstępem >= gap_days od już wybranych."""
    chosen: list[pd.Timestamp] = []
    for d in dates:
        if all(abs((d - c).days) >= gap_days for c in chosen):
            chosen.append(d)
            if len(chosen) == k:
                break
    return chosen


def summarize(lab: pd.DataFrame) -> dict:
    def pct(s, p):
        return float(np.expm1(np.nanpercentile(s, p))) if s.notna().any() else np.nan
    u, dn = lab["up_5d"].astype(float), lab["down_5d"].astype(float)
    return {
        "N": len(lab),
        "up": int(np.nansum(u)), "down": int(np.nansum(dn)), "flat": int(((u == 0) & (dn == 0)).sum()),
        "up_rate": float(np.nanmean(u)) if u.notna().any() else np.nan,
        "down_rate": float(np.nanmean(dn)) if dn.notna().any() else np.nan,
        **{f"{s}_ret_{h}d": pct(lab[f"fwd_ret_{h}d"], p) for h in (5, 20, 60)
           for s, p in (("p10", 10), ("median", 50), ("p90", 90))},
        "median_max_dd_60d": pct(lab["fwd_max_dd_60d"], 50),
        "p10_max_dd_60d": pct(lab["fwd_max_dd_60d"], 10),
        "median_days_to_recover": float(np.nanmedian(lab["fwd_days_to_recover"])) if lab["fwd_days_to_recover"].notna().any() else np.nan,
        "recovered_share": float(lab["fwd_days_to_recover"].notna().mean()),
    }


def eligible(lab: pd.DataFrame, qd: pd.Timestamp) -> pd.DataFrame:
    """Etykiety, które zapytanie z dnia qd może widzieć: cała ścieżka zakończona przed qd, data <= qd − 60 dni,
    pełne etykiety (σ wymaga 252 obs historii)."""
    return lab[(lab.index <= qd - pd.Timedelta(days=EXCLUDE_DAYS)) & (lab["path_end"] < qd)
               & lab["fwd_ret_60d"].notna() & lab["up_5d"].notna()]


def select(d: Data, query, k: int = K, n_null: int = N_NULL) -> Result:
    """Rdzeń bez dostępu do bazy. n_null=0 pomija rozkład zerowy (walidacja)."""
    query = pd.Timestamp(query).normalize()
    qd = d.z.index[d.z.index <= query].max()  # ostatni dzień decyzji <= zapytanie
    q = d.z.loc[qd]
    q_groups = sorted({d.groups[c] for c in q.dropna().index})
    elig = eligible(d.lab, qd)
    dist = distances(d.z.loc[d.z.index.intersection(elig.index)], q, d.groups)
    need = math.ceil(MIN_FEATURE_SHARE * q.notna().sum())
    dist = dist[(dist["n_groups"] == len(q_groups)) & (dist["n_features"] >= need)].sort_values("distance")
    chosen = pick_spaced(dist.index, k)
    analogs = dist.loc[chosen].join(d.lab).sort_values("distance")

    # punkt odniesienia: ten sam tercyl rv_60d wśród dopuszczalnych kandydatów
    cand = elig.loc[elig.index.intersection(dist.index)]
    rvq = d.rv.get(qd, np.nan)
    terc, rand_dates, pool = 1, [], pd.DatetimeIndex([])
    rng = np.random.default_rng(zlib.crc32(f"{d.asset}{qd.date()}".encode()))
    if len(cand) >= 3:
        cuts = np.nanpercentile(cand["rv_60d"], [100 / 3, 200 / 3])
        terc = int(np.searchsorted(cuts, rvq)) if not np.isnan(rvq) else 1
        pool = cand[np.searchsorted(cuts, cand["rv_60d"].to_numpy()) == terc].index
        rand_dates = pick_spaced(pd.DatetimeIndex(rng.permutation(pool)), k)
    random = d.lab.loc[rand_dates]

    stats, rstats = summarize(analogs), summarize(random)
    null_pct = {}
    if n_null and len(pool):
        null = pd.DataFrame([summarize(d.lab.loc[pick_spaced(pd.DatetimeIndex(rng.permutation(pool)), k)]) for _ in range(n_null)])
        null_pct = {s: float((null[s] < stats[s]).mean() * 100 + (null[s] == stats[s]).mean() * 50) for s in KEY_STATS}
    return Result(d.asset, qd, analogs, random, stats, rstats, null_pct, terc, len(dist), q_groups,
                  dist.index.min() if len(dist) else None,
                  float(elig["up_5d"].astype(float).mean()), float(elig["down_5d"].astype(float).mean()))


def find(con, asset: str, query, k: int = K) -> Result:
    return select(load(con, asset), query, k)


def verdict(r: Result) -> str:
    outside = [s for s, p in r.null_pct.items() if p < NULL_LO or p > NULL_HI]
    if not outside:
        return ("**Analogie NIE różnią się od losowych dat z tego samego tercyla zmienności** "
                f"(wszystkie {len(KEY_STATS)} kluczowe statystyki w {NULL_LO}–{NULL_HI} percentylu rozkładu zerowego). "
                "Traktuj wynik jako szum.")
    return ("Analogie różnią się od losowych w: " + ", ".join(f"{s} (percentyl {r.null_pct[s]:.0f})" for s in outside)
            + f". Przy {len(KEY_STATS)} statystykach ok. 19% zapytań pokazuje taką różnicę przypadkiem, "
            "a N=20 to słaba podstawa — sprawdź listę dat.")


def disclaimer() -> str:
    """Stały nagłówek (decyzja 2026-10-06): analogie to narzędzie do nauki, nie sygnał."""
    from ms.db import ROOT
    evals = sorted((ROOT / "reports").glob("analogs-eval-*.md"))
    link = f"[{evals[-1].name}]({evals[-1].name})" if evals else "reports/analogs-eval-*.md (brak raportu)"
    return f"> **Nie jest to prognoza — walidacja: brak przewagi nad częstością bazową ({link}).**"


def to_markdown(r: Result) -> str:
    def fmt(v, pct=True):
        return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:+.1%}" if pct else f"{v:.0f}")

    rows = [("N", r.stats["N"], r.random_stats["N"], False),
            ("up / down / bez ruchu (5d, ±1,5σ)", f"{r.stats['up']} / {r.stats['down']} / {r.stats['flat']}",
             f"{r.random_stats['up']} / {r.random_stats['down']} / {r.random_stats['flat']}", None)]
    for h in (5, 20, 60):
        rows.append((f"zwrot {h}d: mediana [p10, p90]",
                     f"{fmt(r.stats[f'median_ret_{h}d'])} [{fmt(r.stats[f'p10_ret_{h}d'])}, {fmt(r.stats[f'p90_ret_{h}d'])}]",
                     f"{fmt(r.random_stats[f'median_ret_{h}d'])} [{fmt(r.random_stats[f'p10_ret_{h}d'])}, {fmt(r.random_stats[f'p90_ret_{h}d'])}]", None))
    rows += [("max DD 60d: mediana / p10", f"{fmt(r.stats['median_max_dd_60d'])} / {fmt(r.stats['p10_max_dd_60d'])}",
              f"{fmt(r.random_stats['median_max_dd_60d'])} / {fmt(r.random_stats['p10_max_dd_60d'])}", None),
             ("dni do powrotu: mediana (odsetek, który wrócił)",
              f"{fmt(r.stats['median_days_to_recover'], False)} ({r.stats['recovered_share']:.0%})",
              f"{fmt(r.random_stats['median_days_to_recover'], False)} ({r.random_stats['recovered_share']:.0%})", None)]
    out = [f"## Analogie {r.asset} na {r.query.date()}", "", disclaimer(), "",
           f"Grupy w wektorze: {', '.join(r.groups_used)}. Kandydatów: {r.n_candidates}. "
           f"Tercyl rv_60d zapytania: {r.tercile + 1}/3. "
           f"Najstarszy dopuszczalny kandydat (wszystkie grupy zapytania, >= {MIN_FEATURE_SHARE:.0%} cech): "
           f"{r.oldest_candidate.date() if r.oldest_candidate is not None else '—'}.", "",
           "| | analogie | losowe (ten sam tercyl rv_60d) |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c, _ in rows]
    out += ["", "Percentyl statystyk analogii w rozkładzie 1000 losowań: " +
            ", ".join(f"{s} {p:.0f}" for s, p in r.null_pct.items()), "", verdict(r), "",
            "| data | odległość | grupy | cechy | zwrot 5d | 20d | 60d | up | down | max DD | dni do powrotu |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, a in r.analogs.iterrows():
        out.append(f"| {d.date()} | {a['distance']:.2f} | {int(a['n_groups'])} | {int(a['n_features'])} | {fmt(np.expm1(a['fwd_ret_5d']))} | "
                   f"{fmt(np.expm1(a['fwd_ret_20d']))} | {fmt(np.expm1(a['fwd_ret_60d']))} | {'✓' if pd.notna(a['up_5d']) and a['up_5d'] else ''} | "
                   f"{'✓' if pd.notna(a['down_5d']) and a['down_5d'] else ''} | {fmt(np.expm1(a['fwd_max_dd_60d']))} | {fmt(a['fwd_days_to_recover'], False)} |")
    return "\n".join(out) + "\n"

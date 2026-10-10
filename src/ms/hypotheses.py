"""Testy hipotez z docs/MAPA-ZALEZNOSCI.md na naszych danych (etap 4H). Plan i reguły: docs/ETAP4H-PLAN.md.

Tygodnie jak w dekompozycji (piątek 22:00 UTC; krypto niedziela 24:00), wartości znane na koniec tygodnia.
Typy: B — beta współbieżna (Δ czynnika vs zwrot w tym samym tygodniu); P — predykcyjna (czynnik w t -> zwrot t+1…t+h,
błąd Newey–West przy h > 1); S — sezonowa (dummy); N — hipoteza „brak efektu”; T — przepisana z innego testu (3A).
Test główny = ostatnie 156 tygodni; obok cała historia i bety kroczące 52/156 z ±2 SE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from ms import decompose as dc
from ms.features import COT
from ms.pit import align, available_from, first_release, panel
from ms.prices import price_frame

Q_BH = 0.10
LAST = 156
WINDOWS = (52, 156)
CONFIRM_SHARE = 0.70
WEAKENED_SHARE = 0.60
MIN_WEEKS = 104
N_SMALL = 0.10  # „brak efektu”: |beta standaryzowanej| i jej CI w ±0,10


@dataclass
class Spec:
    id: str
    asset: str
    kind: str          # B | P | S | N | T
    sign: int          # +1 / -1 z literatury (0 dla N i T)
    factor: str        # nazwa kolumny czynnika w ramce tygodniowej
    target: str = "ret"
    h: int = 1         # horyzont predykcji (tygodnie)
    desc: str = ""
    note: str = ""
    freq: str = "W"    # W tygodniowa | M miesięczna | E zdarzenia
    events: str = ""   # nazwa zdarzeń (hyp_events.event_times)
    k: int = 5         # okno zdarzenia [0,+k] (dni sesyjne)
    start_offset: int = -1
    variant: str = ""  # np. „energetyczne” (O4)


SPECS: list[Spec] = [
    Spec("G1", "XAU", "B", -1, "dfii10_chg", desc="realne stopy 10Y (Δ DFII10)"),
    Spec("G2", "XAU", "B", +1, "t10yie_chg", desc="oczekiwania inflacyjne (Δ T10YIE)"),
    Spec("G3", "XAU", "B", -1, "usd_gram_ret", desc="dolar (koszyk GRAM: EUR, JPY, CNY, AUD)"),
    Spec("G6", "XAU", "B", +1, "gpr_ma7_chg", desc="ryzyko geopolityczne (Δ GPR 7d)"),
    Spec("G10", "XAU", "B", +1, "cot_net_oi_chg", desc="COT managed money: narastanie (Δ net/OI)",
         note="część „skrajność → korekta” w kolumnie dodatkowej"),
    Spec("G11", "XAU", "P", +1, "mom_52w", "fwd_4w", 4, desc="momentum 12 mies. -> zwrot 4 tyg."),
    Spec("S1", "XAG", "B", +1, "xau_ret", desc="złoto (zwrot XAU)"),
    Spec("S3", "XAG", "N", 0, "dfii10_chg", desc="makro monetarne (Δ DFII10) — brak efektu"),
    Spec("S10", "XAG", "S", +1, "oct_nov", desc="sezon Indie (tygodnie X–XI)"),
    Spec("S12", "XAG", "P", +1, "gsr_z", "fwd_rel_13w", 13, desc="wysoki gold/silver ratio -> XAG lepsze od XAU (13 tyg.)"),
    Spec("S13", "XAG", "P", -1, "cot_net_oi_z", "fwd_4w", 4, desc="COT skrajność -> odwrócenie (4 tyg.)"),
    *[Spec("O9", a, "P", -1, "cot_net_oi_z", "fwd_4w", 4, desc="COT skrajność -> ryzyko odwrócenia (4 tyg.)")
      for a in ("WTI", "BRENT")],
    *[Spec("O12", a, "B", -1, "usd_gram_ret", desc="dolar (koszyk GRAM)") for a in ("WTI", "BRENT")],
    *[Spec("O18", a, "T", 0, "", desc="OVX: reżim zmienności (wynik 3A)") for a in ("WTI", "BRENT")],
    *[Spec("C1", a, "P", +1, "ret", "fwd_1w", 1, desc="momentum tygodniowe") for a in ("BTC", "ETH")],
    *[Spec("C7", a, "B", -1, "usd_gram_ret", desc="dolar (koszyk GRAM)") for a in ("BTC", "ETH")],
    *[Spec("C11", a, "P", -1, "funding_z", "fwd_1w", 1, desc="skrajny funding -> spadek (1 tydz.)") for a in ("BTC", "ETH")],
    *[Spec("C12", a, "P", +1, "oi_chg", "fwd_abs_1w", 1, desc="wzrost OI -> większy ruch (wartość bezwzględna zwrotu, 1 tydz.)") for a in ("BTC", "ETH")],
    *[Spec("C13", a, "B", +1, "fng_chg", desc="Fear & Greed zgodny w tym samym tygodniu") for a in ("BTC", "ETH")],
    *[Spec("C14", a, "N", 0, "gpr_ma7_chg", desc="GPR: średnio ≈ 0") for a in ("BTC", "ETH")],
    # ---- część 2: nowe darmowe źródła (zgoda 2026-10-06)
    Spec("G4", "XAU", "ZR", 0, "x", desc="niespodzianka FOMC (Δ DGS2 w dniu komunikatu) -> zwrot [0,+1]; znak sporny",
         freq="E", events="fomc", k=1),
    Spec("G5", "XAU", "Z", +1, "", desc="krach Nasdaq (1% najgorszych dni) -> złoto [0,+15]", freq="E", events="nasdaq_crash", k=15),
    Spec("S2", "XAG", "B", +1, "copper_chg", "mret", desc="miedź (zmiana mies.)", freq="M"),
    *[Spec("O1", a, "B", -1, "bh_supply", "mret", desc="szok podażowy BH (+ = więcej podaży); dane do 2023-04", freq="M")
      for a in ("WTI", "BRENT")],
    *[Spec("O2", a, "B", +1, "igrea_chg", "mret", desc="aktywność globalna (Δ IGREA)", freq="M") for a in ("WTI", "BRENT")],
    *[Spec("O5", a, "ZR", +1, "x", desc="niespodzianka OPEC (Känzig) -> zwrot [+1,+20] po dniu komunikatu",
           freq="E", events="opec", k=20, start_offset=0) for a in ("WTI", "BRENT")],
    *[Spec("O7", a, "P", +1, "backwardation", "fwd_4w", 4, desc="backwardation (RCLC1/RCLC4−1) -> zwrot 4 tyg.; dane do 2024-04")
      for a in ("WTI", "BRENT")],
    *[Spec("O8", a, "B", -1, "oecd_stocks_chg", "mret", desc="zapasy OECD (Δ, STEO najnowsze wydanie)", freq="M")
      for a in ("WTI", "BRENT")],
    *[Spec("O10", a, "P", +1, "crack_z", "fwd_4w", 4, desc="crack 3-2-1 NYH (poziom, z-score 3 lata) -> zwrot 4 tyg.",
           note="Δ cracku zawiera −3·ΔWTI (zależność konstrukcyjna) — dlatego test na poziomie i predykcyjnie")
      for a in ("WTI", "BRENT")],
    *[Spec("O13", a, "Z", +1, "", desc="huragan w Zatoce Meksykańskiej -> [0,+5]", freq="E", events="hurricane_gom", k=5)
      for a in ("WTI", "BRENT")],
    *[Spec("O16", a, "B", +1, "spr_chg", desc="zmiana zapasów SPR (uwolnienie = spadek) — wg daty obserwacji")
      for a in ("WTI", "BRENT")],
    *[Spec("C4", a, "B", +1, "nasdaq_ret", desc="Nasdaq (zwrot tygodniowy)") for a in ("BTC", "ETH")],
    *[Spec("C5", a, "ZR", -1, "x", desc="FOMC (Δ DGS2 w dniu komunikatu) -> zwrot [0,+1]", freq="E", events="fomc", k=1)
      for a in ("BTC", "ETH")],
    *[Spec("C9", a, "P", 0, "stables_chg", "fwd_1w", 1, desc="podaż stablecoinów (Δ log) -> zwrot 1 tydz.; znak sporny")
      for a in ("BTC", "ETH")],
    # ---- część 3: GDELT (bez par USA–USA)
    Spec("G6", "XAU", "Z", +1, "", desc="skoki GPR (górny 1%) -> złoto [0,+5]", freq="E", events="gpr_spikes", k=5),
    *[Spec("O3", a, "Z", +1, "", desc="skoki konfliktów u producentów ropy (GDELT) -> [0,+1] (natychmiast)",
           freq="E", events="gdelt_producers", k=1) for a in ("WTI", "BRENT")],
    *[Spec("O4", a, "Z", +1, "", desc="skoki konfliktów: energetyczne (producenci ropy) -> [0,+20]", freq="E",
           events="gdelt_producers", k=20, variant="energetyczne") for a in ("WTI", "BRENT")],
    *[Spec("O4", a, "Z", -1, "", desc="skoki konfliktów: pozostałe (bez producentów) -> [0,+20]", freq="E",
           events="gdelt_nonenergy", k=20, variant="pozostałe") for a in ("WTI", "BRENT")],
    *[Spec("O14", a, "Z", +1, "", desc="skoki zdarzeń Ormuz / Morze Czerwone (GDELT) -> [0,+5]", freq="E",
           events="gdelt_chokepoints", k=5) for a in ("WTI", "BRENT")],
    *[Spec("C14", a, "Z", -1, "", desc="start konfliktu: skoki wszystkich konfliktów (GDELT) -> [0,+5]", freq="E",
           events="gdelt_all", k=5, variant="zdarzenia") for a in ("BTC", "ETH")],
]
# Konstrukcyjne: czynnik liczony m.in. z ceny aktywa — nie mogą być kandydatami na cechę (decyzja 2026-10-06)
CONSTRUCTIVE = {"C13": "F&G liczony m.in. z ceny i zmienności BTC — zależność konstrukcyjna"}
OOS_SPLIT = pd.Timestamp("2024-01-01")  # kandydaci predykcyjni: estymacja do 2023, test 2024–2026


# --------------------------------------------------------------------------- dane tygodniowe (tylko wartości znane na koniec tygodnia)


def _z_past(s: pd.Series, win: int) -> pd.Series:
    """z-score względem przeszłych `win` tygodni (bez bieżącego)."""
    m, sd = s.shift(1).rolling(win, min_periods=win // 2).mean(), s.shift(1).rolling(win, min_periods=win // 2).std()
    return (s - m) / sd


def weekly(con, asset: str, end=None) -> pd.DataFrame:
    pf = price_frame(con, asset)
    times = dc.week_ends(asset, pf.index.min(), end or pd.Timestamp.now(tz="UTC").tz_localize(None))
    rep, mkt, lng, sht, oi = COT[asset]
    cot = [f"COT.{rep}.{mkt}.{c}" for c in (lng, sht, oi)]
    sids = ["FRED.DFII10", "FRED.T10YIE", "FRED.DEXUSEU", "FRED.DEXJPUS", "FRED.DEXCHUS", "FRED.DEXUSAL", "FNG.crypto", *cot]
    sym = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}.get(asset)
    if sym:
        sids.append(f"{sym}.sum_open_interest")
    P = panel(con, sids, times)
    col = lambda s: P[s] if s in P else pd.Series(np.nan, index=times)  # noqa: E731
    W = pd.DataFrame(index=times)
    W["ret"] = dc.weekly_returns(pf, times)
    W["dfii10_chg"] = col("FRED.DFII10").diff()
    W["t10yie_chg"] = col("FRED.T10YIE").diff()
    usd = pd.concat([-np.log(col("FRED.DEXUSEU")), np.log(col("FRED.DEXJPUS")), np.log(col("FRED.DEXCHUS")),
                     -np.log(col("FRED.DEXUSAL"))], axis=1).mean(axis=1, skipna=False)
    W["usd_gram_ret"] = usd.diff()
    g = first_release(con, ["GPR.GPRD"]).sort_values("observed_at").reset_index(drop=True)
    W["gpr_ma7_chg"] = align(g["value"].rolling(7, min_periods=7).mean(), available_from(g["known_at"]), times).diff()
    ratio = (col(cot[0]) - col(cot[1])) / col(cot[2])
    W["cot_net_oi_chg"] = ratio.diff()
    W["cot_net_oi_z"] = _z_past(ratio, 156)
    W["mom_52w"] = W["ret"].rolling(52, min_periods=52).sum()
    W["fng_chg"] = col("FNG.crypto").diff()
    if sym:
        fr = first_release(con, [f"{sym}.funding.binance"]).sort_values("observed_at").reset_index(drop=True)
        f7 = align(fr["value"].rolling(21, min_periods=21).mean(), available_from(fr["known_at"]), times)
        W["funding_z"] = _z_past(f7, 52)
        W["oi_chg"] = np.log(col(f"{sym}.sum_open_interest")).diff()
    if asset == "XAG":
        xau = price_frame(con, "XAU")
        W["xau_ret"] = dc.weekly_returns(xau, times)
        lvl = lambda f: align(f["value"].reset_index(drop=True), available_from(f["known_at"].reset_index(drop=True)), times)  # noqa: E731
        W["gsr_z"] = _z_past(np.log(lvl(xau)) - np.log(lvl(pf)), 156)  # log(XAU/XAG) z cen znanych na koniec tygodnia
        W["fwd_rel_13w"] = (W["ret"] - W["xau_ret"]).rolling(13).sum().shift(-13)
    # część 2: Nasdaq, crack, SPR (wg daty obserwacji), backwardation, stablecoiny
    P2 = panel(con, ["FRED.NASDAQCOM", "EIA.RCLC1", "EIA.RCLC4", "CM.usdt.SplyCur", "CM.usdc.SplyCur"], times)
    c2 = lambda s: P2[s] if s in P2 else pd.Series(np.nan, index=times)  # noqa: E731
    W["nasdaq_ret"] = np.log(c2("FRED.NASDAQCOM")).diff()
    W["backwardation"] = c2("EIA.RCLC1") / c2("EIA.RCLC4") - 1
    W["stables_chg"] = np.log(c2("CM.usdt.SplyCur").fillna(0) + c2("CM.usdc.SplyCur").fillna(0)).replace(-np.inf, np.nan).diff()
    fr3 = first_release(con, ["EIA.RWTC", "EIA.GASOLINE_NYH", "EIA.ULSD_NYH"])
    wide = fr3.pivot(index="observed_at", columns="series_id", values="value").dropna()
    kn = fr3.pivot(index="observed_at", columns="series_id", values="known_at").reindex(wide.index).max(axis=1)
    crack = (2 * wide["EIA.GASOLINE_NYH"] * 42 + wide["EIA.ULSD_NYH"] * 42 - 3 * wide["EIA.RWTC"]) / 3
    crack_w = align(crack.reset_index(drop=True), available_from(kn.reset_index(drop=True)), times)
    W["crack_z"] = _z_past(crack_w, 156)
    spr = con.execute("SELECT observed_at, value FROM as_of(now()::TIMESTAMP) WHERE series_id='EIA.SPR' ORDER BY 1").df()
    spr_s = pd.Series(spr["value"].to_numpy(), index=pd.to_datetime(spr["observed_at"]))
    lab = dc.label(times, asset)
    W["spr_chg"] = pd.Series([spr_s[spr_s.index <= d].iloc[-1] if (spr_s.index <= d).any() else np.nan for d in lab],
                             index=times).diff()  # wg daty obserwacji (tydzień do piątku), nie publikacji
    W["fwd_1w"] = W["ret"].shift(-1)
    W["fwd_4w"] = W["ret"].rolling(4).sum().shift(-4)
    W["fwd_abs_1w"] = W["ret"].abs().shift(-1)
    W.index = dc.label(times, asset)
    W["oct_nov"] = W.index.month.isin([10, 11]).astype(float)
    return W.replace([np.inf, -np.inf], np.nan)


# --------------------------------------------------------------------------- statystyka


def ols_uni(x: np.ndarray, y: np.ndarray, lags: int = 0) -> tuple[float, float, float, int]:
    """beta, se, p (dwustronne) dla y = a + b·x. lags=0: HC1; lags>0: Newey–West (Bartlett)."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(x)
    if n < 20 or np.var(x) == 0:
        return np.nan, np.nan, np.nan, n
    xc, yc = x - x.mean(), y - y.mean()
    sxx = xc @ xc
    b = (xc @ yc) / sxx
    e = yc - b * xc
    u = xc * e
    s = u @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        s += 2 * w * (u[L:] @ u[:-L])
    var = s / sxx ** 2 * (n / (n - 2) if lags == 0 else 1.0)
    se = math.sqrt(max(var, 0.0))
    p = 2 * stats.t.sf(abs(b / se), n - 2) if se > 0 else np.nan
    return float(b), float(se), float(p), n


def rolling_beta(x: pd.Series, y: pd.Series, win: int, lags: int = 0) -> pd.DataFrame:
    rows = []
    xv, yv = x.to_numpy(), y.to_numpy()
    for i in range(win, len(x) + 1):
        b, se, p, n = ols_uni(xv[i - win : i], yv[i - win : i], lags)
        if n >= 0.8 * win:
            rows.append((x.index[i - 1], b, se, p))
    return pd.DataFrame(rows, columns=["end", "beta", "se", "p"]).set_index("end")


def bh(pvals: list[float]) -> list[float]:
    """Benjamini–Hochberg: p skorygowane (monotoniczne)."""
    p = np.asarray(pvals, dtype=float)
    out = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    m = ok.sum()
    if m == 0:
        return out.tolist()
    idx = np.where(ok)[0][np.argsort(p[ok])]
    ranked = p[idx] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out[idx] = np.minimum(ranked, 1.0)
    return out.tolist()


# --------------------------------------------------------------------------- test jednej hipotezy


@dataclass
class Result:
    spec: Spec
    n_full: int = 0
    n_last: int = 0
    beta_full: float = np.nan
    se_full: float = np.nan
    p_full: float = np.nan
    beta_last: float = np.nan
    se_last: float = np.nan
    p_last: float = np.nan
    std_beta_last: float = np.nan
    std_ci_last: tuple = (np.nan, np.nan)
    share: dict = field(default_factory=dict)      # klucz: f"{okno}_{zakres}_{miara}"
    yearly: pd.DataFrame | None = None             # beta 52-tyg. na koniec roku
    since: pd.Timestamp | None = None
    p_bh: float = np.nan
    status: str = ""
    regime: str = ""
    extra: str = ""


def test_spec(spec: Spec, W: pd.DataFrame) -> Result:
    r = Result(spec)
    if spec.kind == "T" or spec.factor not in W:
        return r
    df = W[[spec.factor, spec.target]].dropna()
    x, y = df[spec.factor], df[spec.target]
    lags = spec.h if spec.kind == "P" and spec.h > 1 else 0
    r.n_full = len(df)
    last_n, wins, min_n = (36, (12, 36), 24) if spec.freq == "M" else (LAST, WINDOWS, MIN_WEEKS)
    if len(df) < min_n:
        return r
    r.since = df.index.min()
    r.beta_full, r.se_full, r.p_full, _ = ols_uni(x.to_numpy(), y.to_numpy(), lags)
    last = df.iloc[-last_n:]
    r.n_last = len(last)
    r.beta_last, r.se_last, r.p_last, _ = ols_uni(last[spec.factor].to_numpy(), last[spec.target].to_numpy(), lags)
    sx, sy = last[spec.factor].std(), last[spec.target].std()
    if sy > 0:
        r.std_beta_last = r.beta_last * sx / sy
        r.std_ci_last = ((r.beta_last - 2 * r.se_last) * sx / sy, (r.beta_last + 2 * r.se_last) * sx / sy)
    cut = df.index[-last_n] if len(df) > last_n else df.index[0]
    lit = spec.sign if spec.sign != 0 else None
    for wi, win in enumerate(wins):
        wkey = WINDOWS[wi]  # klucze 52/156 także dla okien miesięcznych 12/36 (te same proporcje)
        rb = rolling_beta(x, y, win, lags)
        if rb.empty:
            continue
        sig = (rb["beta"].abs() > 2 * rb["se"])
        for rng, sub_mask in (("cala", np.ones(len(rb), bool)), ("3lata", rb.index >= cut), ("wczesniej", rb.index < cut)):
            sub, s_sig = rb[sub_mask], sig[sub_mask]
            if len(sub) == 0:
                continue
            if lit:
                r.share[f"{wkey}_{rng}_znak"] = float((np.sign(sub["beta"]) == lit).mean())
                r.share[f"{wkey}_{rng}_istotne"] = float(((np.sign(sub["beta"]) == lit) & s_sig).mean())
            r.share[f"{wkey}_{rng}_istotne_dowolny"] = float(s_sig.mean())
        if wkey == 52:
            ye = rb.groupby(rb.index.year).tail(1)
            r.yearly = ye.assign(rok=ye.index.year).set_index("rok")[["beta", "se"]]
    return r


def classify(r: Result) -> None:
    s = r.spec
    if s.kind == "T":
        return
    if s.freq == "E":
        return classify_event(r)
    if r.n_last < (24 if s.freq == "M" else MIN_WEEKS) or not np.isfinite(r.p_last):
        r.status = "brak danych"
        return
    if s.kind == "N":
        lo, hi = r.std_ci_last
        small = np.isfinite(lo) and -N_SMALL <= lo and hi <= N_SMALL
        r.status = "potwierdzona" if (r.p_last >= Q_BH and small) else "niepotwierdzona"
        if r.status == "niepotwierdzona" and r.p_last < Q_BH:
            r.extra = "jest efekt (hipoteza „brak efektu” odrzucona)"
        elif r.status == "niepotwierdzona":
            r.extra = "efekt nieistotny, ale przedział zbyt szeroki, by uznać go za mały"
        return
    sig = np.isfinite(r.p_bh) and r.p_bh < Q_BH
    if s.sign == 0:  # znak sporny w literaturze: test dwustronny, kierunek ustalony na naszych danych
        r.status = "potwierdzona" if sig else ("osłabła" if r.share.get("156_wczesniej_istotne_dowolny", 0) >= WEAKENED_SHARE
                                                 else "niepotwierdzona")
        if sig:
            r.extra = f"znak sporny w literaturze; u nas {'+' if r.beta_last > 0 else '−'}"
        return
    same = np.sign(r.beta_last) == s.sign
    stable = r.share.get("52_3lata_znak", 0.0) >= CONFIRM_SHARE
    earlier = r.share.get("156_wczesniej_istotne", 0.0)
    if sig and same and stable:
        r.status = "potwierdzona"
    elif sig and not same:
        r.status = "odwrócona"
    elif earlier >= WEAKENED_SHARE:
        r.status = "osłabła"
    else:
        r.status = "niepotwierdzona"
        if sig and same:
            r.extra = f"istotna, ale niestabilna (znak zgodny w {r.share.get('52_3lata_znak', 0):.0%} okien 52-tyg. z 3 lat)"


def describe_regime(r: Result) -> str:
    """Zmiana reżimu wprost: cała historia vs ostatnie 3 lata."""
    if not np.isfinite(r.beta_full) or not np.isfinite(r.beta_last):
        return ""
    def word(b, p):
        return ("istotna " + ("+" if b > 0 else "−")) if p < 0.05 else "nieistotna"
    a, b = word(r.beta_full, r.p_full), word(r.beta_last, r.p_last)
    if a.startswith("istotna") and b == "nieistotna":
        trend = "działała w całej historii, w ostatnich 3 latach przestała"
    elif a == "nieistotna" and b.startswith("istotna"):
        trend = "pojawiła się dopiero w ostatnich 3 latach"
    elif a.startswith("istotna") and b.startswith("istotna") and a[-1] != b[-1]:
        trend = "znak się odwrócił"
    elif a.startswith("istotna") and b.startswith("istotna"):
        ratio = abs(r.beta_last) / abs(r.beta_full) if r.beta_full else np.nan
        trend = f"działa w obu okresach (beta 3 lata = {ratio:.0%} bety z całej historii)"
    else:
        trend = "nieistotna w obu okresach"
    end = {"O1": " (dane BH do 2023-04: „3 lata” = 2020-05…2023-04)", "O7": " (futures EIA do 2024-04: „3 lata” = 2021-04…2024-04)"}
    return f"cała historia ({r.since.year}–): {a}; 3 lata: {b} → {trend} [p surowe < 0,05]" + end.get(r.spec.id, "")


# --------------------------------------------------------------------------- zdarzenia: wynik i status


def test_event(spec: Spec, con, pf) -> Result:
    from ms import hyp_events as he

    r = Result(spec)
    ev = he.event_times(con, spec.events)
    if spec.kind == "ZR":
        res = he.event_regression(pf, ev, spec.k, spec.start_offset)
        r.n_full, r.beta_full, r.se_full, r.p_full = res["n"], res["beta"], res["se"], res["p"]
        car, x = res["car"], res["x"]
        recent = car.index >= car.index.max() - pd.Timedelta(days=3 * 365) if len(car) else []
        if len(car) and np.sum(recent) >= 8:
            r.beta_last, r.se_last, r.p_last, r.n_last = ols_uni(x[recent].to_numpy(), car[recent].to_numpy())
    else:
        res = he.event_study(pf, ev, spec.k, spec.start_offset)
        r.n_full = res.get("n", 0)
        if r.n_full >= 5:
            r.beta_full, r.p_full = res["abn"], res["p"]
            car = res["car"]
            recent = car[car.index >= car.index.max() - pd.Timedelta(days=3 * 365)]
            r.n_last = len(recent)
            r.beta_last = recent.mean() - res["mean_random"] if len(recent) else np.nan
            r.se_full = np.nan
    if r.n_full and r.n_full >= 5:
        r.since = pd.Timestamp(min(res["car"].index))
    return r


def classify_event(r: Result) -> None:
    """Zdarzenia: test główny na WSZYSTKICH zdarzeniach (3 lata = za mało zdarzeń); stabilność = znak w ostatnich 3 latach."""
    s = r.spec
    if r.n_full < 5 or not np.isfinite(r.p_full):
        r.status = "brak danych"
        r.extra = f"zdarzeń z ceną: {r.n_full}"
        return
    sig = np.isfinite(r.p_bh) and r.p_bh < Q_BH
    if s.sign == 0:
        r.status = "potwierdzona" if sig else "niepotwierdzona"
        if sig:
            r.extra = f"znak sporny w literaturze; u nas {'+' if r.beta_full > 0 else '−'}"
        return
    same = np.sign(r.beta_full) == s.sign
    recent_ok = (r.n_last >= 3 and np.isfinite(r.beta_last) and np.sign(r.beta_last) == s.sign)
    if sig and same and (recent_ok or r.n_last < 3):
        r.status = "potwierdzona"
        if r.n_last < 3:
            r.extra = f"w ostatnich 3 latach tylko {r.n_last} zdarzeń — stabilności nie da się sprawdzić"
    elif sig and same:
        r.status = "osłabła"
        r.extra = f"w ostatnich 3 latach znak przeciwny ({r.n_last} zdarzeń)"
    elif sig:
        r.status = "odwrócona"
    else:
        r.status = "niepotwierdzona"


def describe_event(r: Result) -> str:
    if not np.isfinite(r.beta_full):
        return ""
    what = "beta CAR na wielkości zdarzenia" if r.spec.kind == "ZR" else "średni CAR ponad losowe"
    tail = (f"; ostatnie 3 lata: {r.beta_last:+.4f} ({r.n_last} zdarzeń)" if np.isfinite(r.beta_last) else
            f"; ostatnie 3 lata: {r.n_last} zdarzeń")
    return f"{r.n_full} zdarzeń od {r.since.year}: {what} {r.beta_full:+.4f} (p={r.p_full:.3g}){tail}".replace(".", ",", 0)


# --------------------------------------------------------------------------- kandydaci predykcyjni: test poza próbą


def oos_test(spec: Spec, W: pd.DataFrame) -> dict:
    """Estymacja do 2023 (włącznie), test 2024–2026 BEZ zmiany progów: (1) beta w okresie testowym ze znakiem
    z literatury i p < Q_BH; (2) R² poza próbą > 0 (prognoza modelu z danych do 2023 vs średnia z danych do 2023)."""
    df = W[[spec.factor, spec.target]].dropna()
    tr, te = df[df.index < OOS_SPLIT], df[df.index >= OOS_SPLIT]
    lags = spec.h if spec.h > 1 else 0
    if len(tr) < MIN_WEEKS or len(te) < 52:
        return {"ok": False, "why": f"za mało danych (trening {len(tr)}, test {len(te)})"}
    xt, yt = tr[spec.factor].to_numpy(), tr[spec.target].to_numpy()
    b = ((xt - xt.mean()) @ (yt - yt.mean())) / ((xt - xt.mean()) @ (xt - xt.mean()))
    a = yt.mean() - b * xt.mean()
    pred = a + b * te[spec.factor].to_numpy()
    y = te[spec.target].to_numpy()
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - yt.mean()) ** 2).sum()
    bt, se, p, n = ols_uni(te[spec.factor].to_numpy(), y, lags)
    ok = (np.sign(bt) == spec.sign) and p < Q_BH and r2 > 0
    return {"ok": bool(ok), "beta_train": b, "beta_test": bt, "p_test": p, "r2_oos": r2, "n_train": len(tr), "n_test": len(te),
            "why": "" if ok else ("znak/istotność w 2024–2026 nie spełnia progu" if not ((np.sign(bt) == spec.sign) and p < Q_BH)
                                   else "R² poza próbą <= 0")}


def candidate_use(spec: Spec) -> str:
    """Prognoza: czynnik znany PRZED oknem zwrotu (P, zdarzenia z oknem po dniu 0). Dekompozycja: współbieżne."""
    if spec.kind == "P" or (spec.freq == "E" and spec.start_offset >= 0):
        return "prognoza"
    return "dekompozycja"


def oos_event(spec: Spec, con, pf) -> dict:
    """Kandydat predykcyjny ze zdarzeń: estymacja na zdarzeniach do 2023, test na 2024–2026 bez zmiany progów
    (znak z literatury, p < Q_BH, R² poza próbą > 0); wymaga >= 8 zdarzeń w okresie testowym."""
    from ms import hyp_events as he

    ev = he.event_times(con, spec.events)
    ev = ev.dropna(subset=["x"]) if spec.kind == "ZR" else ev
    T = pd.to_datetime(ev["T"])
    car = he.car_table(pf, T, spec.k, spec.start_offset)
    ok = np.isfinite(car)
    tr, te = ok & (T < OOS_SPLIT).to_numpy(), ok & (T >= OOS_SPLIT).to_numpy()
    need = 20 if spec.kind == "ZR" else 8  # regresja wymaga >= 20 obserwacji (ols_uni)
    if te.sum() < need:
        return {"ok": False, "why": f"za mało zdarzeń w 2024–2026 do testu ({int(te.sum())} < {need}) — testu nie da się wykonać",
                "n_test": int(te.sum())}
    x = ev["x"].to_numpy(dtype=float) if spec.kind == "ZR" else np.ones(len(ev))
    xt, yt = x[tr], car[tr]
    b = ((xt - xt.mean()) @ (yt - yt.mean())) / ((xt - xt.mean()) @ (xt - xt.mean())) if spec.kind == "ZR" else 0.0
    a = yt.mean() - b * xt.mean()
    pred, y = a + b * x[te], car[te]
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - yt.mean()) ** 2).sum()
    bt, se, p, n = ols_uni(x[te], y) if spec.kind == "ZR" else (y.mean(), y.std() / np.sqrt(len(y)), np.nan, len(y))
    okk = np.sign(bt) == spec.sign and p < Q_BH and r2 > 0
    return {"ok": bool(okk), "beta_train": b, "beta_test": bt, "p_test": p, "r2_oos": r2, "n_test": int(te.sum()),
            "why": "" if okk else "znak/istotność w 2024–2026 albo R² poza próbą nie spełnia progu"}

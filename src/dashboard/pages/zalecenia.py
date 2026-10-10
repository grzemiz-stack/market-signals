"""Zalecenia: reguły etapu 5 na dziś (tabela rules_today z joba), konta „system”, skrót backtestu, D11."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.common import header, market, paper, table  # noqa: E402
from ms import fmt, views  # noqa: E402

header("Zalecenia")
st.error("**D11: wynik backtestu NIE uprawnia do prawdziwych pieniędzy.** Decyzja o prawdziwych pieniądzach tylko na "
         "podstawie kont „system” na żywo; warunki zostaną ustalone osobno. Zalecenia poniżej to informacja — nic nie "
         "jest składane automatycznie na Twoim koncie.")
with market() as mcon, paper() as pcon:
    rv = views.recommendations_view(mcon, pcon)
    bs = views.backtest_summary(mcon)
rt = rv["rules_today"]
st.markdown(f"Zwycięzca reguły D7: **{rv['winner_d7']}**. Dane odłożone otwarte jeden raz: {rv['holdout_opened']} UTC.")


def show(account_id: int, variant: str, label: str) -> None:
    sub = rt[(rt.account_id == account_id) & (rt.variant == variant)]
    if sub.empty:
        st.markdown("_(brak zaleceń — job rules_today jeszcze nie liczył tego konta)_")
        return
    r0 = sub.iloc[0]
    when = ("**dziś dzień decyzji — " + (f"rebalans: {r0.why}**" if r0.rebalance else "bez rebalansu**")
            if r0.decision_day else f"dziś nie ma decyzji; najbliższa: {str(r0.next_decision)[:10]}")
    st.markdown(f"**{label}** — wariant `{variant}`, dzień danych {str(r0.D)[:10]}, wartość konta "
                f"{fmt.zl(r0.account_value)}; {when}")
    table([{"aktywo": r.asset, "waga docelowa": fmt.pct0(r.target_w), "waga teraz": fmt.pct0(r.current_w),
            "trend (ekspozycja)": fmt.pct0(r.exposure) if pd.notna(r.exposure) else "—",
            "σ roczna": fmt.pct0(r.sigma) if pd.notna(r.sigma) else "—", "źródło σ": r.sigma_src or "—",
            "zlecenie do wag docelowych": fmt.zl(r.order_pln)} for r in sub.itertuples()])


st.subheader("Konta „system” (wykonują reguły automatycznie)")
for a in rv["system_accounts"].itertuples():
    show(int(a.id), a.variant, f"{a.name}")
    st.caption(a.note)

st.subheader("Moje konto — co mówią reguły")
mine = rt[~rt.account_id.isin(rv["system_accounts"]["id"].tolist())]
for acc_id in sorted(mine.account_id.unique()):
    name = mine[mine.account_id == acc_id]["account"].iloc[0]
    show(int(acc_id), rv["winner_d7"], f"{name} — wariant zwycięski (D7)")
    with st.expander("Warianty nie wybrane (do porównania)"):
        for var in [x for x in ("iv_bez_filtra", "iv_filtr", "iv_filtr_ovx") if x != rv["winner_d7"]]:
            show(int(acc_id), var, f"{name} — {var} (nie wybrany)")

st.subheader("Skrót backtestu (1000 zł, koszty jak w grze)")
for key, label in (("dev", "część rozwojowa 2016-10 … 2024-10"), ("holdout", "dane odłożone 2024-10 … 2026-10 (jedyne otwarcie)")):
    st.markdown(f"**{label}**")
    d = bs[key]
    table([{"wariant": r.wariant, "na rękę": fmt.zl(r.na_reke), "zwrot roczny": fmt.pct(r.zwrot_roczny),
            "Sharpe": fmt.num2(r.sharpe), "po cięciu 2× / 4×": f"{fmt.num2(r.sharpe_po_cieciu_2)} / {fmt.num2(r.sharpe_po_cieciu_4)}",
            "maks. obsunięcie": fmt.pct(r.max_obsuniecie),
            **({"Deflated Sharpe": fmt.num3(r.dsr) if pd.notna(r.dsr) else "—"} if key == "dev" else {})}
           for r in d.itertuples()])
st.caption("Raporty: reports/etap5-rozwoj-2026-10-07.md, reports/etap5-odlozone-2026-10-07.md. Sharpe z backtestu na żywo "
           "spada zwykle 2–4× (ZASADY cz. 4).")

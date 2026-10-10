"""Moje konto: wartość, wykres na tle porównań i kont „system”, pozycje, zlecenia oczekujące, dziennik."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.common import accounts, book, daily_chart, header, market, paper, table  # noqa: E402
from ms import fmt, paper as pp, views  # noqa: E402

header("Moje konto")
with paper() as pcon, market() as mcon:
    accs = accounts(pcon)
    name = st.selectbox("Konto", accs["name"].tolist(), index=0)
    acc = pp.account(pcon, int(accs.loc[accs["name"] == name, "id"].iloc[0]))
    b = book()
    v = views.account_view(pcon, mcon, b, acc)
    j = views.journal_view(pcon, acc, executed=v["executed"])
    paths = views.compare_paths(pcon, b, acc)

c1, c2, c3 = st.columns(3)
c1.metric("Wartość konta", fmt.zl(v["value"]), fmt.pct(v["result_pct"]))
c2.metric("Wynik od startu", fmt.zl(v["result_pln"]))
c3.metric("Gotówka", fmt.zl(v["cash"]))
st.markdown(f"Start {fmt.zl(v['start_cash'])} {v['start_date']}. Koszty łącznie {fmt.zl(v['costs'])}, "
            f"podatek {fmt.zl(v['tax'])}, odsetki {fmt.zl(v['interest'])}.")

st.subheader("Wartość na tle porównań")
st.altair_chart(daily_chart(pd.DataFrame(paths)), use_container_width=True)

st.subheader("Pozycje")
table([{"aktywo": p["instrument"], "jednostki": fmt.units(p["units"]), "wartość": fmt.zl(p["value"]),
        "koszt": fmt.zl(p["cost"]), "wynik": fmt.zl(p["pnl"])} for p in v["positions"]])

st.subheader("Porównanie od startu konta")
table([{"": "to konto", "wartość": fmt.zl(v["value"])}] + [{"": k, "wartość": fmt.zl(x)} for k, x in v["benchmarks"].items()])

if j["system"]:
    st.subheader(f"Decyzje reguły ({j['variant']}) — próg wyłączenia D9 {fmt.pct(j['dd_limit'])}")
    table([{"decyzja": str(r.decision_date)[:10], "wykonanie": str(r.exec_date)[:10], "rodzaj": r.kind, "powód": r.why or ""}
           for r in j["decisions"].itertuples()])
else:
    st.subheader("Zlecenia oczekujące")
    table([{"id": r.id, "decyzja": str(r.decision_date)[:10], "strona": r.side, "aktywo": r.asset,
            "kwota": fmt.zl(r.amount_pln) if pd.notna(r.amount_pln) else "—",
            "jednostki": fmt.units(r.units) if pd.notna(r.units) else "wszystko"} for r in v["pending"].itertuples()])
    st.subheader("Dziennik zleceń")
    table([{"id": r.id, "decyzja": str(r.decision_date)[:10], "strona": r.side, "aktywo": r.asset,
            "kwota": fmt.zl(r.amount_pln) if pd.notna(r.amount_pln) else "—", "status": r.status, "powód": r.reason}
           for r in j["orders"].itertuples()])
    if len(j["notes"]):
        st.markdown("**Poprawki i anulowania** (pierwotne powody bez zmian):")
        table([{"zlecenie": r.order_id, "kiedy": str(r.logged_at)[:16], "rodzaj": r.kind, "tekst": r.text}
               for r in j["notes"].itertuples()])

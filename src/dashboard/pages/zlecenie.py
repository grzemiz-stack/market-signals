"""Zlecenie na sucho — ta sama funkcja co `paper.py buy/sell` (ms.paper.order); powód wymagany."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from dashboard.common import book, header, market, paper  # noqa: E402
from ms import fmt, paper as pp, views  # noqa: E402
from ms.trading import GAME_ASSETS  # noqa: E402

header("Zlecenie na sucho")
with paper() as pcon:
    accs = pcon.execute("""SELECT id, name FROM paper_accounts WHERE id NOT IN
                           (SELECT account_id FROM paper_system) ORDER BY id""").df()
with st.form("zlecenie"):
    name = st.selectbox("Konto (konta „system” wykonują wyłącznie reguły)", accs["name"].tolist())
    side = st.radio("Strona", ["buy", "sell"], format_func=lambda s: "kupno" if s == "buy" else "sprzedaż", horizontal=True)
    asset = st.selectbox("Aktywo", GAME_ASSETS)
    amount = st.number_input("Kwota (zł) — dla kupna", min_value=0.0, value=100.0, step=50.0)
    sell_all = st.checkbox("Sprzedaj wszystko (dla sprzedaży)", value=True)
    units = st.number_input("albo jednostki (dla sprzedaży)", min_value=0.0, value=0.0, format="%.6f")
    D = st.date_input("Dzień decyzji", value=date.today())
    reason = st.text_area("Powód decyzji (wymagany)")
    sent = st.form_submit_button("Złóż zlecenie")

if sent:
    b = book()
    with paper(write=True) as pcon, market() as mcon:
        acc = pp.account(pcon, int(accs.loc[accs["name"] == name, "id"].iloc[0]))
        try:
            r = pp.order(pcon, mcon, b, acc, side, asset, reason, amount_pln=amount if side == "buy" else None,
                         units=None if side == "buy" or sell_all else units, D=str(D))
        except (ValueError, PermissionError) as e:
            st.error(f"Zlecenie odrzucone: {e}")
        else:
            if side == "buy":
                s = r["snapshot"]
                st.warning(f"Przy typowym złym tygodniu ({fmt.pct(s['bad_week_pct'] / 100)}) stracisz "
                           f"{fmt.zl(s['bad_week_loss_pln'])} z {fmt.zl(amount)}.")
            st.success(f"Zlecenie {r['id']} przyjęte: {side} {asset}, wykonanie po zamknięciu {r['exec_date'].date()}. "
                       "Powód zapisany w dzienniku.")

st.subheader("Anulowanie / poprawka powodu (nic się nie kasuje)")
with paper() as pcon:
    pend = pcon.execute("SELECT id, account_id, decision_date, side, asset FROM paper_orders WHERE status='pending' "
                        "ORDER BY id").df()
if len(pend):
    with st.form("anuluj"):
        oid = st.selectbox("Zlecenie", pend["id"].tolist(),
                           format_func=lambda i: " ".join(str(x) for x in pend.loc[pend.id == i].iloc[0].tolist()))
        txt = st.text_input("Powód anulowania / poprawiony powód")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Anuluj zlecenie")
        note = c2.form_submit_button("Dopisz poprawkę powodu")
    if cancel or note:
        with paper(write=True) as pcon:
            try:
                if cancel:
                    pp.cancel(pcon, book(), int(oid), txt or "anulowane przez użytkownika")
                    st.success(f"Zlecenie {oid} anulowane (wpis w dzienniku).")
                else:
                    pp.add_note(pcon, int(oid), txt)
                    st.success(f"Dopisano poprawkę do zlecenia {oid}.")
            except (ValueError, LookupError) as e:
                st.error(str(e))
else:
    st.markdown("_(brak zleceń oczekujących)_")
st.caption(f"Ceny z kopii bazy {views.view_meta()['published_at']} UTC.")

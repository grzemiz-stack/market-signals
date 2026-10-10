"""Karty aktywów (strony „Karty moich aktywów” i „Pozostałe aktywa”) — ten sam kod dla obu."""

from __future__ import annotations

import streamlit as st

from dashboard.common import book, daily_chart, market
from ms import fmt, paper as pp, views


def render(assets) -> None:
    t = pp.now_utc()
    b = book()
    with market() as mcon:
        cards = [views.asset_card(mcon, b, a, t) for a in assets]
    for c in cards:
        a = c["asset"]
        st.subheader(f"{a} — {c['instrument']}")
        st.caption(f"ostatnie znane zamknięcie {c['last_close_date']}")
        st.altair_chart(daily_chart(views.price_view(b, a, t).rename(a), y_title="USD"), use_container_width=True)
        st.markdown(c["prob_text"])
        for q, lbl in (("prob_up_5d", "w górę"), ("prob_down_5d", "w dół")):
            st.markdown(f"Model {lbl}: **{c['models'][q]['edge']}**")
        st.markdown(views.vol_text(c))
        amount = st.slider(f"Kwota w {a} (zł) — „zły tydzień”", 100, 5000, 1000, step=100, key=f"bw_{a}")
        loss, q = pp.bad_week_loss(b, a, float(amount), t)
        st.markdown(f"Przy typowym złym tygodniu (5. percentyl zwrotów 5-dniowych z roku: {fmt.pct(q / 100)}) "
                    f"stracisz {fmt.zl(loss)} z {fmt.zl(float(amount))}.")
        if views.decomp_text(c):
            st.markdown(views.decomp_text(c))
        if c["that_day"]:
            st.info(c["that_day"])
        nw = views.news_for_asset(a)
        st.markdown("**Ostatnie wiadomości** (tytuł i link; źródła z planu 4N-live)")
        _news(nw["own"])
        if "gdelt" in nw:
            st.markdown("**Zdarzenia GDELT z ostatnich 24 h** (wg liczby wzmianek)")
            _news(nw["gdelt"], mentions=True)
        with st.expander("Makro (banki centralne, sankcje)"):
            _news(nw["macro"])
        st.divider()


def _news(df, mentions: bool = False) -> None:
    if not len(df):
        st.markdown("_(brak wpisów)_")
        return
    for r in df.itertuples():
        when = str(r.czas)[:16] + (" (czas pobrania)" if r.published_missing else "")
        extra = f", wzmianki {int(r.mentions)}" if mentions and r.mentions == r.mentions and r.mentions is not None else ""
        st.markdown(f"- [{r.title}]({r.url}) — {r.zrodlo}, {when}{extra}")

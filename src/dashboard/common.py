"""Wspólne dla stron dashboardu (etap 4C): połączenia, cache cen, nagłówek, tabele.

Zasady (docs/ETAP4C-PLAN.md): market tylko z kopii data/market_view.duckdb TYLKO DO ODCZYTU, otwieranej na jedno
odświeżenie; liczby wyłącznie z ms.views / ms.paper (te same funkcje co paper.py status), formatowane przez ms.fmt;
zapis tylko do paper.duckdb (zlecenia) przez ms.paper.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ms import paper as pp, views  # noqa: E402


def paper_db() -> Path:
    return Path(os.environ.get("MS_PAPER_DB", pp.PAPER_DB))


@contextmanager
def market():
    """Kopia bazy rynkowej tylko do odczytu — otwarta na czas jednego odświeżenia strony."""
    if not views.view_db().exists():
        st.error(f"Brak kopii bazy {views.view_db()} — uruchom `uv run src/publish_view.py` (robi to job snapshot).")
        st.stop()
    con = views.open_market_view()
    try:
        yield con
    finally:
        con.close()


@contextmanager
def paper(write: bool = False):
    """Baza gry. Domyślnie TYLKO odczyt (wyświetlanie nic nie zmienia; wykonania zapisuje nocny job).
    write=True wyłącznie dla formularzy zleceń/anulowań/poprawek. Zajęta przez job -> do 10 s ponowień."""
    if not write and not paper_db().exists():
        st.info("Brak bazy gry — utwórz konto: `uv run src/paper.py new --name ...`.")
        st.stop()
    for _ in range(20):
        try:
            con = pp.connect(paper_db(), read_only=not write)
            break
        except duckdb.IOException:
            time.sleep(0.5)
    else:
        st.error("Baza gry jest zajęta (pracuje job). Odśwież stronę za chwilę.")
        st.stop()
    try:
        yield con
    finally:
        con.close()


@st.cache_resource(show_spinner=False)
def _book(published_at: str, view_path: str):
    with market() as m:
        return views.load_book(m)


def book():
    """Ceny z kopii bazy; cache do następnej publikacji kopii."""
    return _book(views.view_meta()["published_at"], str(views.view_db()))


def header(title: str) -> None:
    st.title(title)
    st.caption(f"Dane z kopii bazy opublikowanej {views.view_meta()['published_at']} UTC (joby). Dashboard niczego nie liczy po swojemu.")


def table(rows: list[dict] | pd.DataFrame) -> None:
    df = pd.DataFrame(rows)
    st.markdown(df.to_markdown(index=False) if len(df) else "_(brak)_")


def accounts(pcon) -> pd.DataFrame:
    return pcon.execute("SELECT id, name FROM paper_accounts ORDER BY id").df()



def time_axis(span_days: int) -> tuple[dict, str]:
    """Podziałka osi X wg długości zakresu (dni): do 31 dni co dzień (RRRR-MM-DD), do roku co miesiąc, dłużej co
    3 miesiące (RRRR-MM) — przy 2 latach cen podziałka dzienna zapchałaby oś."""
    if span_days <= 31:
        return {"interval": "day", "step": 1}, "%Y-%m-%d"
    if span_days <= 366:
        return {"interval": "month", "step": 1}, "%Y-%m"
    return {"interval": "month", "step": 3}, "%Y-%m"


def daily_chart(df: pd.DataFrame | pd.Series, y_title: str = "zł"):
    """Wykres serii dziennych (indeks = dzień, kolumny = serie). Jawne osie zamiast domyślnych st.line_chart:
    oś Y dopasowana do wartości (zero=False — przy ~1000 zł skala od zera spłaszczała serie do krawędzi), oś X
    w jednostce dnia, podziałka wg długości zakresu (time_axis; przy kilku dniach Vega-Lite wstawiała podziałkę
    12-godzinną)."""
    import altair as alt

    if isinstance(df, pd.Series):
        df = df.to_frame(df.name or "wartość")
    long = (df.rename_axis("dzień").reset_index().melt("dzień", var_name="seria", value_name="wartość")
            .dropna(subset=["wartość"]))
    span = (pd.Timestamp(long["dzień"].max()) - pd.Timestamp(long["dzień"].min())).days if len(long) else 0
    ticks, fmt_x = time_axis(span)
    return (alt.Chart(long).mark_line(point=span <= 31)
            .encode(x=alt.X("dzień:T", timeUnit="yearmonthdate", title=None,
                            axis=alt.Axis(format=fmt_x, tickCount=ticks, labelAngle=0)),
                    y=alt.Y("wartość:Q", title=y_title, scale=alt.Scale(zero=False)),
                    color=alt.Color("seria:N", title=None, legend=alt.Legend(orient="bottom")),
                    tooltip=[alt.Tooltip("dzień:T", format="%Y-%m-%d"), "seria:N", alt.Tooltip("wartość:Q", format=",.2f")]))

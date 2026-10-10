"""Dashboard market-signals (etap 4C) — tylko 127.0.0.1, bez telemetrii; uruchamia usługa launchd.

streamlit run src/dashboard/app.py  (konfiguracja: .streamlit/config.toml + argumenty w plist)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="market-signals", layout="wide")
HERE = Path(__file__).resolve().parent / "pages"
st.navigation([
    st.Page(str(HERE / "konto.py"), title="Moje konto", default=True),
    st.Page(str(HERE / "aktywa.py"), title="Karty moich aktywów"),
    st.Page(str(HERE / "pozostale.py"), title="Pozostałe aktywa"),
    st.Page(str(HERE / "zalecenia.py"), title="Zalecenia"),
    st.Page(str(HERE / "zlecenie.py"), title="Zlecenie na sucho"),
    st.Page(str(HERE / "stan.py"), title="Stan systemu"),
]).run()

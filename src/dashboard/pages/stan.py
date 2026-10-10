"""Stan systemu: wynik tools/health.sh."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from dashboard.common import header  # noqa: E402
from ms import views  # noqa: E402

header("Stan systemu")
h = views.system_health()
(st.success if h["ok"] else st.error)("Wszystko działa." if h["ok"] else "Są problemy — lista „PROBLEMY” poniżej.")
st.code(h["text"], language=None)

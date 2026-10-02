"""NHL Props dashboard - entrypoint and router (same scheme as NBA_tool).

Run:  make dashboard   (= streamlit run dashboard/app.py)

Page scripts live in dashboard/views/, NOT dashboard/pages/ (a pages/
folder next to the entrypoint makes Streamlit register it the old way
first; see NBA_tool dashboard/Prehled_modelu.py). Tipy dne = tips of the frozen
naive model (docs/tips_plan.md); marking a tip as bet comes next.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from dashboard import data
from dashboard.theme import ASSETS, ROUTER_FLAG, setup_page

setup_page("NHL Props", app=True)
st.session_state[ROUTER_FLAG] = True
st.logo(str(ASSETS / "logo.svg"), size="large")

PAGES = Path(__file__).resolve().parent / "views"

with st.sidebar:
    age = data.age_hours()
    if age is None:
        meta = '<span class="dot stale">●</span> databáze chybí'
    else:
        meta = (f'<span class="dot{" stale" if age > 30 else ""}">●</span> '
                f"databáze stará {age:.0f} h")
    st.markdown(f'<div class="side-meta">Fáze 0 · výběr trhu<br>{meta}<br>'
                "🔒 jen pro čtení</div>", unsafe_allow_html=True)

st.navigation({
    "Sázení": [
        st.Page(str(PAGES / "0_Tipy_dne.py"), title="Tipy dne",
                icon=":material/sports_hockey:", default=True),
    ],
    "Projekt": [
        st.Page(str(PAGES / "1_Prehled.py"), title="Přehled",
                icon=":material/dashboard:", url_path="prehled"),
        st.Page(str(PAGES / "5_Kurzy.py"), title="Kurzy",
                icon=":material/receipt_long:", url_path="kurzy"),
    ],
    "Statistiky": [
        st.Page(str(PAGES / "2_Hrac.py"), title="Hráč",
                icon=":material/person_search:", url_path="hrac"),
        st.Page(str(PAGES / "3_Brankari.py"), title="Brankáři",
                icon=":material/shield:", url_path="brankari"),
        st.Page(str(PAGES / "4_Tymy.py"), title="Týmy",
                icon=":material/groups:", url_path="tymy"),
    ],
}).run()

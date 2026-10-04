"""NHL Props dashboard - entrypoint and router (same scheme as NBA_tool).

Run:  make dashboard   (= streamlit run dashboard/app.py)

Page scripts live in dashboard/views/, NOT dashboard/pages/ (a pages/
folder next to the entrypoint makes Streamlit register it the old way
first; see NBA_tool dashboard/Prehled_modelu.py). Tipy dne = tips of the frozen
naive model (docs/tips_plan.md). Hosted on Streamlit Community Cloud the app
asks for a password first and fetches the database from the private data
repository (docs/streamlit.md, src/dashboard/cloud.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from datetime import datetime, timezone

from dashboard import cloud, data
from dashboard.theme import ASSETS, ROUTER_FLAG, setup_page

setup_page("NHL Props", app=True)
cloud.gate()                 # hosted: nothing below renders without the password
cloud.hosted_setup()
db_state = cloud.ensure_db()
st.session_state[ROUTER_FLAG] = True
st.logo(str(ASSETS / "logo.svg"), size="large")

PAGES = Path(__file__).resolve().parent / "views"

if db_state["state"] == "error":
    st.warning(f"Databázi se nepodařilo stáhnout: {db_state['error']}")

with st.sidebar:
    age = data.age_hours()
    if db_state.get("uploaded_at"):      # hosted: age of the upload, not of the download
        up = datetime.fromisoformat(db_state["uploaded_at"])
        age = (datetime.now(timezone.utc) - up).total_seconds() / 3600
    if age is None:
        meta = '<span class="dot stale">●</span> databáze chybí'
    else:
        meta = (f'<span class="dot{" stale" if age > 30 else ""}">●</span> '
                f"databáze stará {age:.0f} h")
    st.markdown(f'<div class="side-meta">Fáze 0 · výběr trhu<br>{meta}<br>'
                "✎ tikety se zálohují na GitHub</div>", unsafe_allow_html=True)

from dashboard import nav

P = {
    "tipy": st.Page(str(PAGES / "0_Tipy_dne.py"), title="Tipy dne",
                    icon=":material/sports_hockey:", default=True),
    "sazky": st.Page(str(PAGES / "7_Moje_sazky.py"), title="Moje sázky",
                     icon=":material/confirmation_number:", url_path="moje-sazky"),
    # opened from a game card; hidden in the menu by CSS (assets/style.css)
    "rozbor": st.Page(str(PAGES / "6_Rozbor_zapasu.py"), title="Rozbor zápasu",
                      icon=":material/query_stats:", url_path="rozbor"),
}
nav.PAGES.update(P)

st.navigation({
    "Sázení": [P["tipy"], P["sazky"], P["rozbor"]],
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

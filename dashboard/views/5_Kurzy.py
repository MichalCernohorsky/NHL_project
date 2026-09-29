"""Odds collected by the live snapshots (morning 10:00 ET, closing puck
drop -10 min). Raw lines of the US books; Tipsport is not in The Odds API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import streamlit as st

from dashboard import data
from dashboard.hero import hero
from dashboard.theme import section, setup_page

setup_page("Kurzy")
if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()

days = data.odds_by_day()
quota = data.quota()
hero("Kurzy", "Americké knihy · ráno <b>16:00</b> CZ · closing 10 min před zápasem",
     kpi_label="kredity", kpi_value=quota["zbyva"] if quota else "—", scene="odds")
if days.empty:
    st.info("Zatím se nenasbíral žádný kurz. Sběr spouští `make odds-morning` "
            "a `make odds-closing` (nebo automatika, docs/automation.md).")
    st.stop()

section("Nasbíráno po dnech", "nespárováno = jméno z knihy se nenašlo v soupiskách")
st.dataframe(days, hide_index=True, use_container_width=True)

c1, c2 = st.columns(2)
day = c1.selectbox("Den (ET)", sorted(days["den"].unique(), reverse=True))
kinds = days[days["den"] == day]["snimek"].tolist()
kind = c2.selectbox("Snímek", kinds, format_func=lambda k: {"morning": "ranní",
                                                           "closing": "closing"}[k])
lines = data.odds_lines(day, kind)
market = st.selectbox("Trh", sorted(lines["trh"].unique()))
section(f"Lajny — {market}", "poslední snímek dne pro každý zápas")
st.dataframe(lines[lines["trh"] == market].drop(columns=["trh"]), hide_index=True,
             use_container_width=True)

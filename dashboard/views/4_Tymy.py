"""Teams: shots for / against per game (the context of every shots market),
goals, overtime games; one team game by game."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import plotly.graph_objects as go
import streamlit as st

from dashboard import data
from dashboard.hero import hero, logo_url
from dashboard.theme import COLORS, section, setup_page

setup_page("Týmy")
if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
seasons = data.seasons()
if not seasons:
    st.info("V databázi zatím nejsou odehrané zápasy.")
    st.stop()

season = st.selectbox("Sezóna", seasons)
t = data.team_table(season)
if t.empty:
    st.info("Pro tuto sezónu nejsou týmová data.")
    st.stop()
hero("Týmy", f"Sezóna <b>{season}</b> · {len(t)} týmů · nejvíc střel "
     f"<b>{t.iloc[0]['tym']}</b> ({t.iloc[0]['strely_pro']:.1f} na zápas)",
     kpi_label="střely / tým / zápas", kpi_value=f"{t['strely_pro'].mean():.1f}",
     kpi_cls="acc", scene="teams")

section("Střely pro a proti", "vpravo dole = hodně střílí a málo pouští")
fig = go.Figure()
fig.add_scatter(x=t["strely_pro"], y=t["strely_proti"], mode="markers+text",
                text=t["tym"], textposition="top center",
                marker=dict(size=11, color=COLORS["accent"]),
                hovertemplate="%{text}<br>pro %{x:.1f} · proti %{y:.1f}<extra></extra>")
fig.update_layout(height=420, xaxis_title="střely pro / zápas",
                  yaxis_title="střely proti / zápas")
fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig, use_container_width=True)

st.dataframe(t, hide_index=True, use_container_width=True,
             column_config={c: st.column_config.NumberColumn(format="%.2f")
                            for c in ("strely_pro", "strely_proti", "goly_pro", "goly_proti")})

abbr = st.selectbox("Tým", t["tym"].tolist())
g = data.team_games(abbr, season)
section(f"{abbr} po zápasech")
st.markdown(f'<img src="{logo_url(abbr, light=True)}" style="height:34px">', unsafe_allow_html=True)
fig2 = go.Figure()
fig2.add_scatter(x=g["datum"], y=g["strely_pro"], name="pro", mode="lines+markers",
                 line_color=COLORS["over"])
fig2.add_scatter(x=g["datum"], y=g["strely_proti"], name="proti", mode="lines+markers",
                 line_color=COLORS["under"])
fig2.update_layout(height=300)
st.plotly_chart(fig2, use_container_width=True)
st.dataframe(g.iloc[::-1], hide_index=True, use_container_width=True)

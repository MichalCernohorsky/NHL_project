"""Goalies: starts, saves per start (full game and 60 minutes), save %."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import plotly.graph_objects as go
import streamlit as st

from dashboard import data
from dashboard.hero import hero, logo_url
from dashboard.theme import COLORS, section, setup_page

setup_page("Brankáři")
if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
seasons = data.seasons()
if not seasons:
    st.info("V databázi zatím nejsou odehrané zápasy.")
    st.stop()

season = st.selectbox("Sezóna", seasons)
gl = data.goalies(season)
if gl.empty:
    st.info("V této sezóně zatím nechytal nikdo.")
    st.stop()
top = gl.iloc[0]
hero("Brankáři", f"Sezóna <b>{season}</b> · {len(gl)} brankářů · "
     f"nejvíc startů <b>{top['jmeno']}</b> ({int(top['startu'])})",
     kpi_label="zásahy / start (liga)",
     kpi_value=f"{(gl['zasahy_start'] * gl['startu']).sum() / gl['startu'].sum():.1f}",
     kpi_cls="acc", scene="goalie")

section("Přehled", "zásahy za 60 min = jak by počítal Tipsport")
st.dataframe(gl.drop(columns=["player_id"]), hide_index=True, use_container_width=True,
             column_config={
                 "zasahy_start": st.column_config.NumberColumn("zásahy / start", format="%.1f"),
                 "zasahy_60": st.column_config.NumberColumn("za 60 min", format="%.1f"),
                 "uspesnost": st.column_config.NumberColumn("úspěšnost", format="%.3f")})

starters = gl[gl["startu"] > 0]
pick = st.selectbox("Brankář", range(len(starters)),
                    format_func=lambda i: f"{starters.iloc[i]['jmeno']} · {starters.iloc[i]['tym']}")
row = starters.iloc[pick]
g = data.goalie_games(int(row["player_id"]), season)
g = g[g["start"] == 1]
section(f"{row['jmeno']} — zásahy v odchytaných startech")
st.markdown(f'<img src="{logo_url(row["tym"])}" style="height:34px">', unsafe_allow_html=True)
fig = go.Figure()
fig.add_bar(x=g["datum"], y=g["zasahy"], name="zásahy", marker_color=COLORS["accent"],
            customdata=g[["souper", "strely_proti", "obdrzene"]],
            hovertemplate="%{x} %{customdata[0]}<br>zásahy %{y} z %{customdata[1]}"
                          "<br>obdržené %{customdata[2]}<extra></extra>")
fig.update_layout(height=300)
st.plotly_chart(fig, use_container_width=True)
st.dataframe(g.iloc[::-1], hide_index=True, use_container_width=True)

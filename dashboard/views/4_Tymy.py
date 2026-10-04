"""Teams: shots for / against per game (the context of every shots market),
goals, overtime games; the same in 60 minutes (how Tipsport settles), shots
allowed to forwards / defensemen, penalty minutes; one team game by game
with over-the-line rates, home / away and back-to-back splits with their
95% intervals, and who shoots for the team. Descriptive (docs/tips_plan.md
section 11)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, describe
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

season = st.selectbox("Sezóna", seasons, index=data.default_season_index(seasons))
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

t60 = data.team_table_60(season)
if not t60.empty:
    section("Za 60 minut — jak počítá Tipsport",
            "střely bez prodloužení · komu soupeři tým pouští střely · trestné minuty hráčů na zápas")
    t60 = t60.assign(tempo=t60["strely_pro_60"] + t60["strely_proti_60"]) \
             .sort_values("strely_pro_60", ascending=False)
    cols60 = {"tym": "tým", "zapasu_60": "zápasů", "strely_pro_60": "střely pro",
              "strely_proti_60": "střely proti", "tempo": "tempo (pro + proti)",
              "pousti_utocnikum": "pouští útočníkům", "pousti_obrancum": "pouští obráncům",
              "tm": "trestné min", "tm_soupere": "trestné min soupeře",
              "hity": "hity", "bloky": "bloky"}
    st.dataframe(t60[list(cols60)].rename(columns=cols60), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in list(cols60.values())[2:]})
    st.caption("„Pouští útočníkům / obráncům“ = kolik střel za 60 minut na zápas proti týmu vyšle "
               "útočníci a obránci soupeře. Trestné minuty jsou součet hráčů v poli (bez trestů "
               "střídačky). Popis historie; model používá jen celkové střely povolené soupeřem.")

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

g60 = data.team_games_60(abbr, season)
if len(g60) >= 2:
    section(f"{abbr} · jak často přes lajnu (střely týmu za 60 minut)",
            "popis historie, ne predikce — model pro střely týmů zatím neexistuje")
    periods = [("celá sezóna", g60), ("posledních 20", g60.tail(20)), ("posledních 10", g60.tail(10))]
    lines = [23.5, 25.5, 27.5, 29.5, 31.5, 33.5]
    o1, o2 = st.columns(2)
    with o1:
        st.markdown("**Střely týmu**")
        st.dataframe(describe.over_table([(n, d["strely_pro_60"]) for n, d in periods], lines),
                     hide_index=True, use_container_width=True)
    with o2:
        st.markdown("**Střely soupeře**")
        st.dataframe(describe.over_table([(n, d["strely_proti_60"]) for n, d in periods], lines),
                     hide_index=True, use_container_width=True)

if len(g60) >= 4:
    section(f"{abbr} · doma × venku, den po zápase", "za 60 minut · popis historie")
    parts = []
    for col, name in (("strely_pro_60", "střely týmu"), ("strely_proti_60", "střely soupeře"),
                      ("tm", "trestné minuty")):
        sp = describe.split_table(g60, col, [("doma", "doma", "venku"),
                                             ("b2b", "den po zápase", "s odpočinkem")])
        if not sp.empty:
            parts.append(sp.assign(co=name))
    if parts:
        sp = pd.concat(parts)[["co", "srovnání", "první", "druhá", "rozdíl",
                               "95% interval rozdílu", "čtení"]]
        st.dataframe(sp.rename(columns={"první": "první skupina", "druhá": "druhá skupina"}),
                     hide_index=True, use_container_width=True)
        st.caption("Když 95% interval rozdílu obsahuje nulu, rozdíl je v rámci náhody. Šest "
                   "srovnání najednou: i bez skutečného rozdílu občas jedno vyjde „větší než "
                   "náhoda“ jen shodou okolností.")

sh = data.team_shooters(abbr, season)
if not sh.empty:
    section(f"{abbr} · kdo střílí", "hráči podle střel za 60 minut na zápas")
    team_total = sh["strely_60"].mul(sh["zapasu"]).sum()
    sh = sh.assign(podil=sh["strely_60"] * sh["zapasu"] / team_total * 100 if team_total else None)
    st.dataframe(sh.head(15).rename(columns={
        "hrac": "hráč", "pozice": "pozice", "zapasu": "zápasů", "strely_60": "střely za 60 min",
        "toi": "TOI", "pp_toi": "PP TOI", "na_60_ledu": "na 60 min ledu", "goly": "góly",
        "podil": "podíl střel týmu %"}), hide_index=True, use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%.2f")
                       for c in ("střely za 60 min", "na 60 min ledu")}
        | {c: st.column_config.NumberColumn(format="%.1f")
           for c in ("TOI", "PP TOI", "podíl střel týmu %")})

if not g60.empty:
    section(f"{abbr} · zápasy za 60 minut")
    st.dataframe(g60.assign(doma=g60["doma"].map({1: "doma", 0: "venku"}),
                            b2b=g60["b2b"].map({1: "ano", 0: ""})).iloc[::-1].rename(columns={
        "souper": "soupeř", "b2b": "den po zápase", "strely_pro_60": "střely pro",
        "strely_proti_60": "střely proti", "pousti_utocnikum": "pouští útočníkům",
        "pousti_obrancum": "pouští obráncům", "tm": "trestné min",
        "tm_soupere": "trestné min soupeře"}), hide_index=True, use_container_width=True)

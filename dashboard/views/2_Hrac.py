"""Player: shots on goal game by game (60 minutes vs overtime), time on
ice and power play, and how often the player went over the usual lines.
Descriptive - no model here yet (phase 0)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data
from dashboard.hero import hero, logo_url
from dashboard.theme import COLORS, pill_row, section, setup_page, stat_pill

setup_page("Hráč")
if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
seasons = data.seasons()
if not seasons:
    st.info("V databázi zatím nejsou odehrané zápasy.")
    st.stop()

c1, c2 = st.columns([1, 3])
season = c1.selectbox("Sezóna", seasons)
sk = data.skaters(season, min_games=1)
if sk.empty:
    st.info("V této sezóně zatím nikdo nehrál.")
    st.stop()
labels = [f"{r.jmeno} · {r.tym} · {r.pozice}" for r in sk.itertuples()]
pick = c2.selectbox("Hráč (řazeno podle střel na zápas)", range(len(sk)),
                    format_func=lambda i: labels[i])
p = sk.iloc[pick]
g = data.player_games(int(p["player_id"]), season)


def f(v, d=1):
    return "—" if v is None or pd.isna(v) else f"{v:.{d}f}"


n60 = int(g["strely_60"].notna().sum())
has60 = n60 == len(g) and len(g) > 0     # 60-min numbers only when complete
hero(p["jmeno"],
     f"<b>{p['tym']}</b> · {p['pozice']} · sezóna <b>{season}</b> · "
     f"{len(g)} zápasů · čas na ledě {f(g['toi'].mean())} min",
     kpi_label="střely za 60 min / zápas" if has60 else "střely / zápas",
     kpi_value=f(g["strely_60"].mean() if has60 else g["strely"].mean(), 2),
     kpi_cls="acc", scene="player", logo_url=logo_url(p["tym"]))

last10 = g.tail(10)
st.markdown(pill_row([
    stat_pill("střely / zápas", f(g["strely"].mean(), 2), "vč. prodloužení"),
    stat_pill("za 60 min", f(g["strely_60"].mean(), 2),
              "jak počítá Tipsport" if has60 else f"jen {n60} z {len(g)} zápasů"),
    stat_pill("posledních 10", f(last10["strely_60" if has60 else "strely"].mean(), 2)),
    stat_pill("čas na ledě", f(g["toi"].mean()), "min / zápas"),
    stat_pill("přesilovka", f(g["pp_toi"].mean(), 2), "min / zápas"),
    stat_pill("bloky", f(g["bloky"].mean(), 2), "/ zápas"),
    stat_pill("body", f(g["body"].mean(), 2), "/ zápas"),
]), unsafe_allow_html=True)

if not has60:
    st.warning(f"Střely za 60 minut jsou načtené jen u {n60} z {len(g)} zápasů "
               "(play-by-play se ještě stahuje). Čísla níže jsou proto za celý zápas "
               "včetně prodloužení.")

section("Střely na branku po zápasech",
        "sloupec = za 60 minut, světlá čepička = navíc v prodloužení · čáry = lajny 1,5 / 2,5 / 3,5")
reg = g["strely_60"].fillna(g["strely"])
ot = (g["strely"] - reg).clip(lower=0)
fig = go.Figure()
fig.add_bar(x=g["datum"], y=reg, name="za 60 min", marker_color=COLORS["accent"],
            customdata=g[["souper", "toi", "pp_toi"]],
            hovertemplate="%{x} %{customdata[0]}<br>střely 60 min: %{y}"
                          "<br>TOI %{customdata[1]:.1f} · PP %{customdata[2]:.1f} min<extra></extra>")
fig.add_bar(x=g["datum"], y=ot, name="prodloužení", marker_color=COLORS["baseline"])
for line in (1.5, 2.5, 3.5):
    fig.add_hline(y=line, line_dash="dot", line_color=COLORS["muted"], opacity=.6)
fig.update_layout(barmode="stack", height=320, bargap=.25)
st.plotly_chart(fig, use_container_width=True)

section("Jak často přes lajnu" + (" (za 60 minut)" if has60 else " (celý zápas)"),
        "popis historie, ne predikce - model zatím neexistuje")
col = "strely_60" if has60 else "strely"
rows = []
for name, part in (("celá sezóna", g), ("posledních 20", g.tail(20)),
                   ("posledních 10", g.tail(10))):
    v = part[col].dropna()
    rows.append({"období": name, "zápasů": len(v),
                 **{f"přes {line}": f"{(v > line).mean() * 100:.0f} %" if len(v) else "—"
                    for line in (0.5, 1.5, 2.5, 3.5, 4.5)}})
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

section("Zápasy")
st.dataframe(g.drop(columns=["game_id"]).iloc[::-1], hide_index=True,
             use_container_width=True,
             column_config={"toi": st.column_config.NumberColumn("TOI", format="%.1f"),
                            "pp_toi": st.column_config.NumberColumn("PP TOI", format="%.1f"),
                            "ot_toi": st.column_config.NumberColumn("OT TOI", format="%.1f")})

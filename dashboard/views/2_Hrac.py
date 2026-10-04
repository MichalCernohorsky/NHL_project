"""Player: shots on goal game by game (60 minutes vs overtime), time on
ice and power play, how often the player went over the usual lines, his
role over time (shots per 60 minutes of ice, share of the team's shots),
seasons side by side, home / away and back-to-back splits with their 95%
intervals, and the model's tips on him. Descriptive (docs/tips_plan.md
section 11): the model uses only shooting rate, ice time and opponent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, describe
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
season = c1.selectbox("Sezóna", seasons, index=data.default_season_index(seasons))
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
c60 = g.dropna(subset=["strely_60"])                 # games with 60-minute counts
ice = c60["toi_60"].sum()
rate_60 = c60["strely_60"].sum() / ice * 60 if ice else None
team_s = c60["tym_strely_60"].sum()
share = c60["strely_60"].sum() / team_s if team_s else None
st.markdown(pill_row([
    stat_pill("střely / zápas", f(g["strely"].mean(), 2), "vč. prodloužení"),
    stat_pill("za 60 min", f(g["strely_60"].mean(), 2),
              "jak počítá Tipsport" if has60 else f"jen {n60} z {len(g)} zápasů"),
    stat_pill("posledních 10", f(last10["strely_60" if has60 else "strely"].mean(), 2)),
    stat_pill("čas na ledě", f(g["toi"].mean()), "min / zápas"),
    stat_pill("přesilovka", f(g["pp_toi"].mean(), 2), "min / zápas"),
    stat_pill("na 60 min ledu", f(rate_60, 2), "střel · vstup modelu"),
    stat_pill("podíl střel týmu", "—" if share is None else f"{share * 100:.0f} %", "za 60 minut"),
    stat_pill("góly", str(int(g["goly"].sum())),
              "—" if not g["strely"].sum() else f"úspěšnost {g['goly'].sum() / g['strely'].sum() * 100:.1f} %"),
    stat_pill("body", f(g["body"].mean(), 2), "/ zápas"),
    stat_pill("bloky", f(g["bloky"].mean(), 2), "/ zápas"),
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
        "popis historie, ne predikce modelu")
col = "strely_60" if has60 else "strely"
rows = []
for name, part in (("celá sezóna", g), ("posledních 20", g.tail(20)),
                   ("posledních 10", g.tail(10))):
    v = part[col].dropna()
    rows.append({"období": name, "zápasů": len(v),
                 **{f"přes {line}": f"{(v > line).mean() * 100:.0f} %" if len(v) else "—"
                    for line in (0.5, 1.5, 2.5, 3.5, 4.5)}})
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# ------------------------------------------------------------- role over time
if len(c60) >= 5:
    section("Role v čase", "klouzavý průměr 10 zápasů · střely na 60 minut ledu = vstup modelu, "
            "čas na ledě = druhý vstup")
    w = min(10, len(c60))
    roll_rate = c60["strely_60"].rolling(w, min_periods=3).sum() \
        / c60["toi_60"].rolling(w, min_periods=3).sum() * 60
    roll_toi = c60["toi_60"].rolling(w, min_periods=3).mean()
    roll_share = c60["strely_60"].rolling(w, min_periods=3).sum() \
        / c60["tym_strely_60"].rolling(w, min_periods=3).sum() * 100
    figr = go.Figure()
    figr.add_scatter(x=c60["datum"], y=roll_rate, name="střely na 60 min ledu",
                     line_color=COLORS["accent"],
                     hovertemplate="%{x}: %{y:.2f} na 60 min ledu<extra></extra>")
    figr.add_scatter(x=c60["datum"], y=roll_toi, name="čas na ledě (min)", yaxis="y2",
                     line=dict(color="#D9822B", dash="dot"),
                     hovertemplate="%{x}: %{y:.1f} min<extra></extra>")
    figr.update_layout(height=300, yaxis=dict(title="střely na 60 min ledu"),
                       yaxis2=dict(title="minuty", overlaying="y", side="right", showgrid=False,
                                   tickformat=".0f", dtick=1))
    st.plotly_chart(figr, use_container_width=True)
    last_share = roll_share.dropna()
    if not last_share.empty:
        st.caption(f"Podíl na střelách týmu za 60 minut: posledních {w} zápasů "
                   f"{last_share.iloc[-1]:.0f} %, celá sezóna {share * 100:.0f} %. "
                   "Skok v čase na ledě nebo v podílu obvykle znamená změnu role (jiná lajna, přesilovka).")

# ------------------------------------------------------------- seasons side by side
ps = data.player_seasons(int(p["player_id"]))
if not ps.empty:
    section("Sezóny vedle sebe", "model bere loňskou sezónu jako výchozí bod a letošní k ní přidává")
    st.dataframe(ps.rename(columns={
        "sezona": "sezóna", "zapasu": "zápasů", "strely_60": "střely za 60 min", "toi": "TOI",
        "pp_toi": "PP TOI", "na_60_ledu": "na 60 min ledu", "goly": "góly", "asistence": "asistence",
        "body": "body", "uspesnost": "úspěšnost %", "bloky": "bloky / z.", "hity": "hity / z.",
        "tm": "trestné min"}), hide_index=True, use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%.2f") for c in
                       ("střely za 60 min", "na 60 min ledu", "bloky / z.", "hity / z.")}
        | {c: st.column_config.NumberColumn(format="%.1f") for c in ("TOI", "PP TOI", "úspěšnost %")})

# ------------------------------------------------------------- splits with intervals
if len(c60) >= 4:
    section("Doma × venku, den po zápase", "střely za 60 minut · popis historie, model to nepoužívá")
    sp = describe.split_table(c60, "strely_60", [("doma", "doma", "venku"),
                                                 ("b2b", "den po zápase", "s odpočinkem")])
    if not sp.empty:
        st.dataframe(sp.rename(columns={"první": "první skupina", "druhá": "druhá skupina"}),
                     hide_index=True, use_container_width=True)
        st.caption("95% interval rozdílu říká, jak moc může rozdíl kolísat jen náhodou. Když obsahuje "
                   "nulu, čtení je „v rámci náhody“. I „větší než náhoda“ je jen popis jedné sezóny: "
                   "u každého dvacátého hráče tak vyjde rozdíl, který ve skutečnosti neexistuje. "
                   "Model tato rozdělení nepoužívá a tipy se podle nich nevyhodnocují.")

# ------------------------------------------------------------- the model's tips on him
pt = data.player_tips(int(p["player_id"]))
if not pt.empty:
    section("Tipy modelu na hráče", "jen výpis, bez bilance — bilance jednoho hráče je šum")
    pt = pt.assign(
        tip=[f"{'⭐ ' if t.arm_top else ''}{'více' if t.side == 'over' else 'méně'} než "
             f"{str(t.line).replace('.', ',')}" for t in pt.itertuples()],
        vysledek=pt["outcome"].map({"win": "✅", "loss": "❌", "void": "nehrál"}).fillna("čeká"),
        actual_60=["–" if pd.isna(v) else str(int(v)) for v in pt["actual_60"]])
    for c in ("p_model", "p_market", "edge"):
        pt[c] = pt[c] * 100
    st.dataframe(pt[["datum", "souper", "tip", "p_model", "p_market", "edge", "actual_60", "vysledek"]]
                 .rename(columns={"souper": "soupeř", "p_model": "p modelu %", "p_market": "p trhu %",
                                  "edge": "hrana p.b.", "actual_60": "střel za 60 min",
                                  "vysledek": "výsledek"}),
                 hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.1f")
                                for c in ("p modelu %", "p trhu %", "hrana p.b.")})

section("Zápasy")
g = g.drop(columns=["toi_60", "tym_strely_60"]).assign(
    doma=g["doma"].map({1: "doma", 0: "venku"}), b2b=g["b2b"].map({1: "ano", 0: ""}))
st.dataframe(g.drop(columns=["game_id"]).iloc[::-1], hide_index=True,
             use_container_width=True,
             column_config={"toi": st.column_config.NumberColumn("TOI", format="%.1f"),
                            "pp_toi": st.column_config.NumberColumn("PP TOI", format="%.1f"),
                            "ot_toi": st.column_config.NumberColumn("OT TOI", format="%.1f")})

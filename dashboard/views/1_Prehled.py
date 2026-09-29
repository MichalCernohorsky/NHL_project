"""Overview: where phase 0 stands, what data we hold, today's games,
odds collected and the last known credit balance."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import streamlit as st

from dashboard import data, phase0
from dashboard.hero import hero, ticker
from dashboard.theme import badge, metric_card, section, setup_page

setup_page("Přehled")
if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není - spusť python scripts/migrate.py.")
    st.stop()

CZ, ET = ZoneInfo("Europe/Prague"), ZoneInfo("America/New_York")
today_et = datetime.now(ET).date().isoformat()
games = data.games_on(today_et)


def cz_time(iso):
    return pd.Timestamp(iso).tz_convert(CZ).strftime("%H:%M") if iso else "?"


rows = [{"cas": cz_time(g.start_time_utc), "a_ab": g.a_ab, "h_ab": g.h_ab,
         "score": (f"{g.away_score}:{g.home_score}" if g.game_state in ("OFF", "FINAL")
                   else None)} for g in games.itertuples()]
done = sum(1 for k in phase0.CRITERIA if k[3] == "ok")
hero("Přehled",
     f"Sezóna <b>{data.live_season()}</b> · fáze 0: výběr trhu · "
     f"dnes ({today_et} ET) <b>{len(games)}</b> zápasů · stav k {phase0.UPDATED}",
     kpi_label="kritéria splněna", kpi_value=f"{done} / {len(phase0.CRITERIA)}",
     kpi_cls="acc", scene="rink", ticker_html=ticker(rows))

cov = data.coverage()
live = cov[cov["sezona"] == data.live_season()]
quota = data.quota()
odds = data.odds_by_day()
c1, c2, c3, c4 = st.columns(4)
c1.markdown(metric_card("odehráno v sezóně",
                        f"{int(live['odehrano'].iloc[0]) if len(live) else 0}",
                        footnote=f"z {int(live['zapasu'].iloc[0]) if len(live) else 0} zápasů"),
            unsafe_allow_html=True)
c2.markdown(metric_card("historie v DB", f"{int(cov['box_score'].sum()):,}".replace(",", " "),
                        footnote="zápasů s box score"), unsafe_allow_html=True)
c3.markdown(metric_card("živé kurzy", f"{int(odds['radku'].sum()) if len(odds) else 0}",
                        footnote=f"řádků za {odds['den'].nunique() if len(odds) else 0} dnů"),
            unsafe_allow_html=True)
c4.markdown(metric_card("kredity The Odds API", quota["zbyva"] if quota else "—",
                        footnote=(f"poslední dotaz {quota['cas'][:16].replace('T', ' ')} UTC"
                                  if quota else "zatím žádný dotaz")),
            unsafe_allow_html=True)

section("Fáze 0 — kritéria výběru trhu",
        "plán: docs/market_discovery_plan.md · stav se zapisuje ručně po důkazu")
KIND = {"ok": ("splněno", "over"), "progress": ("probíhá", "warn"),
        "wait": ("čeká", "neutral"), "fail": ("nesplněno", "under")}
html_rows = "".join(
    f"<tr><td><b>{k}</b></td><td>{name}</td><td>{badge(*KIND[state])}</td><td>{text}</td></tr>"
    for k, name, text, state in phase0.CRITERIA)
st.markdown(f'<table class="plain-table"><tr><th></th><th>kritérium</th><th>stav</th>'
            f"<th>poznámka</th></tr>{html_rows}</table>", unsafe_allow_html=True)
st.caption(f"Marže Tipsportu u střel hráče: {phase0.TIPSPORT_MARGIN}. "
           "Tipsport vyhodnocuje střely za 60 minut bez prodloužení (dodatek D3).")

section("Data v databázi", "základní část · prodloužení = OT i nájezdy")
st.dataframe(cov.rename(columns={"sezona": "sezóna", "zapasu": "zápasů",
                                 "odehrano": "odehráno", "prodlouzeni": "prodloužení",
                                 "box_score": "box score", "s_pp_toi": "s PP TOI",
                                 "strely_60": "střely za 60 min"}),
             hide_index=True, use_container_width=True)

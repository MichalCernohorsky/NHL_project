"""Moje sázky - the real tickets (MLB 'Moje sázky' layout): balance cards,
the queue of tips confirmed with ✅ Vsazeno waiting for their ticket (line,
book, price, stake), and the log of all tickets with results. Tickets
settle at their own line and price over 60 minutes; everything locks at
puck drop (dashboard.bets, in code)."""
import html
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import streamlit as st

from dashboard import bets, data, nav
from dashboard.hero import hero
from dashboard.theme import section, setup_page
from nhl_tool import naive_sog as ns
from nhl_tool import tips as tipmod

setup_page("Moje sázky")
CZ = ZoneInfo("Europe/Prague")
BOOKS = ["Tipsport", "Chance", "Betano", "Fortuna", "jiná"]

if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
if not st.session_state.get("_bets_pulled"):
    bets.sync_pull()
    st.session_state["_bets_pulled"] = True


def cz(x, d=1):
    return "–" if x is None or pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def side_cz(side):
    return "Více" if side == "over" else "Méně"


def kpi(tag, big, rows, cls=""):
    cells = "".join(f"<span>{r}</span>" for r in rows)
    return (f'<div class="kpi"><span class="tag">{tag}</span>'
            f'<span class="big{cls}">{big}</span><div class="row">{cells}</div></div>')


# ------------------------------------------------------------- settle tickets
mine = bets.player_bets()
rows = []
for b in mine:
    f = data.bet_facts(b["game_id"], b["player_id"])
    if f.get("final"):
        outcome, profit = bets.settle(b, f["actual"], f["played"])
    else:
        outcome, profit = "pending", 0.0
    rows.append({**b, **{k: f.get(k) for k in ("zapas", "final", "actual")},
                 "outcome": outcome, "profit": profit})
log = pd.DataFrame(rows)
done = log[log["outcome"].isin(["win", "loss"])] if not log.empty else log
staked = float(done["stake"].sum()) if not done.empty else 0.0
profit = float(done["profit"].sum()) if not done.empty else 0.0
pending = int((log["outcome"] == "pending").sum()) if not log.empty else 0

hero("Moje sázky", f"Skutečné tikety · vyhodnocení za lajnu a kurz z tiketu, střely za 60 minut · "
     f"<b>{len(mine)}</b> tiketů",
     kpi_label="bilance", kpi_value=(f"{'+' if profit > 0 else ''}{cz(profit, 0)} Kč" if len(done) else "–"),
     kpi_cls="up" if profit > 0 else "dn" if profit < 0 else "", scene="odds")
if bets.unsynced():
    st.warning("Poslední zápis se nepodařilo zálohovat na GitHub — je uložený v tomto počítači "
               "a odešle se při dalším zápisu.")

roi = profit / staked * 100 if staked else None
st.markdown('<div class="kpis">' + "".join([
    kpi("Bilance", f"{'+' if profit > 0 else ''}{cz(profit, 0)} Kč" if len(done) else "–",
        [f"vsazeno <b>{cz(staked, 0)} Kč</b>"], " up" if profit > 0 else " dn" if profit < 0 else ""),
    kpi("ROI", f"{'+' if (roi or 0) > 0 else ''}{cz(roi)} %" if roi is not None else "–",
        [f"<b>{len(done)}</b> vyhodnocených tiketů"],
        " up" if (roi or 0) > 0 else " dn" if (roi or 0) < 0 else ""),
    kpi("Výhry", f"{int((done['outcome'] == 'win').sum())} / {len(done)}" if len(done) else "–",
        [f"průměrný kurz <b>{cz(done['price'].mean(), 2)}</b>" if len(done) else "zatím nic"]),
    kpi("Čeká na výsledek", str(pending), ["vyhodnotí se po nočním běhu"]),
]) + "</div>", unsafe_allow_html=True)

# ------------------------------------------------------------- queue
decisions = bets.current_decisions()
have = {b.get("tip_id") for b in mine}
todo_ids = [tid for tid, d in decisions.items() if d["decision"] == "bet" and tid not in have]
queue = data.tips_by_ids(todo_ids)
if not queue.empty:
    queue = queue[~queue["start_time_utc"].map(bets.started)].sort_values("start_time_utc")

section("Potvrzené tipy ke vsazení", "označené ✅ Vsazeno v Rozboru zápasu · zapiš, co je na tiketu")
if queue.empty:
    st.caption("Nic nečeká. Tip potvrdíš v Rozboru zápasu (z karty na stránce Tipy dne).")
model = tipmod.load_model()
for r in queue.itertuples():
    with st.container(border=True):
        start = pd.Timestamp(r.start_time_utc).tz_convert(CZ).strftime("%-d. %-m. %H:%M")
        st.markdown(f"**{html.escape(str(r.player_name))}** ({r.tym} – {r.souper}) · tip "
                    f"**{side_cz(r.side)} {cz(r.line)}** · min. kurz **{cz(r.tipsport_min_price, 2)}** "
                    f"· začátek {start}" + (" · ⭐ TOP" if r.arm_top else ""))
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1.3, 1, 1.2])
        line = c1.number_input("Lajna u sázkovky", value=float(r.line), step=1.0, format="%.1f",
                               key=f"ln_{r.tip_id}")
        side = c2.selectbox("Strana", ["over", "under"], index=0 if r.side == "over" else 1,
                            format_func=side_cz, key=f"sd_{r.tip_id}")
        book = c3.selectbox("Sázkovka", BOOKS, key=f"bk_{r.tip_id}")
        price = c4.number_input("Kurz u sázkovky", min_value=1.01, value=1.85, step=0.01,
                                key=f"pr_{r.tip_id}")
        stake = c5.number_input("Vklad (Kč)", min_value=1.0,
                                value=float(st.session_state.get("_last_stake", 200.0)), step=50.0,
                                key=f"st_{r.tip_id}")
        p_over = float(ns.p_over(r.mu_60, line, model["nb_k"])[0])
        p_mod = p_over if side == "over" else 1 - p_over
        edge = p_mod - 1 / price
        ok = edge >= tipmod.EDGE_MIN
        mp = tipmod.min_price(p_mod)
        st.markdown(("✅ **SÁZEJ**" if ok else "❌ **NESÁZEJ**")
                    + f" — model {cz(p_mod * 100)} %, kurz tvrdí {cz(100 / price)} %, hrana "
                    f"{'+' if edge >= 0 else ''}{cz(edge * 100)} p.b., očekávaný zisk "
                    f"{'+' if p_mod * price - 1 >= 0 else ''}{cz((p_mod * price - 1) * 100)} %"
                    + (f" · min. kurz pro tuhle lajnu {cz(mp, 2)}" if mp else ""))
        b1, b2, _ = st.columns([1.4, 1.4, 3])
        tipd = {"tip_id": r.tip_id, "game_id": int(r.game_id), "game_date": r.game_date,
                "start_time_utc": r.start_time_utc, "player_id": int(r.player_id),
                "player_name": r.player_name, "side": r.side}
        if b1.button("💾 Uložit vsazenou sázku", key=f"sv_{r.tip_id}", type="primary"):
            try:
                bets.save_bet(tipd, line, price, stake, book, side=side)
                st.session_state["_last_stake"] = stake
            except (bets.Locked, ValueError) as exc:
                st.error(str(exc))
            st.rerun()
        if b2.button("✖ Zrušit — nevsazeno", key=f"cx_{r.tip_id}"):
            try:
                bets.decide(tipd, "no")
            except bets.Locked as exc:
                st.error(str(exc))
            st.rerun()

# ------------------------------------------------------------- log
section("Všechny tikety", "nejnovější nahoře · smazat jde jen do začátku zápasu")
if log.empty:
    st.caption("Zatím žádný tiket.")
else:
    ICON = {"win": "✅ výhra", "loss": "❌ prohra", "void": "↩ vráceno", "push": "↩ push",
            "pending": "⏳ čeká"}
    for b in log.sort_values("ts", ascending=False).to_dict("records"):
        c = st.columns([1.0, 1.3, 2.6, 0.8, 0.9, 1.5, 1.0, 1.3])
        c[0].markdown(b.get("game_date") or "")
        c[1].markdown(b.get("zapas") or "")
        c[2].markdown(f"**{html.escape(str(b['player_name']))}** · {side_cz(b['side'])} {cz(b['line'])}")
        c[3].markdown(f"@ **{cz(b['price'], 2)}**")
        c[4].markdown(f"{cz(b['stake'], 0)} Kč")
        res = ICON[b["outcome"]] + ("" if b.get("actual") is None else f" · {b['actual']} střel")
        c[5].markdown(res)
        c[6].markdown("" if b["outcome"] == "pending" else
                      f"**{'+' if b['profit'] > 0 else ''}{cz(b['profit'], 0)} Kč**")
        if not bets.started(b.get("start_time_utc")):
            if c[7].button("✖ Smazat", key=f"del_{b['id']}", help="Překlep nebo nakonec nevsazeno"):
                try:
                    bets.delete_bet(b)
                except bets.Locked as exc:
                    st.error(str(exc))
                st.rerun()
        else:
            c[7].markdown(f"<span style='color:#8b8f9e;font-size:12px'>🔒 {b['book']}</span>",
                          unsafe_allow_html=True)

if st.button("← Tipy dne", type="tertiary"):
    nav.goto("tipy")

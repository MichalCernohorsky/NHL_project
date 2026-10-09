"""Rozbor zápasu - one game on one page, laid out like the MLB 'Schvalování'
one-pager: game header, tip rows with ✅ Vsazeno / ❌ Ne (locked at puck
drop, in code), then per tip: distribution + books + 'tip by vyšel',
why the model tips it (what lifts / lowers the prediction), trends, what
matters today, and a summary for the bettor. Opened from a game card on
Tipy dne; not in the sidebar menu.
"""
import html
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import bets, data, nav
from dashboard.hero import team_logo
from dashboard.theme import setup_page
from nhl_tool import explain
from nhl_tool import naive_sog as ns
from nhl_tool import tips as tipmod

setup_page("Rozbor zápasu")
CZ = ZoneInfo("Europe/Prague")
GREEN, GREEN_BG, GREEN_BD = "#1e7a46", "#e8f4ee", "#bfe0cf"
RED, RED_BG, RED_BD = "#b3403a", "#fbeceb", "#f0cbc7"
YELL, YELL_BG, YELL_BD = "#8a6a1f", "#fdf3e1", "#f3d9a6"
NAVY, NAVY_BG, NAVY_BD = "#2E5FB7", "#e9effa", "#c9d7f1"
MUTED, SEC, INK = "#8b8f9e", "#5a6572", "#0c1c33"

st.markdown("""
<style>
.mono{font-variant-numeric:tabular-nums}
.chip{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;
  font-size:12px;font-weight:650;white-space:nowrap;margin:0 4px 3px 0}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:#8b8f9e}
.krow{display:grid;grid-template-columns:170px 1fr;gap:10px;padding:6px 2px;
  border-top:1px dashed #e2e6ea;font-size:13.5px}
.krow:first-child{border-top:0}
.krow .kl{color:#5a6572}.krow .kv{color:#0c1c33;font-weight:600}
.krow .kv small{font-weight:400;color:#5a6572}
.ghdr{background:#fff;border:1px solid #e2e6ea;border-top:3px solid #2E5FB7;border-radius:14px;
  display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:16px 22px;margin-bottom:12px}
.ghdr .tm{font-size:22px;font-weight:800;color:#0c1c33}
.ghdr .tm img{height:40px;width:40px;vertical-align:-11px;margin-right:10px}
.ghdr .tm.home{text-align:right}.ghdr .tm.home img{margin:0 0 0 10px}
.ghdr .tm small{display:block;font-size:12px;font-weight:450;color:#5a6572}
.ghdr .mid{text-align:center;color:#5a6572;font-size:12px;line-height:1.5}
.ghdr .mid b{display:block;font-size:22px;color:#0c1c33}
.fact{padding:6px 2px;border-top:1px dashed #e2e6ea;font-size:13.5px;color:#0c1c33}
.fact:first-child{border-top:0}
.fact.w{background:#fdf3e1;border:1px solid #f3d9a6;border-radius:8px;padding:7px 10px;color:#7a5410;margin:4px 0}
.stub{display:inline-flex;gap:8px;padding:4px 10px;background:#e8f4ee;border:1px dashed #bfe0cf;
  border-radius:8px;font-size:12px;color:#1e7a46;margin-top:2px}
div[data-testid="stButton"] button{border-radius:8px;font-weight:650;white-space:nowrap;
  padding-left:8px;padding-right:8px}
div[data-testid="stButton"] button p{white-space:nowrap;font-size:13.5px}
</style>
""", unsafe_allow_html=True)


def chip(text, fg, bg, bd):
    return f'<span class="chip" style="background:{bg};border:1px solid {bd};color:{fg}">{text}</span>'


def cz(x, d=1):
    return "–" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def sgn(x, d=1):
    """Signed Czech number: +1,2 / −0,4."""
    return ("+" if x >= 0 else "−") + cz(abs(x), d)


def side_cz(side):
    return "Více" if side == "over" else "Méně"


def cz_time(iso):
    return pd.Timestamp(iso).tz_convert(CZ).strftime("%H:%M") if iso else "?"


def until(iso) -> str:
    left = (pd.Timestamp(iso) - pd.Timestamp.now(tz="UTC")).total_seconds()
    if left <= 0:
        return "zápas začal"
    h, m = int(left // 3600), int(left % 3600 // 60)
    return f"zámek za {h} h {m:02d} min" if h else f"zámek za {m} min"


def krows(rows):
    return "".join(f'<div class="krow"><span class="kl">{k}</span><span class="kv">{v}</span></div>'
                   for k, v in rows)


if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
if not st.session_state.get("_bets_pulled"):
    bets.sync_pull()
    st.session_state["_bets_pulled"] = True

# --------------------------------------------------------------- which game
gid = st.session_state.get("game_id") or st.query_params.get("game")
days = data.tip_days()
if gid is None:
    if not days:
        st.info("Zatím nejsou žádné tipy.")
        st.stop()
    first = data.games_on(days[0])
    gid = int(first["game_id"].iloc[0]) if not first.empty else None
g = data.game(int(gid)) if gid is not None else None
if g is None:
    st.info("Zápas nenalezen. Vrať se na Tipy dne.")
    st.stop()
gid, day = int(g["game_id"]), g["game_date"]
st.query_params["game"] = str(gid)
games = data.games_on(day)
order = games["game_id"].astype(int).tolist()
idx = order.index(gid) if gid in order else 0
all_tips = data.tips_on(day)
tips_g = (all_tips[(all_tips["game_id"] == gid) & (all_tips["playable"] == 1)]
          .sort_values(["arm_top", "edge"], ascending=False) if not all_tips.empty else all_tips)
locked = bets.started(g["start_time_utc"])
finished = g["game_state"] in ("OFF", "FINAL")
model = tipmod.load_model()
k = model["nb_k"]

if st.button("← Tipy dne", type="tertiary", key="back"):
    nav.goto("tipy")
if bets.unsynced():
    st.warning("Poslední zápis se nepodařilo zálohovat na GitHub — je uložený v tomto "
               "počítači a odešle se při dalším zápisu.")

# --------------------------------------------------------------- 1 · header
mid = (f'<b>{g["away_score"]} : {g["home_score"]}</b>konec' if finished
       else f'<b>{cz_time(g["start_time_utc"])}</b>čas CZ · {day}')
st.markdown(
    f'<div class="ghdr"><div class="tm">{team_logo(g["a_ab"], 40, light=True)}{g["a_ab"]}'
    f'<small>hosté · {html.escape(g["a_name"])}</small></div>'
    f'<div class="mid">{mid}<br>zápas {idx + 1} z {len(order)}'
    f'{"" if locked else " · 🔒 " + until(g["start_time_utc"])}</div>'
    f'<div class="tm home">{g["h_ab"]}{team_logo(g["h_ab"], 40, light=True)}'
    f'<small>domácí · {html.escape(g["h_name"])}</small></div></div>', unsafe_allow_html=True)

if tips_g.empty:
    st.info("K tomuto zápasu model nemá tip (žádný hráč nepřekročil hranu 3 p.b., "
            "nebo zatím chybí lajny amerických knih).")
else:
    # ----------------------------------------------------------- 2 · tip rows
    decisions = bets.current_decisions()
    mine = {b["tip_id"]: b for b in bets.player_bets() if b.get("tip_id")}
    W = [1.25, 2.2, 0.75, 1.15, 0.7, 1.35, 0.95, 1.65]
    for col, name in zip(st.columns(W), ["", "HRÁČ · STRANA · LAJNA", "MIN. KURZ",
                                         "MODEL / TRH", "HRANA", "", "", "STAV"]):
        col.markdown(f'<span class="lbl">{name}</span>', unsafe_allow_html=True)
    for r in tips_g.itertuples():
        dec = decisions.get(r.tip_id, {}).get("decision", "pending")
        tipd = {"tip_id": r.tip_id, "game_id": gid, "start_time_utc": g["start_time_utc"]}
        c = st.columns(W)
        chips = (chip("⭐ TOP", NAVY, NAVY_BG, NAVY_BD) if r.arm_top else "") + (
            chip("⚠ velká neshoda", YELL, YELL_BG, YELL_BD) if r.edge > tipmod.WARN_EDGE
            else chip("🟢 tip", GREEN, GREEN_BG, GREEN_BD))
        c[0].markdown(chips, unsafe_allow_html=True)
        stub = ""
        if r.tip_id in mine:
            b = mine[r.tip_id]
            stub = (f'<br><span class="stub">🎟️ <b>vsazeno</b> {side_cz(b["side"])} '
                    f'{cz(b["line"])} @ {cz(b["price"], 2)} · {cz(b["stake"], 0)} Kč</span>')
        c[1].markdown(f'<span style="font-size:15px;font-weight:750">{html.escape(str(r.player_name))}'
                      f'</span> <span style="color:{SEC}">{r.tym or ""} · <b>{side_cz(r.side)} '
                      f'{cz(r.line)}</b></span>{stub}', unsafe_allow_html=True)
        c[2].markdown(f'<span class="mono" style="font-size:17px;font-weight:700">'
                      f'{cz(r.tipsport_min_price, 2)}</span>', unsafe_allow_html=True)
        c[3].markdown(f'<b class="mono" style="font-size:15px">{r.p_model * 100:.0f} %</b> '
                      f'<span class="mono" style="color:{SEC}">/ {r.p_market * 100:.0f} %</span>',
                      unsafe_allow_html=True)
        c[4].markdown(f'<span class="mono" style="font-size:15px;font-weight:750;color:'
                      f'{YELL if r.edge > tipmod.WARN_EDGE else GREEN}">+{cz(r.edge * 100)}</span>',
                      unsafe_allow_html=True)
        if c[5].button("✅ Vsazeno" if dec != "bet" else "✅ ✓", key=f"ok_{r.tip_id}",
                       disabled=locked, type="primary" if dec == "bet" else "secondary",
                       use_container_width=True):
            try:      # a second click on the active choice takes it back
                bets.decide(tipd, "pending" if dec == "bet" else "bet")
            except bets.Locked as exc:
                st.error(str(exc))
            st.rerun()
        if c[6].button("❌ Ne" if dec != "no" else "❌ ✓", key=f"no_{r.tip_id}",
                       disabled=locked, type="primary" if dec == "no" else "secondary",
                       use_container_width=True):
            try:
                bets.decide(tipd, "pending" if dec == "no" else "no")
            except bets.Locked as exc:
                st.error(str(exc))
            st.rerun()
        if isinstance(r.outcome, str):
            txt = {"win": ("✅ vyšel", GREEN, GREEN_BG, GREEN_BD),
                   "loss": ("❌ nevyšel", RED, RED_BG, RED_BD),
                   "void": ("nehrál · vráceno", SEC, "#eef1f5", "#e2e6ea")}[r.outcome]
            shots = "" if pd.isna(r.actual_60) else f"{int(r.actual_60)} střel za 60 min"
            stav, sub = chip(*txt), shots + (" · vsazeno" if dec == "bet" else "")
        elif locked:
            stav = (chip("🔒 zamčeno · vsazeno", GREEN, GREEN_BG, GREEN_BD) if dec == "bet"
                    else chip("🔒 zamčeno · nevsazeno", SEC, "#eef1f5", "#e2e6ea"))
            sub = "zápas začal"
        elif dec == "bet":
            stav, sub = chip("🟩 vsazeno", GREEN, GREEN_BG, GREEN_BD), "tiket zapiš v Moje sázky"
        elif dec == "no":
            stav, sub = chip("🟥 nevsazeno", RED, RED_BG, RED_BD), "lze změnit do startu"
        else:
            stav, sub = chip("⏳ čeká na rozhodnutí", YELL, YELL_BG, YELL_BD), "🔒 " + until(g["start_time_utc"])
        c[7].markdown(f'{stav}<br><span style="font-size:11px;color:{MUTED}">{sub}</span>',
                      unsafe_allow_html=True)
    n_dec = sum(1 for r in tips_g.itertuples()
                if decisions.get(r.tip_id, {}).get("decision") in ("bet", "no"))
    st.markdown(
        f'<div style="font-size:12px;color:{MUTED};margin:4px 0 6px">Rozhodnutí lze měnit do '
        f'začátku zápasu, pak se zamkne. Nerozhodnuto = nevsazeno. Rozhodnuto {n_dec} z '
        f'{len(tips_g)}. <b>Min. kurz</b> = kurz u Tipsportu, od kterého tip splňuje pravidlo.</div>',
        unsafe_allow_html=True)
    if any(decisions.get(r.tip_id, {}).get("decision") == "bet" and r.tip_id not in mine
           for r in tips_g.itertuples()) and not locked:
        if st.button("🎟️ Zapsat tikety v Moje sázky →", type="primary"):
            nav.goto("sazky")

    # ------------------------------------------------- 3-7 · one tab per tip
    toi_pos = data.pos_avg_toi_min()
    tabs = st.tabs([f"{'⭐ ' if r.arm_top else ''}{r.player_name} · {side_cz(r.side)} {cz(r.line)}"
                    for r in tips_g.itertuples()])
    for tab, r in zip(tabs, tips_g.itertuples()):
        with tab:
            grp = r.pos_group if isinstance(r.pos_group, str) else "F"
            pmf = ns.nb_pmf_upto(r.mu_60, k, 14)[0]
            cdf = np.cumsum(pmf)
            q10, med, q90 = (int(np.searchsorted(cdf, p)) for p in (0.1, 0.5, 0.9))
            hist = data.player_shots_history(int(r.player_id), day)

            # --- 3 · distribution + books ----------------------------------
            left, right = st.columns([1.35, 1])
            with left:
                st.markdown('<div class="section-title">Rozdělení a lajna</div>', unsafe_allow_html=True)
                fig = go.Figure(go.Bar(
                    x=list(range(11)), y=pmf[:11],
                    marker_color=["rgba(46,95,183,.85)" if (x > r.line) == (r.side == "over")
                                  else "rgba(46,95,183,.30)" for x in range(11)],
                    hovertemplate="%{x} střel: %{y:.1%}<extra></extra>"))
                fig.add_vrect(x0=q10 - .5, x1=q90 + .5, fillcolor="rgba(46,95,183,.06)", line_width=0)
                fig.add_vline(x=float(r.line), line_color=NAVY, line_dash="dash",
                              annotation_text=f"lajna {cz(r.line)}", annotation_position="top left",
                              annotation_font=dict(color=NAVY, size=12))
                fig.add_vline(x=float(r.mu_60), line_color="#D9822B",
                              annotation_text=f"model čeká {cz(r.mu_60, 2)}",
                              annotation_position="top right",
                              annotation_font=dict(color="#D9822B", size=12))
                fig.update_layout(height=290, showlegend=False, bargap=.12,
                                  margin=dict(l=10, r=10, t=30, b=10))
                fig.update_yaxes(showticklabels=False, showgrid=False)
                fig.update_xaxes(dtick=1, title_text="střel na branku za 60 minut")
                st.plotly_chart(fig, use_container_width=True, key=f"dist_{r.tip_id}")
                st.caption("Tmavé sloupce = výsledky, při kterých tip vyjde. Pásmo = obvyklé "
                           f"rozpětí {q10}–{q90} střel (8 z 10 zápasů), čárkovaně lajna, "
                           "oranžově očekávání modelu.")
            with right:
                st.markdown('<div class="section-title">Kurzy amerických knih</div>',
                            unsafe_allow_html=True)
                tb = data.tip_books(gid, int(r.player_id), r.snapshot_kind, r.snapshot_time)
                if tb.empty:
                    st.caption("Lajny v databázi nejsou.")
                else:
                    col = "vice" if r.side == "over" else "mene"
                    p_side = [float(ns.p_over(r.mu_60, ln, k)[0]) for ln in tb["lajna"]]
                    tb["p modelu"] = [f"{100 * (p if r.side == 'over' else 1 - p):.0f} %" for p in p_side]
                    best = tb.loc[tb["lajna"] == r.line, col].max()
                    tb.insert(0, "⭐", np.where((tb["lajna"] == r.line) & (tb[col] == best), "⭐", ""))
                    st.dataframe(tb.rename(columns={"vice": "více", "mene": "méně"}), hide_index=True,
                                 use_container_width=True,
                                 column_config={"více": st.column_config.NumberColumn(format="%.2f"),
                                                "méně": st.column_config.NumberColumn(format="%.2f"),
                                                "lajna": st.column_config.NumberColumn(format="%.1f")})
                    st.caption("Americké knihy počítají i prodloužení, Tipsport jen 60 minut — "
                               "trh v řádku tipu je na 60 minut přepočtený. ⭐ = nejlepší kurz "
                               "na naši stranu a lajnu.")
                if not hist.empty:
                    hit = (hist["s"] > r.line) if r.side == "over" else (hist["s"] < r.line)
                    parts = []
                    for name, mask in (("posledních 10", hist.index < 10),
                                       ("letos", (hist["season"] == g["season"]).to_numpy()),
                                       ("loni", (hist["season"] == ns.prev_season(g["season"])).to_numpy())):
                        n = int(mask.sum())
                        if n:
                            parts.append(f"**{name}:** {int(hit[mask].sum())} z {n} "
                                         f"({100 * hit[mask].mean():.0f} %)")
                    st.markdown("**Tip by vyšel…** (na dnešní lajně, za 60 minut)  \n" + "  \n".join(parts))

            # --- 4 · why the model tips it ----------------------------------
            st.markdown('<div class="section-title">🧩 Proč model tipuje '
                        '<span class="hint">rozklad dnešní predikce, ne věštba</span></div>',
                        unsafe_allow_html=True)
            has_factors = r.f_rate_60 is not None and pd.notna(r.f_rate_60)
            if not has_factors:
                st.caption("Rozklad pro tento tip není uložený (starší záznam).")
            r_pos = model["prior_rate_per_s"][grp] * 3600
            t_pos = toi_pos.get(grp, 16.0)
            if has_factors:
                ex = explain.tip_contributions(
                    rate_60=r.f_rate_60, toi_min=r.f_toi_l10_min, opp_factor=r.f_opp_factor,
                    base_rate_60=r_pos, base_toi_min=t_pos, line=float(r.line), side=r.side, k=k)
                who = "obránce" if grp == "D" else "útočník"
                bet = f"{side_cz(r.side)} {cz(r.line)}"
                parts = [ex["p_parts"][f] * 100 for f in explain.FACTORS]
                a1, a2 = st.columns([1.15, 1.1])
                with a1:
                    figb = go.Figure(go.Waterfall(
                        x=[f"Průměrný<br>{who}", *[explain.LABELS[f] for f in explain.FACTORS],
                           "Model"],
                        measure=["absolute", "relative", "relative", "relative", "total"],
                        y=[ex["p_base"] * 100, *parts, 0],
                        text=[f"{cz(ex['p_base'] * 100)} %",
                              *[sgn(v) for v in parts],
                              f"{cz(ex['p'] * 100)} %"],
                        textposition="outside", cliponaxis=False,
                        increasing=dict(marker=dict(color=GREEN)),
                        decreasing=dict(marker=dict(color=RED)),
                        totals=dict(marker=dict(color=NAVY)),
                        connector=dict(line=dict(color="#c9d1dc", width=1)),
                        hovertemplate="%{x}: %{text}<extra></extra>"))
                    figb.add_hline(y=float(r.p_market) * 100, line_dash="dash", line_color="#D9822B",
                                   annotation_text=f"trh {cz(r.p_market * 100)} %",
                                   annotation_position="bottom right",
                                   annotation_font=dict(color="#D9822B", size=12),
                                   annotation_bgcolor="#ffffff", annotation_bordercolor="#D9822B",
                                   annotation_borderpad=2)
                    # zoom on the part of the scale where the steps happen
                    levels = [ex["p_base"] * 100, *(ex["p_base"] * 100 + np.cumsum(parts)),
                              float(r.p_market) * 100]
                    figb.update_layout(height=300, showlegend=False,
                                       margin=dict(l=10, r=10, t=24, b=10))
                    figb.update_yaxes(range=[max(0, min(levels) - 14), min(100, max(levels) + 9)],
                                      ticksuffix=" %", title_text=f"pravděpodobnost „{bet}“")
                    st.plotly_chart(figb, use_container_width=True, key=f"why_{r.tip_id}")
                    mp = ex["mu_parts"]
                    st.caption(
                        f"Čti zleva: průměrný {who} by sázku „{bet}“ trefil v "
                        f"{cz(ex['p_base'] * 100)} %. Zelená pravděpodobnost zvedá, červená sráží "
                        f"(v procentních bodech) → model **{cz(ex['p'] * 100)} %**, trh "
                        f"{cz(r.p_market * 100)} %, hrana **+{cz(r.edge * 100)} p.b.** "
                        f"Ve střelách: průměr {cz(ex['mu_base'], 2)} · střelba "
                        f"{sgn(mp['rate'], 2)} · led {sgn(mp['toi'], 2)} · soupeř "
                        f"{sgn(mp['opp'], 2)} → {cz(ex['mu'], 2)}. Rozklad říká, odkud se "
                        "číslo vzalo, ne že je správné.")
                with a2:
                    w_prior = 100 * 180 / (r.f_season_toi_min + 180)
                    base = "loňská sezóna" if (r.gp_prev or 0) >= ns.MIN_GP_PRIOR else "průměr pozice"
                    opp_txt = (f"{r.souper} letos pouští {cz(r.f_opp_mean)} střel za 60 min "
                               f"({int(r.f_opp_n)} z.), liga {cz(model['league_team_shots'])} → "
                               f"faktor {cz(r.f_opp_factor, 3)}" if r.f_opp_n else
                               f"{r.souper} letos ještě nehrál → faktor 1,000")
                    st.markdown(krows([
                        ("Střelba hráče", f"{cz(r.f_rate_60, 2)} střely na 60 min ledu<br><small>letos "
                         f"{cz(r.f_season_shots, 0)} střel za {cz(r.f_season_toi_min, 0)} min "
                         f"({int(r.gp_season or 0)} z.) · základ {cz(r.f_prior_60, 2)} ({base}) · "
                         f"váha základu {w_prior:.0f} %</small>"),
                        ("Čas na ledě", f"{cz(r.f_toi_l10_min)} min<br><small>průměr posledních 10 "
                         f"zápasů (bez prodloužení) · průměr pozice {cz(t_pos)} min</small>"),
                        ("Soupeř", f"faktor {cz(r.f_opp_factor, 3)}<br><small>{opp_txt}</small>"),
                        ("Výsledek", f"{cz(r.f_rate_60, 2)} ÷ 60 × {cz(r.f_toi_l10_min)} × "
                         f"{cz(r.f_opp_factor, 3)} = <b>{cz(r.mu_60, 2)} střely za 60 minut</b>"),
                    ]), unsafe_allow_html=True)

            # --- 5 · trends --------------------------------------------------
            rec = data.player_recent(int(r.player_id), day, 15)
            t1, t2 = st.columns(2)
            with t1:
                st.markdown('<div class="section-title">Střely · posledních 15 zápasů '
                            '<span class="hint">za 60 minut</span></div>', unsafe_allow_html=True)
                if rec.empty:
                    st.caption("Bez odehraných zápasů.")
                else:
                    good = (rec["strely_60"] > r.line) == (r.side == "over")
                    f1 = go.Figure(go.Bar(
                        x=list(range(len(rec))), y=rec["strely_60"],
                        marker_color=[NAVY if ok else "rgba(46,95,183,.30)" for ok in good],
                        customdata=rec[["datum", "souper"]],
                        hovertemplate="%{customdata[0]} %{customdata[1]}: %{y} střel<extra></extra>"))
                    f1.add_hline(y=float(r.line), line_dash="dash", line_color="#D9822B")
                    f1.update_layout(height=230, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
                    f1.update_xaxes(showticklabels=False, title_text="← starší · novější →")
                    st.plotly_chart(f1, use_container_width=True, key=f"tr_{r.tip_id}")
            with t2:
                st.markdown('<div class="section-title">Čas na ledě · posledních 15 zápasů '
                            '<span class="hint">minuty, z toho přesilovka</span></div>',
                            unsafe_allow_html=True)
                if not rec.empty:
                    f2 = go.Figure()
                    f2.add_scatter(x=list(range(len(rec))), y=rec["toi"], mode="lines+markers",
                                   line_color=NAVY, name="celkem",
                                   customdata=rec[["datum", "souper"]],
                                   hovertemplate="%{customdata[0]} %{customdata[1]}: %{y:.1f} min<extra></extra>")
                    f2.add_bar(x=list(range(len(rec))), y=rec["pp_toi"], marker_color="rgba(217,130,43,.55)",
                               name="přesilovka")
                    f2.update_layout(height=230, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
                    f2.update_xaxes(showticklabels=False, title_text="← starší · novější →")
                    st.plotly_chart(f2, use_container_width=True, key=f"toi_{r.tip_id}")

            # --- 6 · what matters today + 7 · summary -------------------------
            e1, e2 = st.columns(2)
            with e1:
                st.markdown('<div class="section-title">Co ovlivňuje dnešek</div>', unsafe_allow_html=True)
                home = int(r.team_id) == int(g["home_team_id"])
                facts = [("", "🏠 Hraje doma." if home else "✈️ Hraje venku.")]
                if data.played_previous_day(int(r.team_id), day):
                    facts.append(("", f"😴 {r.tym} hrál i včera (zápas den po zápase)."))
                if data.played_previous_day(int(r.opp_id), day):
                    facts.append(("", f"😴 Soupeř {r.souper} hrál i včera."))
                facts.append(("", "⏱️ Tipsport počítá jen 60 minut; v prodloužení padne "
                              f"{100 * model['ot_ratio'][grp]:.1f} % střel navíc — do tipu se nepočítají."))
                if (r.gp_season or 0) < ns.MIN_GP_SEASON:
                    facts.append(("w", f"📅 Letos jen {int(r.gp_season or 0)} zápasů — model stojí "
                                  "hlavně na minulé sezóně. Změna role, lajny nebo týmu v něm není."))
                if ns.MIN_GP_PRIOR <= (r.gp_prev or 0) < 60:
                    facts.append(("w", f"🩹 Loni jen {int(r.gp_prev)} zápasů — loňský základ může "
                                  "být zkreslený (zranění, jiná role)."))
                if pd.notna(r.loni_s60) and pd.notna(r.predloni_s60) and r.predloni_s60 > 0 \
                        and abs(r.loni_s60 / r.predloni_s60 - 1) > 0.25:
                    facts.append(("w", f"📉 Loni {cz(r.loni_s60, 2)} střely na zápas, předloni "
                                  f"{cz(r.predloni_s60, 2)} — velký rozdíl mezi sezónami; model "
                                  "vidí jen tu loňskou."))
                if r.edge > tipmod.WARN_EDGE:
                    facts.append(("w", f"⚠ Model se s trhem rozchází o {cz(r.edge * 100)} p.b. "
                                  "U takových tipů se v NBA nejčastěji mýlil model, ne trh."))
                st.markdown("".join(f'<div class="fact {c}">{t}</div>' for c, t in facts),
                            unsafe_allow_html=True)
            with e2:
                st.markdown('<div class="section-title">Shrnutí pro sázkaře</div>', unsafe_allow_html=True)
                with st.container(border=True):
                    top_c = chip("⭐ TOP", NAVY, NAVY_BG, NAVY_BD) if r.arm_top else ""
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
                        f'margin-bottom:6px"><span style="font-size:17px;font-weight:750;color:{INK}">'
                        f'{html.escape(str(r.player_name))} · {side_cz(r.side)} {cz(r.line)}</span>{top_c}</div>'
                        + krows([
                            ("p modelu", f"{cz(r.p_model * 100)} %"),
                            ("p trhu (bez marže, 60 min)", f"{cz(r.p_market * 100)} %"),
                            ("hrana", f"+{cz(r.edge * 100)} p.b."),
                            ("model čeká", f"{cz(r.mu_60, 2)} střely · medián {med} · rozpětí {q10}–{q90}"),
                            ("min. kurz u Tipsportu", f"<b>{cz(r.tipsport_min_price, 2)}</b> "
                             f"<small>(férový kurz {cz(1 / r.p_model, 2)})</small>"),
                            ("nejlepší kurz v USA", f"{cz(r.best_price, 2)} <small>({r.best_book})</small>"),
                        ]), unsafe_allow_html=True)
                st.caption("Naivní model bez ověřené hrany. Číselný souhrn úvahy modelu, ne jistota "
                           "výsledku — rozhodnutí je na tobě. Sázej jen to, co si můžeš dovolit ztratit.")

with st.expander("ℹ️ Vysvětlivky"):
    st.markdown("""
**Lajna** — hranice od sázkovky (např. 2,5 střely). Sázíš, jestli hráč vystřelí víc, nebo míň.
**p modelu** — pravděpodobnost naší strany podle modelu: 60 % = ze sta takových zápasů by tip vyšel šedesátkrát.
**p trhu** — totéž podle amerických knih po odečtení marže a přepočtu na 60 minut.
**Hrana** — rozdíl p modelu − p trhu v procentních bodech. Tip vzniká od 3 p.b.
**Min. kurz** — kurz u Tipsportu, od kterého tip pořád splňuje pravidlo. Pod ním marže sní hranu.
**Férový kurz** — 1 ÷ p modelu; při něm by sázka byla přesně na nule.
**⭐ TOP** — nejvýš 3 tipy dne s největší hranou mezi tipy bez varování, jeden na zápas.
**⚠ velká neshoda** — hrana nad 10 p.b.; v NBA byly tyhle tipy nejhorší.
**Rozdělení** — jak pravděpodobný je každý počet střel; pásmo pokrývá 8 z 10 zápasů.
**Proč model tipuje** — přesný rozklad (Shapleyho hodnoty): o kolik procentních bodů zvedá nebo sráží pravděpodobnost tipu střelba hráče, jeho čas na ledě a soupeř, proti průměrnému hráči téže pozice. Součet přesně sedí; neříká, že má model pravdu.

*Všechna čísla jsou odhady modelu, ne jistoty. I tip s vysokou pravděpodobností pravidelně prohrává.*
""")

# --------------------------------------------------------------- 8 · navigation
n1, n2, n3 = st.columns([1.2, 3, 1.2])
if n1.button("← předchozí zápas", disabled=idx <= 0):
    st.session_state["game_id"] = order[idx - 1]
    st.rerun()
n2.markdown(f'<div style="text-align:center;color:{SEC};font-size:13px;padding-top:8px">'
            f'zápas {idx + 1} z {len(order)} · {day}</div>', unsafe_allow_html=True)
if n3.button("další zápas →", type="primary", disabled=idx >= len(order) - 1):
    st.session_state["game_id"] = order[idx + 1]
    st.rerun()

"""Tipy dne - tips of the frozen naive model per game (docs/tips_plan.md),
in the MLB "Přehled dne" look: balance cards, then game cards with their
tips. Read-only; marking a tip as bet comes with the next step (Vsazeno)."""
import html
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import streamlit as st

from dashboard import data
from dashboard.hero import hero, team_logo, ticker
from dashboard.theme import section, setup_page
from nhl_tool import naive_sog as ns
from nhl_tool import tips as tipmod
from nhl_tool.stats import roi_ci

setup_page("Tipy dne")
CZ, ET = ZoneInfo("Europe/Prague"), ZoneInfo("America/New_York")
WARN_EDGE = 0.10       # docs/tips_plan.md section 7 (display only)

if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()


def cz(x, d=1):
    return "–" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def line_txt(side, line):
    return f"{'Více' if side == 'over' else 'Méně'} {cz(line)}"


def cz_time(iso):
    return pd.Timestamp(iso).tz_convert(CZ).strftime("%H:%M") if iso else "?"


st.markdown("""
<style>
.gcard{background:#fff;border:1px solid #e2e6ea;border-radius:14px;overflow:hidden;
  font-variant-numeric:tabular-nums;margin-bottom:14px}
.gcard.has{border-top:3px solid #2E5FB7}
.gcard .ghead{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
  padding:12px 16px 10px;gap:8px}
.gcard .team{font-weight:750;font-size:16px;color:#0c1c33}
.gcard .team img{height:26px;width:26px;vertical-align:-7px;margin-right:6px}
.gcard .team.home{text-align:right}
.gcard .team.home img{margin:0 0 0 6px}
.gcard .team small{display:block;font-weight:450;color:#5a6572;font-size:11px}
.gcard .side{font-size:9.5px;font-weight:750;text-transform:uppercase;letter-spacing:.07em;color:#8b8f9e}
.gcard .mid{color:#5a6572;font-size:11.5px;text-align:center;line-height:1.35}
.gcard .mid b{display:block;color:#0c1c33;font-size:15px}
.gcard .tips{border-top:1px solid #e2e6ea;padding:4px 12px 8px}
.gcard .tip{display:flex;align-items:center;gap:10px;padding:7px 2px;font-size:13.5px;color:#0c1c33}
.gcard .tip+.tip{border-top:1px dashed #e2e6ea}
.gcard .chip{flex:none;width:52px;text-align:center;font-size:10px;font-weight:800;letter-spacing:.06em;
  border-radius:999px;padding:3px 0}
.gcard .chip.over{background:#e8f4ee;color:#1e7a46}.gcard .chip.under{background:#fbeceb;color:#b3403a}
.gcard .lbl{flex:1 1 auto;min-width:0}
.gcard .lbl small{display:block;color:#5a6572;font-size:11.5px;margin-top:1px}
.gcard .warn{color:#b7791f;font-weight:700;font-size:11px;margin-left:4px}
.gcard .minp{flex:none;text-align:right;font-size:11px;color:#5a6572;line-height:1.2}
.gcard .minp b{display:block;font-size:15px;color:#0c1c33}
.gcard .ebar{width:58px;height:7px;background:#f4f6f9;border-radius:4px;overflow:hidden;flex:none}
.gcard .ebar i{display:block;height:100%;background:#2E5FB7}
.gcard .ebar i.w{background:#d9a441}
.gcard .pct{width:44px;text-align:right;color:#5a6572;font-size:12px;flex:none}
.gcard .res{flex:none;font-weight:750;font-size:12px;width:62px;text-align:right}
.gcard .res.win{color:#1e7a46}.gcard .res.loss{color:#b3403a}.gcard .res.void{color:#5a6572}
.gcard .none{padding:10px 16px;color:#5a6572;font-size:12.5px;border-top:1px solid #e2e6ea}
.naive{background:#fdf3e1;border:1px solid #f3d9a6;color:#7a5410;border-radius:12px;
  padding:10px 14px;font-size:13px;margin:2px 0 12px}
.naive b{color:#5c3d06}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------- the day
today = datetime.now(ET).date().isoformat()
days = data.tip_days()
options = sorted(set(days[:7]) | {today}, reverse=True)
labels = {d: ("dnes" if d == today else pd.Timestamp(d).strftime("%-d. %-m.")) for d in options}
day = st.pills("Den", options, format_func=lambda d: labels[d], default=options[0],
               label_visibility="collapsed") or options[0]

df = data.tips_on(day)
games = data.games_on(day)
model = tipmod.load_model()
k = model["nb_k"]
play = df[df["playable"] == 1].copy() if not df.empty else df
n_warn = int((play["edge"] > WARN_EDGE).sum()) if not play.empty else 0
snap = df["snapshot_time"].max() if not df.empty else None

hero("Tipy dne",
     f"<b>{labels[day]}</b> ({day} ET) · {len(games)} zápasů · "
     f"{df['player_id'].nunique() if not df.empty else 0} hráčů s lajnou · "
     f"střely na branku za 60 minut",
     kpi_label="tipů", kpi_value=str(len(play)), kpi_cls="acc", scene="odds",
     ticker_html=ticker([{"cas": cz_time(g.start_time_utc), "a_ab": g.a_ab, "h_ab": g.h_ab,
                          "score": (f"{g.away_score}:{g.home_score}"
                                    if g.game_state in ("OFF", "FINAL") else None)}
                         for g in games.itertuples()]))

# ------------------------------------------------------------- balance cards
rec = data.model_record()


def kpi(tag, big, rows, cls=""):
    cells = "".join(f"<span>{r}</span>" for r in rows)
    return (f'<div class="kpi"><span class="tag">{tag}</span>'
            f'<span class="big{cls}">{big}</span><div class="row">{cells}</div></div>')


if rec.empty:
    model_card = kpi("Model celkem · papír", "–", ["zatím žádný vyhodnocený tip"])
else:
    roi, lo, hi = roi_ci(rec)
    ci = (f"95% CI {cz(lo * 100)} až {cz(hi * 100)} %" if len(rec) >= 30
          else "interval až od 30 tipů")
    model_card = kpi("Model celkem · papír", f"{'+' if roi > 0 else ''}{cz(roi * 100)} %",
                     [f"<b>{len(rec)}</b> tipů", f"výhry <b>{(rec.outcome == 'win').mean() * 100:.0f} %</b>",
                      f"zisk <b>{cz(rec.profit_units.sum())} j.</b>", ci],
                     " up" if roi > 0 else " dn" if roi < 0 else "")
cards = [
    kpi("Tipy dne", str(len(play)),
        [f"⚠ velká neshoda <b>{n_warn}</b>",
         f"hráčů s lajnou <b>{df['player_id'].nunique() if not df.empty else 0}</b>"]),
    model_card,
    kpi("Moje sázky", "–", ["✅ Vsazeno přijde v dalším kroku (~14. 10.)"]),
    kpi("Kurzy", cz_time(snap) if snap else "–",
        [f"snímek <b>{df['snapshot_kind'].iloc[0] if not df.empty else '–'}</b>",
         "americké knihy, převod na 60 min"]),
]
st.markdown('<div class="kpis">' + "".join(cards) + "</div>", unsafe_allow_html=True)

st.markdown(
    '<div class="naive"><b>Naivní model — bez ověřené hrany.</b> Tipy dává zamrazený '
    'jednoduchý model (loňské a letošní střely, čas na ledě, soupeř). Jestli trh porazí, '
    'ukáže až verdikt fáze 0. Na začátku sezóny stojí hlavně na loňsku. '
    '<b>Hraj jen za kurz ≥ min. kurz</b> — pod ním marže Tipsportu sní hranu. '
    '⚠ = model se s trhem rozchází o víc než 10 p.b.; v NBA byly takové tipy nejhorší.</div>',
    unsafe_allow_html=True)

# ------------------------------------------------------------- game cards
by_game = dict(list(play.groupby("game_id"))) if not play.empty else {}
with_lines = set(df["game_id"]) if not df.empty else set()


def tip_row(r) -> str:
    warn = '<span class="warn">⚠</span>' if r.edge > WARN_EDGE else ""
    width = min(abs(r.edge) / 0.20 * 100, 100)
    ctx = []
    if pd.notna(r.loni_s60):
        ctx.append(f"loni {cz(r.loni_s60, 2)}")
    if pd.notna(r.predloni_s60):
        ctx.append(f"předloni {cz(r.predloni_s60, 2)}")
    res = ""
    if isinstance(r.outcome, str):
        txt = {"win": "✅", "loss": "❌", "void": "nehrál"}[r.outcome]
        shots = "" if pd.isna(r.actual_60) else f" {int(r.actual_60)}"
        res = f'<span class="res {r.outcome}">{txt}{shots}</span>'
    minp = (f'<span class="minp">min. kurz<b>{cz(r.tipsport_min_price, 2)}</b></span>'
            if pd.notna(r.tipsport_min_price) else "")
    return (f'<div class="tip"><span class="chip {r.side}">{"VÍCE" if r.side == "over" else "MÉNĚ"}</span>'
            f'<span class="lbl"><b>{html.escape(str(r.player_name))}</b> '
            f'<span style="color:#5a6572">{r.tym or ""}</span> · <b>{line_txt(r.side, r.line)}</b>{warn}'
            f'<small>model {cz(r.p_model * 100)} % · trh {cz(r.p_market * 100)} % · '
            f'čeká {cz(r.mu_60, 2)} střely{" · " + " · ".join(ctx) if ctx else ""}</small></span>'
            f'{minp}<span class="ebar"><i class="{"w" if r.edge > WARN_EDGE else ""}" '
            f'style="width:{width:.0f}%"></i></span>'
            f'<span class="pct">+{cz(r.edge * 100)}</span>{res}</div>')


def card(g) -> str:
    sub = by_game.get(g.game_id)
    if sub is not None and not sub.empty:
        body = ('<div class="tips">' + "".join(tip_row(r) for r in sub.sort_values(
            "edge", ascending=False).itertuples()) + "</div>")
    elif g.game_id in with_lines:
        body = '<div class="none">Model dnes bez tipu.</div>'
    else:
        body = '<div class="none">Zatím bez lajn amerických knih.</div>'
    score = (f"{g.away_score} : {g.home_score}" if g.game_state in ("OFF", "FINAL")
             else cz_time(g.start_time_utc))
    return (f'<div class="gcard{" has" if sub is not None else ""}"><div class="ghead">'
            f'<div class="team">{team_logo(g.a_ab, 26, light=True)}{g.a_ab}'
            f'<small><span class="side">hosté</span></small></div>'
            f'<div class="mid"><b>{score}</b>{"konec" if g.game_state in ("OFF", "FINAL") else "čas CZ"}</div>'
            f'<div class="team home">{g.h_ab}{team_logo(g.h_ab, 26, light=True)}'
            f'<small><span class="side">domácí</span></small></div></div>{body}</div>')


section("Zápasy a tipy", "seřazeno podle začátku · pruh = hrana proti trhu (plný = 20 p.b.)")
if games.empty:
    st.info("V tento den se nehraje.")
rows = list(games.itertuples())
for i in range(0, len(rows), 2):
    cols = st.columns(2)
    for col, g in zip(cols, rows[i:i + 2]):
        col.markdown(card(g), unsafe_allow_html=True)

# ------------------------------------------------------------- calculator
if not df.empty:
    players = (df.drop_duplicates("player_id").sort_values("player_name")
                 [["player_id", "player_name", "tym", "mu_60", "loni_s60"]])
    with st.expander("🧮 Kalkulačka pro Tipsport — libovolný hráč, lajna a kurz"):
        c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
        pick = c1.selectbox("Hráč", players.itertuples(),
                            format_func=lambda r: f"{r.player_name} ({r.tym})")
        line = c2.selectbox("Lajna", [0.5, 1.5, 2.5, 3.5, 4.5], index=2,
                            format_func=lambda x: cz(x))
        side = c3.radio("Strana", ["over", "under"], horizontal=True,
                        format_func=lambda s: "Více" if s == "over" else "Méně")
        price = c4.number_input("Kurz Tipsport", min_value=1.01, value=1.85, step=0.01)
        p_over = float(ns.p_over(pick.mu_60, line, k)[0])
        p_mod = p_over if side == "over" else 1 - p_over
        p_imp = 1 / price
        edge = p_mod - p_imp
        ok = edge >= tipmod.EDGE_MIN
        mp = tipmod.min_price(p_mod)
        st.markdown(
            f"Model čeká **{cz(pick.mu_60, 2)}** střely za 60 minut → "
            f"**{line_txt(side, line)}** s pravděpodobností **{cz(p_mod * 100)} %**. "
            f"Kurz {cz(price, 2)} tvrdí {cz(p_imp * 100)} % (s marží). "
            f"Hrana **{'+' if edge >= 0 else ''}{cz(edge * 100)} p.b.**, očekávaný zisk "
            f"**{'+' if p_mod * price - 1 >= 0 else ''}{cz((p_mod * price - 1) * 100)} %**. "
            + ("✅ **splňuje pravidlo** (hrana ≥ 3 p.b.)" if ok else "❌ **nesplňuje pravidlo**")
            + (f" · min. kurz {cz(mp, 2)}" if mp else ""))

    with st.expander("Všichni hráči s lajnou — pravděpodobnost „více než“ za 60 minut"):
        tbl = players.copy()
        for line in (0.5, 1.5, 2.5, 3.5, 4.5):
            tbl[f"> {cz(line)}"] = (ns.p_over(tbl["mu_60"].to_numpy(), line, k) * 100).round(0)
        st.dataframe(tbl.drop(columns=["player_id"]).rename(columns={
            "player_name": "hráč", "tym": "tým", "mu_60": "čeká střel", "loni_s60": "loni / zápas"}),
            hide_index=True, use_container_width=True,
            column_config={"čeká střel": st.column_config.NumberColumn(format="%.2f"),
                           "loni / zápas": st.column_config.NumberColumn(format="%.2f")})

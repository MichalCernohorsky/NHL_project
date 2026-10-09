"""Týmové trhy - stage 2 of the team markets plan (docs/team_markets_plan.md
section 6, amendment T-5): for both teams of every game the frozen naive
team models' expectation of shots (S-T) and two-minute penalties (T-T) in
60 minutes, P(over / under) for the lines Tipsport uses and the MINIMUM
price at which a ticket meets the rule (p_model - 1/price >= 3 p.b.).
The user compares with Tipsport and writes paper or real tickets; the
page settles them at their own line and price. Locked at puck drop."""
import html
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import streamlit as st

from dashboard import bets, data
from dashboard.hero import hero, team_logo
from dashboard.theme import section, setup_page
from nhl_tool import team_tips
from nhl_tool.stats import roi_ci

setup_page("Týmové trhy")
CZ, ET = ZoneInfo("Europe/Prague"), ZoneInfo("America/New_York")
MIN_DAYS_CI = 5
LOOKS = (300, 800)                       # plan section 6: the two looks
BOOKS = ["Tipsport", "Chance", "Betano", "Fortuna", "jiná"]

if not data.db_path().exists():
    st.error(f"Databáze {data.db_path()} tu není.")
    st.stop()
if not st.session_state.get("_bets_pulled"):
    bets.sync_pull()
    st.session_state["_bets_pulled"] = True

st.markdown("""
<style>
.tcard{background:#fff;border:1px solid #e2e6ea;border-top:3px solid #2E5FB7;border-radius:14px;
  padding:12px 16px 6px;margin-bottom:12px}
.tcard .ghead{display:flex;align-items:center;justify-content:space-between;gap:10px;
  font-weight:800;font-size:17px;color:#0c1c33;margin-bottom:6px}
.tcard .ghead small{font-weight:500;color:#5a6572;font-size:12px}
.tcard .ghead img{height:26px;width:26px;vertical-align:-7px;margin:0 6px}
.mkt{font-size:11px;font-weight:750;letter-spacing:.07em;text-transform:uppercase;color:#5a6572;
  margin:8px 0 2px}
.mkt b{color:#0c1c33;font-size:13px;letter-spacing:0;text-transform:none;font-weight:750}
.ltab{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;
  margin-bottom:6px}
.ltab th{text-align:right;color:#8b8f9e;font-weight:600;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.05em;padding:2px 6px;border-bottom:1px solid #e2e6ea}
.ltab th:first-child,.ltab td:first-child{text-align:left}
.ltab td{text-align:right;padding:3px 6px;border-bottom:1px dashed #eef1f4;color:#0c1c33}
.ltab td.mp{font-weight:750}
.ltab tr.near td{background:#f3f6fb}
.stub{display:inline-flex;gap:8px;padding:3px 9px;background:#e8f4ee;border:1px dashed #bfe0cf;
  border-radius:8px;font-size:11.5px;color:#1e7a46;margin:2px 4px 6px 0}
.stub.paper{background:#f4f6f9;border-color:#d7dce3;color:#5a6572}
.note{background:#fdf3e1;border:1px solid #f3d9a6;color:#7a5410;border-radius:12px;
  padding:10px 14px;font-size:13px;margin:2px 0 12px}
</style>
""", unsafe_allow_html=True)


def cz(x, d=1):
    return "–" if x is None or pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def cz_time(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(CZ).strftime("%H:%M")


def side_cz(side):
    return "více" if side == "over" else "méně"


def kpi(tag, big, rows, cls=""):
    cells = "".join(f"<span>{r}</span>" for r in rows)
    return (f'<div class="kpi"><span class="tag">{tag}</span>'
            f'<span class="big{cls}">{big}</span><div class="row">{cells}</div></div>')


# ------------------------------------------------------------- the day
today = datetime.now(ET).date().isoformat()
days = data.team_pred_days()
options = sorted(set(days[:7]) | {today}, reverse=True)
labels = {d: ("dnes" if d == today else pd.Timestamp(d).strftime("%-d. %-m.")) for d in options}
day = st.pills("Den", options, format_func=lambda d: labels[d], default=options[0],
               label_visibility="collapsed") or options[0]
preds = data.team_preds_on(day)
models = team_tips.load_models()

# ------------------------------------------------------------- tickets + balance
mine = bets.team_bets()
rows = []
for b in mine:
    f = data.team_bet_facts(b["game_id"], b["team_id"], b["market"])
    outcome, profit = (bets.settle(b, f["actual"], True) if f.get("final") else ("pending", 0.0))
    rows.append({**b, "zapas": f.get("zapas"), "actual": f.get("actual"),
                 "outcome": outcome, "profit": profit,
                 "profit_units": profit / b["stake"] if b.get("stake") else 0.0})
log = pd.DataFrame(rows)
done = log[log["outcome"].isin(["win", "loss"])] if not log.empty else log


def record_card(tag, d, empty):
    if d.empty:
        return kpi(tag, "–", [empty])
    roi, lo, hi = roi_ci(d, "game_date", "profit_units")
    n_days = d["game_date"].nunique()
    ci = (f"interval <b>{cz(lo * 100)} až {cz(hi * 100)} %</b>" if n_days >= MIN_DAYS_CI
          else f"interval až od {MIN_DAYS_CI} herních dnů (zatím {n_days})")
    return kpi(tag, f"{'+' if roi > 0 else ''}{cz(roi * 100)} %",
               [f"<b>{len(d)}</b> tiketů", f"výhry <b>{(d.outcome == 'win').mean() * 100:.0f} %</b>",
                f"zisk <b>{cz(d.profit_units.sum(), 2)} j.</b>", ci],
               " up" if roi > 0 else " dn" if roi < 0 else "")


n_all = len(log)
next_look = next((n for n in LOOKS if n_all < n), None)
hero("Týmové trhy", f"<b>{labels[day]}</b> ({day} ET) · střely týmu a dvouminutové tresty za "
     f"60 minut · {preds['game_id'].nunique() if not preds.empty else 0} zápasů s predikcí",
     kpi_label="tiketů k pohledu", kpi_value=(f"{n_all} / {next_look}" if next_look else f"{n_all}"),
     kpi_cls="acc", scene="teams")
if bets.unsynced():
    st.warning("Poslední zápis se nepodařilo zálohovat na GitHub — je uložený v tomto počítači "
               "a odešle se při dalším zápisu.")
paper = done[done["paper"] == True] if not done.empty else done      # noqa: E712
real = done[done["paper"] == False] if not done.empty else done      # noqa: E712
st.markdown('<div class="kpis">' + "".join([
    kpi("Predikce dne", str(preds["game_id"].nunique() if not preds.empty else 0),
        [f"týmů <b>{preds['team_id'].nunique() if not preds.empty else 0}</b>", "S-T a T-T"]),
    record_card("Papírové tikety", paper, "zatím žádný vyhodnocený"),
    record_card("Skutečné tikety", real, "zatím žádný vyhodnocený"),
    kpi("Pohledy", f"{n_all} / {LOOKS[0]}" if n_all < LOOKS[0] else f"{n_all} / {LOOKS[1]}",
        [f"čeká <b>{int((log['outcome'] == 'pending').sum()) if not log.empty else 0}</b>",
         "verdikt až po 300 a 800 tiketech"]),
]) + "</div>", unsafe_allow_html=True)
st.markdown(
    '<div class="note"><b>Bez ověřené hrany proti Tipsportu.</b> Modely porazily jen jednoduché '
    'základy (etapa 1); historické kurzy těchto trhů neexistují, takže o zisku rozhodne teprve '
    'tento test. <b>Tiket dává smysl jen za kurz ≥ min. kurz.</b> Doporučení plánu: do verdiktu '
    'jen papírové tikety. Tresty: jen lajny 3,5 a 4,5; dvojitý menší = 2, střídačka se počítá, '
    'prodloužení ne.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------- per game
if preds.empty:
    st.info("Pro tento den zatím nejsou predikce (zapisuje je denní běh před začátkem zápasů).")
    st.stop()
my_by_key = {}
for r in rows:
    my_by_key.setdefault((r["game_id"], r["team_id"], r["market"]), []).append(r)


def lines_html(market, mu, locked_actual=None):
    t = team_tips.table(market, mu, models)
    if t.empty:
        return '<div style="color:#5a6572;font-size:12px">Bez lajn.</div>'
    out = ['<table class="ltab"><tr><th>lajna</th><th>p více</th><th>min. kurz více</th>'
           '<th>p méně</th><th>min. kurz méně</th></tr>']
    for x in t.itertuples():
        near = " near" if abs(x.line - mu) < 1 else ""
        out.append(f'<tr class="{near.strip()}"><td>{cz(x.line)}</td><td>{cz(x.p_over * 100)} %</td>'
                   f'<td class="mp">{cz(x.min_over, 2) if x.min_over else "–"}</td>'
                   f'<td>{cz(x.p_under * 100)} %</td>'
                   f'<td class="mp">{cz(x.min_under, 2) if x.min_under else "–"}</td></tr>')
    out.append("</table>")
    return "".join(out)


games = preds.drop_duplicates("game_id")
for g in games.itertuples():
    sub = preds[preds["game_id"] == g.game_id]
    final = g.game_state in ("OFF", "FINAL")
    score = f"{g.away_score} : {g.home_score}" if final else f"{cz_time(g.start_time_utc)} CZ"
    locked = bets.started(g.start_time_utc)
    body = [f'<div class="tcard"><div class="ghead"><span>{team_logo(g.a_ab, 26, True)}{g.a_ab} @ '
            f'{g.h_ab}{team_logo(g.h_ab, 26, True)}</span><small>{score}'
            f'{" · zamčeno" if locked else ""}</small></div>']
    st.markdown("".join(body) + "</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    for col, team_id in zip(cols, (g.home_team_id, int(sub.loc[sub["is_home"] == 0, "team_id"].iloc[0]))):
        tr = sub[sub["team_id"] == team_id]
        if tr.empty:
            continue
        ab = tr["tym"].iloc[0]
        with col:
            st.markdown(f'<div style="font-weight:750;color:#0c1c33">{team_logo(ab, 22, True)} {ab} '
                        f'<small style="color:#5a6572;font-weight:500">'
                        f'{"doma" if int(tr["is_home"].iloc[0]) else "venku"}</small></div>',
                        unsafe_allow_html=True)
            for p in tr.itertuples():
                actual = "" if pd.isna(p.actual_60) else f" · skutečnost <b>{int(p.actual_60)}</b>"
                st.markdown(f'<div class="mkt">{team_tips.NAMES[p.market]} · model čeká '
                            f'<b>{cz(p.mu, 2)}</b>{actual}</div>' + lines_html(p.market, p.mu),
                            unsafe_allow_html=True)
                for b in my_by_key.get((p.game_id, p.team_id, p.market), []):
                    res = {"win": "✅", "loss": "❌", "push": "push", "pending": "čeká"}[b["outcome"]]
                    st.markdown(f'<div class="stub{" paper" if b.get("paper") else ""}">'
                                f'{"📝 papír" if b.get("paper") else "🎟️ vsazeno"} · '
                                f'{side_cz(b["side"])} {cz(b["line"])} @ {cz(b["price"], 2)} · '
                                f'{cz(b["stake"], 0)} Kč · {html.escape(str(b["book"]))} · {res}</div>',
                                unsafe_allow_html=True)
    if not locked:
        with st.expander(f"✍️ Tiket {g.a_ab} @ {g.h_ab}"):
            with st.form(f"ticket_{g.game_id}"):
                c1, c2, c3, c4 = st.columns([1.2, 1.4, 1, 1])
                team_pick = c1.selectbox("Tým", sorted(sub["tym"].unique()), key=f"t_{g.game_id}")
                market = c2.selectbox("Trh", list(team_tips.MARKETS), format_func=lambda m: team_tips.NAMES[m],
                                      key=f"m_{g.game_id}")
                row = sub[(sub["tym"] == team_pick) & (sub["market"] == market)]
                mu = float(row["mu"].iloc[0]) if not row.empty else None
                line = c3.selectbox("Lajna", team_tips.lines_for(market, mu) if mu else [],
                                    format_func=cz, key=f"l_{g.game_id}")
                side = c4.radio("Strana", ["over", "under"], format_func=side_cz, horizontal=True,
                                key=f"s_{g.game_id}")
                d1, d2, d3, d4 = st.columns([1, 1, 1.2, 1])
                price = d1.number_input("Kurz", min_value=1.01, value=1.85, step=0.01, key=f"p_{g.game_id}")
                stake = d2.number_input("Vklad (Kč)", min_value=1.0, value=100.0, step=50.0,
                                        key=f"v_{g.game_id}")
                book = d3.selectbox("Sázkovka", BOOKS, key=f"b_{g.game_id}")
                is_paper = d4.checkbox("papírový (bez peněz)", value=True, key=f"pp_{g.game_id}")
                if mu is not None:
                    p = team_tips.p_over(market, mu, float(line), models)
                    if p is not None:
                        p_side = p if side == "over" else 1 - p
                        mp = team_tips.min_price(p_side)
                        ok = price >= (mp or 99)
                        st.caption(f"Model: {side_cz(side)} {cz(line)} s pravděpodobností "
                                   f"{cz(p_side * 100)} % · min. kurz {cz(mp, 2) if mp else '–'} → "
                                   f"{'✅ splňuje pravidlo' if ok else '❌ nesplňuje pravidlo (jen k záznamu)'}")
                if st.form_submit_button("Zapsat tiket", type="primary"):
                    try:
                        pred = row.iloc[0].to_dict()
                        bets.save_team_bet(pred, float(line), float(price), float(stake), book,
                                           side, bool(is_paper))
                        st.success("Tiket zapsaný a zálohovaný." if not bets.unsynced()
                                   else "Tiket zapsaný (záloha na GitHub se zopakuje).")
                        st.rerun()
                    except (bets.Locked, ValueError) as exc:
                        st.error(str(exc))

# ------------------------------------------------------------- log
section("Tikety na týmové trhy", "vyhodnocení za lajnu a kurz z tiketu, 60 minut")
if log.empty:
    st.caption("Zatím žádný tiket.")
else:
    show = log.sort_values("ts", ascending=False).assign(
        typ=log["paper"].map({True: "papír", False: "peníze"}),
        tip=[f"{side_cz(s)} {cz(l)}" for s, l in zip(log["side"], log["line"])],
        trh=log["market"].map(team_tips.NAMES),
        actual=["–" if a is None or pd.isna(a) else str(int(a)) for a in log["actual"]],
        vysledek=log["outcome"].map({"win": "✅", "loss": "❌", "push": "push", "pending": "čeká"}))
    st.dataframe(show[["game_date", "zapas", "team", "trh", "tip", "price", "stake", "typ", "book",
                       "actual", "vysledek", "profit"]].rename(columns={
        "game_date": "den", "zapas": "zápas", "team": "tým", "price": "kurz", "stake": "vklad",
        "book": "sázkovka", "actual": "skutečnost", "vysledek": "výsledek", "profit": "zisk Kč"}),
        hide_index=True, use_container_width=True,
        column_config={"kurz": st.column_config.NumberColumn(format="%.2f"),
                       "zisk Kč": st.column_config.NumberColumn(format="%.0f")})
    pend = [r for r in rows if r["outcome"] == "pending" and not bets.started(r.get("start_time_utc"))]
    if pend:
        with st.expander("Smazat chybně zapsaný tiket (jen před začátkem zápasu)"):
            pick = st.selectbox("Tiket", pend, format_func=lambda r: (
                f'{r["game_date"]} {r["zapas"]} · {r["team"]} · {team_tips.NAMES[r["market"]]} · '
                f'{side_cz(r["side"])} {cz(r["line"])} @ {cz(r["price"], 2)}'))
            if st.button("Smazat", type="secondary"):
                try:
                    bets.delete_bet(pick)
                    st.rerun()
                except bets.Locked as exc:
                    st.error(str(exc))

with st.expander("ℹ️ Vysvětlivky"):
    st.markdown("""
**Model čeká** — očekávaný počet za 60 minut ze zamrazeného naivního modelu (liga × útok týmu × obrana soupeře × doma/venku).
**p více / p méně** — pravděpodobnost podle modelu; u trestů z kalibrace odhadnuté na sezónách 2023–25, proto jen lajny 3,5 a 4,5.
**Min. kurz** — 1 ÷ (p − 0,03): nejnižší kurz, při kterém sázka splňuje pravidlo hrany 3 p.b. Pod ním se nesází.
**Papírový tiket** — zápis bez peněz; počítá se do testu stejně jako skutečný, vykazuje se zvlášť.
**Pohledy** — výsledek se čte jen po 300 a po 800 tiketech (plán, sekce 6); do té doby je bilance jen průběžná.
**Zamčeno** — od začátku zápasu nejde tiket zapsat ani smazat.
""")

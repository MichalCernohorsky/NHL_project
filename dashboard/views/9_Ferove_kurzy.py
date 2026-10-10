"""Férové kurzy - stage 2 of the market-as-model plan (docs/topdown_plan.md):
no model of our own. For every player with a shots line at three or more
US books the page shows the FAIR price of both sides (median de-vig of the
books, converted to 60 minutes) and the MINIMUM Tipsport price at which a
bet has an expected value of at least 3 %. The user compares with Tipsport
and writes a ticket (paper or real) where Tipsport pays at least that.
The rule is enforced in code: three books, a US snapshot no older than 60
minutes, the minimum price, and the lock at puck drop."""
import html
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
import streamlit as st

from dashboard import bets, cloud, data
from dashboard.hero import hero, team_logo
from dashboard.theme import section, setup_page
from nhl_tool import naive_sog as ns
from nhl_tool import tips as tipmod
from nhl_tool.stats import roi_ci

setup_page("Férové kurzy")
CZ, ET = ZoneInfo("Europe/Prague"), ZoneInfo("America/New_York")
MIN_DAYS_CI = 5
LOOKS = (300, 800)
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
  padding:12px 16px 6px;margin-bottom:6px}
.tcard .ghead{display:flex;align-items:center;justify-content:space-between;gap:10px;
  font-weight:800;font-size:17px;color:#0c1c33}
.tcard .ghead small{font-weight:500;color:#5a6572;font-size:12px}
.tcard .ghead img{height:26px;width:26px;vertical-align:-7px;margin:0 6px}
.ltab{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;
  margin-bottom:6px;background:#fff;border:1px solid #e2e6ea;border-radius:10px}
.ltab th{text-align:right;color:#8b8f9e;font-weight:600;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.05em;padding:4px 8px;border-bottom:1px solid #e2e6ea}
.ltab th:first-child,.ltab td:first-child{text-align:left}
.ltab td{text-align:right;padding:4px 8px;border-bottom:1px dashed #eef1f4;color:#0c1c33}
.ltab td.mp{font-weight:750}
.ltab td small{color:#5a6572}
.stub{display:inline-flex;gap:8px;padding:3px 9px;background:#e8f4ee;border:1px dashed #bfe0cf;
  border-radius:8px;font-size:11.5px;color:#1e7a46;margin:2px 4px 6px 0}
.stub.paper{background:#f4f6f9;border-color:#d7dce3;color:#5a6572}
.note{background:#fdf3e1;border:1px solid #f3d9a6;color:#7a5410;border-radius:12px;
  padding:10px 14px;font-size:13px;margin:2px 0 12px}
.stale{background:#fbeceb;border:1px solid #f0cbc7;color:#7c2620;border-radius:10px;
  padding:6px 10px;font-size:12.5px;margin:4px 0 8px}
</style>
""", unsafe_allow_html=True)


def cz(x, d=1):
    return "–" if x is None or pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def cz_time(iso):
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(CZ).strftime("%H:%M")


def side_cz(side):
    return "více" if side == "over" else "méně"


def kpi(tag, big, rows, cls=""):
    cells = "".join(f"<span>{r}</span>" for r in rows)
    return (f'<div class="kpi"><span class="tag">{tag}</span>'
            f'<span class="big{cls}">{big}</span><div class="row">{cells}</div></div>')


# ------------------------------------------------------------- the day
today = datetime.now(ET).date().isoformat()
days = data.fair_days()
options = sorted(set(days[:7]) | {today}, reverse=True)
labels = {d: ("dnes" if d == today else pd.Timestamp(d).strftime("%-d. %-m.")) for d in options}
day = st.pills("Den", options, format_func=lambda d: labels[d], default=options[0],
               label_visibility="collapsed") or options[0]
lines = data.fair_lines(day)
fair = lines[lines["books"] >= bets.FAIR_MIN_BOOKS] if not lines.empty else lines
model = tipmod.load_model()

# ------------------------------------------------------------- tickets + balance
mine = bets.fair_bets()
rows = []
for b in mine:
    f = data.bet_facts(b["game_id"], b["player_id"])
    outcome, profit = (bets.settle(b, f["actual"], f["played"]) if f.get("final") else ("pending", 0.0))
    move = None
    p_close, n_close = data.closing_consensus(b["game_id"], b["player_id"], b["line"])
    if p_close is not None and n_close >= bets.FAIR_MIN_BOOKS:
        grp = ns.pos_group(data.player_position(b["player_id"]))
        p60 = ns.market_p_60(p_close, b["line"], model["nb_k"], model["ot_ratio"][grp])
        move = (p60 if b["side"] == "over" else 1 - p60) - b["p_fair"]
    rows.append({**b, "zapas": f.get("zapas"), "actual": f.get("actual"), "outcome": outcome,
                 "profit": profit, "profit_units": profit / b["stake"] if b.get("stake") else 0.0,
                 "move": move})
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
next_look = next((n for n in LOOKS if n_all < n), LOOKS[-1])
hero("Férové kurzy", f"<b>{labels[day]}</b> ({day} ET) · střely hráčů za 60 minut · férový kurz "
     f"z amerických knih · {fair['player_id'].nunique() if not fair.empty else 0} hráčů",
     kpi_label="tiketů k pohledu", kpi_value=f"{n_all} / {next_look}", kpi_cls="acc", scene="odds")
if bets.unsynced():
    st.warning("Poslední zápis se nepodařilo zálohovat na GitHub — je uložený v tomto počítači "
               "a odešle se při dalším zápisu.")
paper = done[done["paper"] == True] if not done.empty else done      # noqa: E712
real = done[done["paper"] == False] if not done.empty else done      # noqa: E712
moves = log["move"].dropna() if not log.empty else pd.Series(dtype=float)
st.markdown('<div class="kpis">' + "".join([
    record_card("Papírové tikety", paper, "zatím žádný vyhodnocený"),
    record_card("Skutečné tikety", real, "zatím žádný vyhodnocený"),
    kpi("Posun trhu", f"{'+' if moves.mean() > 0 else ''}{cz(moves.mean() * 100)} p.b." if len(moves) else "–",
        [f"<b>{len(moves)}</b> tiketů s večerním kurzem",
         "kladný = americký trh se do večera přiklonil na naši stranu"],
        (" up" if moves.mean() > 0 else " dn") if len(moves) else ""),
    kpi("Pohledy", f"{n_all} / {next_look}",
        [f"čeká <b>{int((log['outcome'] == 'pending').sum()) if not log.empty else 0}</b>",
         "výsledek se čte až po 300 a 800 tiketech"]),
]) + "</div>", unsafe_allow_html=True)
st.markdown(
    '<div class="note"><b>Papírový test, bez ověřené výhody.</b> Férový kurz je průměr amerických '
    'knih po odečtení marže; nic se tu nepředpovídá. Pravidlo: tiket jen tam, kde Tipsport platí '
    '<b>aspoň minimální kurz</b> (o 3 % nad férový), u hráče s kurzem u ≥ 3 knih, a americký snímek '
    'není starší než 60 minut. Kontrola na loňských kurzech princip nevyvrátila ani nepotvrdila '
    '(76 sázek); o výsledku rozhodnou až tikety. Doporučení plánu: do 300 tiketů jen papírově.</div>',
    unsafe_allow_html=True)

if cloud.dispatch_token():
    if st.button("↻ Obnovit americké kurzy (≈ 1 kredit na zápas, nejvýš 3× denně)"):
        started, msg = cloud.dispatch_live_refresh()
        (st.success if started else st.warning)(msg)

# ------------------------------------------------------------- per game
if fair.empty:
    st.info("Pro tento den zatím nejsou americké kurzy (bere je denní běh), nebo je kotují méně "
            "než 3 knihy.")
else:
    my_by_game = {}
    for r in rows:
        my_by_game.setdefault(r["game_id"], []).append(r)
    for gid, g in fair.groupby("game_id", sort=False):
        head = g.iloc[0]
        final = head["game_state"] in ("OFF", "FINAL")
        locked = bets.started(head["start_time_utc"])
        age = bets.snapshot_age_min(head["snapshot_time"])
        fresh = age <= bets.FAIR_MAX_AGE_MIN
        score = (f"{head['away_score']} : {head['home_score']}" if final
                 else f"{cz_time(head['start_time_utc'])} CZ")
        st.markdown(
            f'<div class="tcard"><div class="ghead"><span>{team_logo(head["a_ab"], 26, True)}'
            f'{head["a_ab"]} @ {head["h_ab"]}{team_logo(head["h_ab"], 26, True)}</span>'
            f'<small>{score}{" · zamčeno" if locked else ""} · snímek {cz_time(head["snapshot_time"])}'
            f'</small></div></div>', unsafe_allow_html=True)
        if not locked and not fresh:
            st.markdown(f'<div class="stale">Americký snímek je starý {age:.0f} min — minimální kurzy '
                        'jsou jen orientační a tiket nejde zapsat. Obnov kurzy.</div>',
                        unsafe_allow_html=True)
        out = ['<table class="ltab"><tr><th>hráč</th><th>lajna</th><th>knih</th><th>férový více</th>'
               '<th>min. kurz více</th><th>férový méně</th><th>min. kurz méně</th></tr>']
        for r in g.itertuples():
            p = float(r.p_over)
            out.append(
                f'<tr><td>{html.escape(str(r.player_name))} <small>{r.tym or ""}</small></td>'
                f'<td>{cz(r.line)}</td><td>{int(r.books)}</td><td>{cz(1 / p, 2)}</td>'
                f'<td class="mp">{cz(bets.fair_min_price(p), 2)}</td><td>{cz(1 / (1 - p), 2)}</td>'
                f'<td class="mp">{cz(bets.fair_min_price(1 - p), 2)}</td></tr>')
        st.markdown("".join(out) + "</table>", unsafe_allow_html=True)
        for b in my_by_game.get(gid, []):
            res = {"win": "✅", "loss": "❌", "push": "push", "void": "nehrál", "pending": "čeká"}[b["outcome"]]
            st.markdown(f'<div class="stub{" paper" if b.get("paper") else ""}">'
                        f'{"📝 papír" if b.get("paper") else "🎟️ vsazeno"} · '
                        f'{html.escape(str(b["player_name"]))} · {side_cz(b["side"])} {cz(b["line"])} @ '
                        f'{cz(b["price"], 2)} (min. {cz(b["min_price"], 2)}) · {cz(b["stake"], 0)} Kč · {res}'
                        '</div>', unsafe_allow_html=True)
        if not locked and fresh:
            with st.expander(f"✍️ Tiket {head['a_ab']} @ {head['h_ab']}"):
                with st.form(f"fair_{gid}"):
                    picks = list(g.itertuples())
                    c1, c2, c3 = st.columns([2.4, 1, 1])
                    pick = c1.selectbox("Hráč a lajna", picks, key=f"fp_{gid}",
                                        format_func=lambda r: f"{r.player_name} ({r.tym}) · {cz(r.line)}")
                    side = c2.radio("Strana", ["over", "under"], format_func=side_cz, horizontal=True,
                                    key=f"fs_{gid}")
                    price = c3.number_input("Kurz Tipsportu", min_value=1.01, value=1.90, step=0.01,
                                            key=f"fk_{gid}")
                    d1, d2, d3 = st.columns([1, 1.2, 1])
                    stake = d1.number_input("Vklad (Kč)", min_value=1.0, value=100.0, step=50.0,
                                            key=f"fv_{gid}")
                    book = d2.selectbox("Sázkovka", BOOKS, key=f"fb_{gid}")
                    is_paper = d3.checkbox("papírový (bez peněz)", value=True, key=f"fpp_{gid}")
                    p_side = float(pick.p_over) if side == "over" else 1 - float(pick.p_over)
                    need = bets.fair_min_price(p_side)
                    st.caption(f"Férový kurz {cz(1 / p_side, 2)} · minimální kurz {cz(need, 2)} → "
                               f"{'✅ splňuje pravidlo' if price >= need else '❌ pod minimálním kurzem — nezapíše se'}"
                               f" · očekávaný zisk {cz((price * p_side - 1) * 100)} %")
                    if st.form_submit_button("Zapsat tiket", type="primary"):
                        try:
                            bets.save_fair_bet(pick._asdict(), side, float(price), float(stake), book,
                                               bool(is_paper))
                            st.success("Tiket zapsaný." if not bets.unsynced()
                                       else "Tiket zapsaný (záloha na GitHub se zopakuje).")
                            st.rerun()
                        except (bets.Locked, ValueError) as exc:
                            st.error(str(exc))

# ------------------------------------------------------------- log
section("Tikety testu", "vyhodnocení za lajnu a kurz z tiketu, střely za 60 minut")
if log.empty:
    st.caption("Zatím žádný tiket.")
else:
    show = log.sort_values("ts", ascending=False).assign(
        typ=log["paper"].map({True: "papír", False: "peníze"}),
        tip=[f"{side_cz(s)} {cz(l)}" for s, l in zip(log["side"], log["line"])],
        actual=["–" if a is None or pd.isna(a) else str(int(a)) for a in log["actual"]],
        ev=log["ev"] * 100, posun=log["move"] * 100,
        vysledek=log["outcome"].map({"win": "✅", "loss": "❌", "push": "push", "void": "nehrál",
                                     "pending": "čeká"}))
    st.dataframe(show[["game_date", "zapas", "player_name", "tip", "price", "min_price", "ev", "stake",
                       "typ", "actual", "vysledek", "profit", "posun"]].rename(columns={
        "game_date": "den", "zapas": "zápas", "player_name": "hráč", "price": "kurz",
        "min_price": "min. kurz", "ev": "oček. zisk %", "stake": "vklad", "actual": "střel",
        "vysledek": "výsledek", "profit": "zisk Kč", "posun": "posun trhu p.b."}),
        hide_index=True, use_container_width=True,
        column_config={"kurz": st.column_config.NumberColumn(format="%.2f"),
                       "min. kurz": st.column_config.NumberColumn(format="%.2f"),
                       "oček. zisk %": st.column_config.NumberColumn(format="%.1f"),
                       "posun trhu p.b.": st.column_config.NumberColumn(format="%.1f"),
                       "zisk Kč": st.column_config.NumberColumn(format="%.0f")})
    pend = [r for r in rows if r["outcome"] == "pending" and not bets.started(r.get("start_time_utc"))]
    if pend:
        with st.expander("Smazat chybně zapsaný tiket (jen před začátkem zápasu)"):
            pick = st.selectbox("Tiket", pend, format_func=lambda r: (
                f'{r["game_date"]} · {r["player_name"]} · {side_cz(r["side"])} {cz(r["line"])} @ '
                f'{cz(r["price"], 2)}'))
            if st.button("Smazat", type="secondary"):
                try:
                    bets.delete_bet(pick)
                    st.rerun()
                except bets.Locked as exc:
                    st.error(str(exc))

with st.expander("ℹ️ Vysvětlivky"):
    st.markdown("""
**Férový kurz** — 1 ÷ pravděpodobnost podle amerických knih (prostřední z nich, bez marže), přepočtená na 60 minut, jak vyhodnocuje Tipsport.
**Minimální kurz** — férový kurz × 1,03. Od něj má sázka očekávaný zisk aspoň 3 %, pokud má americký trh pravdu.
**Knih** — kolik amerických knih kotuje obě strany lajny. Pod tři se férový kurz nepočítá.
**Posun trhu** — o kolik procentních bodů se pravděpodobnost naší strany podle amerických knih změnila mezi tiketem a posledním kurzem před zápasem. Kladný průměr je dobré znamení dřív, než je znát bilance.
**Pohledy** — výsledek se čte jen po 300 a 800 tiketech; při ~0,3 tiketu na zápas první pohled vychází zhruba na březen.
**Lajna Tipsportu jinde** — když má Tipsport jinou lajnu než tabulka, férový kurz pro ni nemáme a tiket se nepíše.
""")

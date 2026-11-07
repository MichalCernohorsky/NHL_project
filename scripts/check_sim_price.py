#!/usr/bin/env python3
"""How close is the simulated Tipsport price (US consensus at the same line,
60 minutes, + m = 8.74 %) to the real Tipsport prices logged from the user's
screenshots? Descriptive check of a measurement, no betting rule."""
import re, sqlite3, sys, unicodedata
import numpy as np, pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nhl_tool import phase0, tips
from nhl_tool.odds_import import normalize_name

# approximate screenshot times (docs/tipsport_k1_log.md), UTC
SHOT_UTC = {"2026-09-29": "18:00", "2026-10-02": "19:30", "2026-10-04": "11:15", "2026-10-10": "14:05", "2026-10-11": "15:30"}
rows = []
for line in open(Path(__file__).resolve().parents[1] / "docs" / "tipsport_k1_log.md"):
    m = re.match(r"^\| (\d{1,2})\. (\d{1,2})\. \| ([A-Z]{3})@([A-Z]{3}) \| (.+?) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", line)
    if m:
        d, mo, a, h, name, ln, over, under = m.groups()
        rows.append({"date": f"2026-{int(mo):02d}-{int(d):02d}", "away": a, "home": h, "name": re.sub(r"\s*\(\d{4}\)", "", name),
                     "line": float(ln), "over": float(over), "under": float(under)})
ts = pd.DataFrame(rows)
c = sqlite3.connect("file:data/nhl.db?mode=ro", uri=True); c.row_factory = sqlite3.Row
model = tips.load_model(); k = model["nb_k"]
g = pd.read_sql_query("""SELECT g.game_id, g.game_date, a.abbreviation away, h.abbreviation home FROM games g
                         JOIN teams a ON a.team_id = g.away_team_id JOIN teams h ON h.team_id = g.home_team_id""", c)
ts = ts.merge(g, left_on=["date", "away", "home"], right_on=["game_date", "away", "home"], how="left")
print("pairs", len(ts), "matched games", ts.game_id.notna().sum())
pos = dict(c.execute("SELECT player_id, position FROM players").fetchall())
out = []
for r in ts.dropna(subset=["game_id"]).itertuples():
    odds = pd.read_sql_query("""SELECT player_id, player_name_raw, bookmaker, line, side, price, snapshot_time, snapshot_kind
                                FROM odds WHERE game_id = ? AND market = 'player_shots_on_goal' AND line = ?
                                  AND snapshot_kind IN ('live', 'morning', 'closing')""", c, params=(int(r.game_id), r.line))
    if odds.empty: continue
    want = set(normalize_name(r.name).split())
    odds["match"] = [set(normalize_name(n).split()) == want for n in odds.player_name_raw]
    o = odds[odds["match"]]
    if o.empty: continue
    shot = f"{r.date}T{SHOT_UTC[r.date]}:00Z"
    for label, sub in (("before_shot", o[o.snapshot_time <= shot]), ("closing", o[o.snapshot_kind == "closing"])):
        if sub.empty: continue
        last = sub[sub.snapshot_time == sub.snapshot_time.max()]
        wide = last.pivot_table(index="bookmaker", columns="side", values="price", aggfunc="max").dropna()
        if wide.empty: continue
        p_full = float(np.median((1 / wide["over"]) / (1 / wide["over"] + 1 / wide["under"])))
        grp = "D" if pos.get(int(o.player_id.dropna().iloc[0]) if o.player_id.notna().any() else -1) == "D" else "F"
        p60 = phase0.p60(p_full, r.line, k, model["ot_ratio"][grp])
        io, iu = 1 / r.over, 1 / r.under
        p_ts = io / (io + iu)
        out.append({"which": label, "date": r.date, "name": r.name, "line": r.line, "books": len(wide), "p_ts": p_ts, "p_us60": p60,
                    "sim_over": 1 / (p60 * 1.0874), "sim_under": 1 / ((1 - p60) * 1.0874), "ts_over": r.over, "ts_under": r.under,
                    "age_h": (pd.Timestamp(shot) - pd.Timestamp(last.snapshot_time.iloc[0])).total_seconds() / 3600})
res = pd.DataFrame(out)
for which, part in res.groupby("which"):
    d = (part.p_ts - part.p_us60) * 100
    pd_over = part.ts_over - part.sim_over; pd_under = part.ts_under - part.sim_under
    print(f"\n{which}: pairs {len(part)} | Tipsport - US60 (p.b.): mean {d.mean():+.2f}, median {d.median():+.2f}, mean |diff| {d.abs().mean():.2f}, "
          f"within 2 pb {(d.abs() <= 2).mean() * 100:.0f} %, within 4 pb {(d.abs() <= 4).mean() * 100:.0f} %, corr {np.corrcoef(part.p_ts, part.p_us60)[0, 1]:.3f}")
    print(f"   price diff Tipsport - simulated: over mean {pd_over.mean():+.3f} |{pd_over.abs().mean():.3f}|, under mean {pd_under.mean():+.3f} |{pd_under.abs().mean():.3f}| | "
          f"snapshot age h median {part.age_h.median():.1f} | by date: " + ", ".join(f"{k} {v}" for k, v in part.date.value_counts().sort_index().items()))

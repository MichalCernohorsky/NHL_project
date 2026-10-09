"""Team markets, stage 2 (docs/team_markets_plan.md section 6, amendment
T-5): the frozen naive team models' expectation for today's games, the
probabilities and minimum Tipsport prices the page shows, and settlement.

Markets: S-T team shots on goal, T-T team two-minute penalties, both in
60 minutes. Predictions are written once per (game, team, market) before
puck drop; every input comes from games with an earlier date.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import naive_sog as ns
from . import team_model as tm
from .tips import EDGE_MIN, min_price  # noqa: F401 - the same rule as player tips

ROOT = Path(__file__).resolve().parents[2]
MODEL_FILE = ROOT / "models" / "naive_team.json"
CAL_FILE = ROOT / "models" / "naive_team_tt_cal.json"
MARKETS = {"S-T": "shots", "T-T": "penalties"}
NAMES = {"S-T": "střely týmu", "T-T": "dvouminutové tresty týmu"}
N_LINES_ST = 6


def load_models(model_path: Path = MODEL_FILE, cal_path: Path = CAL_FILE) -> dict:
    team = json.loads(model_path.read_text())
    cal = json.loads(cal_path.read_text())
    return {"team": team, "cal": {float(k): (v["a"], v["b"]) for k, v in cal["lines"].items()},
            "names": {"S-T": team["model"], "T-T": f"{team['model']}+{cal['model']}"}}


# ----------------------------------------------------------------- display

def lines_for(market: str, mu: float) -> list[float]:
    if market == "T-T":
        return list(tm.CAL_LINES)
    base = int(round(mu))
    return [base - 2.5 + i for i in range(N_LINES_ST)]


def p_over(market: str, mu: float, line: float, models: dict) -> float | None:
    """P(count > line) in 60 minutes; None where the plan gives no number."""
    if market == "S-T":
        k = models["team"]["families"]["shots"]["k_team"]
        return float(ns.p_over(mu, line, k)[0])
    ab = models["cal"].get(float(line))
    return None if ab is None else float(tm.logit_p(mu, ab))


def table(market: str, mu: float, models: dict) -> pd.DataFrame:
    """One row per line: P(over), P(under) and the minimum price of each side."""
    rows = []
    for line in lines_for(market, mu):
        p = p_over(market, mu, line, models)
        if p is None:
            continue
        rows.append({"line": line, "p_over": p, "p_under": 1 - p,
                     "min_over": min_price(p), "min_under": min_price(1 - p)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- build

def upcoming_rows(conn, game_date: str) -> pd.DataFrame:
    g = pd.read_sql_query(
        """SELECT game_id, season, game_date, start_time_utc, home_team_id, away_team_id
           FROM games WHERE game_date = ? AND season_type = 'regular'""", conn, params=(game_date,))
    rows = []
    for r in g.itertuples(index=False):
        rows.append((r.game_id, r.season, r.game_date, r.home_team_id, r.away_team_id, 1))
        rows.append((r.game_id, r.season, r.game_date, r.away_team_id, r.home_team_id, 0))
    out = pd.DataFrame(rows, columns=["game_id", "season", "game_date", "team_id", "opp_id", "is_home"])
    out["y"] = np.nan
    out["y_opp"] = np.nan
    out["start_time_utc"] = out["game_id"].map(dict(zip(g["game_id"], g["start_time_utc"])))
    return out


def frame_for(conn, game_date: str, family: str) -> pd.DataFrame:
    """As-of frame: every finished game with an EARLIER date plus the day's
    games with unknown counts, so their features use only the past."""
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT season FROM games WHERE season_type = 'regular' ORDER BY season")]
    hist = tm.load_team_games(conn, seasons, family)
    hist = hist[hist["game_date"] < game_date]
    up = upcoming_rows(conn, game_date)
    cols = ["game_id", "season", "game_date", "team_id", "opp_id", "is_home", "y", "y_opp"]
    both = pd.concat([hist[cols], up[cols]], ignore_index=True)
    frame = tm.add_asof(both)
    starts = dict(zip(up["game_id"], up["start_time_utc"]))
    frame["start_time_utc"] = frame["game_id"].map(starts)
    return frame


def build(conn, game_date: str, now: datetime | None = None, models: dict | None = None) -> dict:
    """Write the day's predictions (INSERT OR IGNORE) for games not started."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    models = models or load_models()
    stats = {"games": 0, "inserted": 0, "started": 0}
    for market, family in MARKETS.items():
        const = models["team"]["families"][family]
        frame = frame_for(conn, game_date, family)
        today = frame[frame["game_date"] == game_date].reset_index(drop=True)
        if today.empty:
            continue
        mu = tm.predict(today, const)
        f = tm.factors(today, const["w"], const["c"], const["league_mean_train"])
        opp_def = tm.opponent_defence(today, const)
        stats["games"] = int(today["game_id"].nunique())
        for i, r in enumerate(today.itertuples(index=False)):
            if not r.start_time_utc or r.start_time_utc <= now_iso:
                stats["started"] += 1
                continue
            stats["inserted"] += conn.execute(
                """INSERT OR IGNORE INTO team_predictions (game_id, team_id, market, game_date,
                       start_time_utc, opp_id, is_home, mu, model, f_league, f_attack, f_defence,
                       f_n, built_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(r.game_id), int(r.team_id), market, game_date, r.start_time_utc,
                 int(r.opp_id), int(r.is_home), float(mu[i]), models["names"][market],
                 float(f.loc[i, "L"]), float(f.loc[i, "attack"]), float(opp_def[i]),
                 int(r.n), now_iso.replace("Z", "+00:00"))).rowcount
        conn.commit()
    return stats


# ------------------------------------------------------------------ settle

def actual_60(conn, game_id: int, team_id: int, market: str) -> int | None:
    """The team's 60-minute count once the game's counts are loaded, else None."""
    if market == "S-T":
        done = conn.execute("SELECT 1 FROM backfill_state WHERE task = 'pbp' AND key = ? "
                            "AND status = 'done'", (str(game_id),)).fetchone()
        r = conn.execute("SELECT SUM(sog_reg) AS s, SUM(sog_reg IS NULL) AS missing, COUNT(*) AS n "
                         "FROM player_game_logs WHERE game_id = ? AND team_id = ?",
                         (game_id, team_id)).fetchone()
        if not done or not r["n"] or r["missing"]:
            return None
        return int(r["s"])
    done = conn.execute("SELECT 1 FROM backfill_state WHERE task = 'penalties' AND key = ? "
                        "AND status = 'done'", (str(game_id),)).fetchone()
    if not done:
        return None
    r = conn.execute("""SELECT COALESCE(SUM(duration / 2), 0) FROM penalties
                        WHERE game_id = ? AND team_id = ? AND period_type = 'REG'
                          AND type_code IN ('MIN', 'BEN')""", (game_id, team_id)).fetchone()
    return int(r[0])


def settle(conn, upto_date: str, now: datetime | None = None) -> int:
    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    pending = conn.execute(
        """SELECT p.game_id, p.team_id, p.market FROM team_predictions p JOIN games g USING (game_id)
           WHERE p.actual_60 IS NULL AND p.game_date <= ? AND g.game_state IN ('OFF', 'FINAL')""",
        (upto_date,)).fetchall()
    n = 0
    for p in pending:
        a = actual_60(conn, p["game_id"], p["team_id"], p["market"])
        if a is None:
            continue
        conn.execute("UPDATE team_predictions SET actual_60 = ?, settled_at = ? "
                     "WHERE game_id = ? AND team_id = ? AND market = ?",
                     (a, now_iso, p["game_id"], p["team_id"], p["market"]))
        n += 1
    conn.commit()
    return n

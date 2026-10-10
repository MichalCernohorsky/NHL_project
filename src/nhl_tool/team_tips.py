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
from . import team_v2 as t2
from .tips import EDGE_MIN, min_price  # noqa: F401 - the same rule as player tips

ROOT = Path(__file__).resolve().parents[2]
MODEL_FILE = ROOT / "models" / "naive_team.json"
CAL_FILE = ROOT / "models" / "naive_team_tt_cal.json"
V2_FILE = ROOT / "models" / "team_v2.json"
MARKETS = {"S-T": "shots", "T-T": "penalties"}
NAMES = {"S-T": "střely týmu", "T-T": "dvouminutové tresty týmu"}
N_LINES_ST = 6


def load_models(model_path: Path = MODEL_FILE, cal_path: Path = CAL_FILE,
                v2_path: Path = V2_FILE) -> dict:
    team = json.loads(model_path.read_text())
    cal = json.loads(cal_path.read_text())
    v2 = json.loads(v2_path.read_text()) if v2_path.exists() else None      # None until frozen
    return {"team": team, "cal": {float(k): (v["a"], v["b"]) for k, v in cal["lines"].items()},
            "names": {"S-T": team["model"], "T-T": f"{team['model']}+{cal['model']}"}, "v2": v2}


# ----------------------------------------------------------------- display

def lines_for(market: str, mu: float) -> list[float]:
    if market == "T-T":
        return list(tm.CAL_LINES)
    base = int(round(mu))
    return [base - 2.5 + i for i in range(N_LINES_ST)]


def active(pred, models: dict) -> tuple[float, str]:
    """(expectation, version) the page and the tickets use for a stored
    prediction: version 2 (block A) where it was written next to version 1
    and its frozen file is here - it replaced version 1 on both markets
    (docs/team_v2_report.md) - else version 1."""
    mu2 = pred.get("mu_v2") if isinstance(pred, dict) else getattr(pred, "mu_v2", None)
    mu1 = pred.get("mu") if isinstance(pred, dict) else getattr(pred, "mu")
    if models.get("v2") and mu2 is not None and not pd.isna(mu2):
        return float(mu2), "v2"
    return float(mu1), "v1"


def model_name(market: str, version: str, models: dict) -> str:
    return f"{models['v2']['model']}_A" if version == "v2" else models["names"][market]


def p_over(market: str, mu: float, line: float, models: dict, version: str = "v1") -> float | None:
    """P(count > line) in 60 minutes; None where the plan gives no number.
    `version` picks the dispersion / calibration that belongs to mu."""
    if market == "S-T":
        k = models["v2"]["shots"]["k"] if version == "v2" else models["team"]["families"]["shots"]["k_team"]
        return float(ns.p_over(mu, line, k)[0])
    cal = t2.as_cal(models["v2"]["penalties"]["cal"]) if version == "v2" else models["cal"]
    ab = cal.get(float(line))
    return None if ab is None else float(tm.logit_p(mu, ab))


def table(market: str, mu: float, models: dict, version: str = "v1") -> pd.DataFrame:
    """One row per line: P(over), P(under) and the minimum price of each side."""
    rows = []
    for line in lines_for(market, mu):
        p = p_over(market, mu, line, models, version)
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


def _seasons(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT season FROM games WHERE season_type = 'regular' ORDER BY season")]


def raw_frame(conn, game_date: str, family: str) -> pd.DataFrame:
    """Every finished game with an EARLIER date plus the day's games with
    unknown counts (before the as-of columns are added)."""
    hist = tm.load_team_games(conn, _seasons(conn), family)
    hist = hist[hist["game_date"] < game_date]
    up = upcoming_rows(conn, game_date)
    cols = ["game_id", "season", "game_date", "team_id", "opp_id", "is_home", "y", "y_opp"]
    return pd.concat([hist[cols], up[cols]], ignore_index=True)


def frame_for(conn, game_date: str, family: str) -> pd.DataFrame:
    """As-of frame: the day's games get features from the past only."""
    frame = tm.add_asof(raw_frame(conn, game_date, family))
    up = upcoming_rows(conn, game_date)
    starts = dict(zip(up["game_id"], up["start_time_utc"]))
    frame["start_time_utc"] = frame["game_id"].map(starts)
    return frame


def mu_v2(conn, game_date: str, models: dict) -> dict:
    """Block A expectation of models v2 for the day's games:
    {(game_id, team_id, market): mu}. Empty until models/team_v2.json exists.
    Referees are not known before the game, so block R is never used here."""
    v2 = models.get("v2")
    if not v2:
        return {}
    const = models["team"]["families"]
    frames = t2.build_frames(raw_frame(conn, game_date, "shots"), raw_frame(conn, game_date, "penalties"),
                             t2.load_team_attempts(conn, _seasons(conn)), t2.load_b2b(conn),
                             t2.load_referees(conn), const)
    out = {}
    for market, family in MARKETS.items():
        today = frames[family][frames[family]["game_date"] == game_date].reset_index(drop=True)
        if today.empty:
            continue
        mu = t2.predict_a(today, const[family], v2[family])
        for gid, tid, m in zip(today["game_id"], today["team_id"], mu):
            if np.isfinite(m) and m > 0:
                out[(int(gid), int(tid), market)] = float(m)
    return out


def build(conn, game_date: str, now: datetime | None = None, models: dict | None = None) -> dict:
    """Write the day's predictions (INSERT OR IGNORE) for games not started."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    models = models or load_models()
    stats = {"games": 0, "inserted": 0, "started": 0}
    try:
        second = mu_v2(conn, game_date, models)
    except Exception as exc:  # noqa: BLE001 - version 1 must be written even if version 2 fails
        print(f"POZOR: predikce verze 2 se nepodarilo spocitat ({type(exc).__name__}: {exc}); "
              "zapisuje se jen verze 1")
        second = {}
    name_v2 = models["v2"]["model"] + "_A" if second else None
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
                       f_n, built_at, mu_v2, model_v2)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(r.game_id), int(r.team_id), market, game_date, r.start_time_utc,
                 int(r.opp_id), int(r.is_home), float(mu[i]), models["names"][market],
                 float(f.loc[i, "L"]), float(f.loc[i, "attack"]), float(opp_def[i]),
                 int(r.n), now_iso.replace("Z", "+00:00"),
                 (v := second.get((int(r.game_id), int(r.team_id), market))),
                 name_v2 if v is not None else None)).rowcount
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

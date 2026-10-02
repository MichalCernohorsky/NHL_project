"""Read-only data access for the dashboard.

The database is opened with SQLite's mode=ro: no page can write, whatever
it does. Every odds query names its snapshot kind
(tests/test_snapshot_isolation.py scans this file too).

Descriptive only. Nothing here is an evaluation of a betting rule - those
live in pre-registered reports (docs/), never on a page someone can filter
until a pattern appears.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QUOTA_LOG = ROOT / "data" / "odds_quota.log"


def db_path() -> Path:
    env = os.environ.get("NHL_DASHBOARD_DB")
    if env:
        return Path(env)
    from nhl_tool.config import load_config, resolve_db_path
    return resolve_db_path(load_config())


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql: str, params=()) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def age_hours() -> float | None:
    p = db_path()
    return (time.time() - p.stat().st_mtime) / 3600 if p.exists() else None


def live_season() -> str:
    from nhl_tool.config import load_config
    return load_config()["live"]["season"]


def seasons() -> list[str]:
    df = q("""SELECT DISTINCT g.season FROM games g
              JOIN player_game_logs p USING (game_id)
              WHERE g.season_type = 'regular' ORDER BY g.season DESC""")
    return df["season"].tolist()


# ------------------------------------------------------------ overview

def coverage() -> pd.DataFrame:
    return q("""
        SELECT g.season AS sezona,
               COUNT(*) AS zapasu,
               SUM(g.game_state IN ('OFF', 'FINAL')) AS odehrano,
               SUM(g.last_period_type IN ('OT', 'SO')) AS prodlouzeni,
               (SELECT COUNT(DISTINCT p.game_id) FROM player_game_logs p
                  JOIN games x USING (game_id) WHERE x.season = g.season) AS box_score,
               (SELECT COUNT(DISTINCT p.game_id) FROM player_game_logs p
                  JOIN games x USING (game_id)
                 WHERE x.season = g.season AND p.pp_toi_s IS NOT NULL) AS s_pp_toi,
               (SELECT COUNT(DISTINCT p.game_id) FROM player_game_logs p
                  JOIN games x USING (game_id)
                 WHERE x.season = g.season AND p.sog_reg IS NOT NULL) AS strely_60
        FROM games g WHERE g.season_type = 'regular'
        GROUP BY g.season ORDER BY g.season""")


def games_on(game_date: str) -> pd.DataFrame:
    return q("""SELECT g.game_id, g.start_time_utc, g.game_state, g.home_score,
                       g.away_score, g.last_period_type,
                       h.abbreviation AS h_ab, a.abbreviation AS a_ab
                FROM games g JOIN teams h ON h.team_id = g.home_team_id
                JOIN teams a ON a.team_id = g.away_team_id
                WHERE g.game_date = ? AND g.season_type = 'regular'
                ORDER BY g.start_time_utc""", (game_date,))


def odds_by_day() -> pd.DataFrame:
    return q("""SELECT g.game_date AS den, o.snapshot_kind AS snimek,
                       COUNT(DISTINCT o.game_id) AS zapasu,
                       COUNT(DISTINCT o.player_name_raw) AS hracu,
                       COUNT(*) AS radku,
                       SUM(o.player_id IS NULL) AS nesparovano
                FROM odds o JOIN games g USING (game_id)
                WHERE o.snapshot_kind IN ('morning', 'closing')
                GROUP BY g.game_date, o.snapshot_kind
                ORDER BY g.game_date DESC, o.snapshot_kind DESC""")


def odds_lines(game_date: str, kind: str) -> pd.DataFrame:
    """Latest snapshot of the given kind per (game, player, market, book, line)."""
    return q("""SELECT a.abbreviation || ' @ ' || h.abbreviation AS zapas,
                       o.player_name_raw AS hrac, o.market AS trh, o.bookmaker AS kniha,
                       o.line AS lajna,
                       MAX(CASE WHEN o.side = 'over' THEN o.price END) AS vice,
                       MAX(CASE WHEN o.side = 'under' THEN o.price END) AS mene,
                       MAX(o.snapshot_time) AS cas_snimku,
                       MAX(o.player_id IS NULL) AS nesparovan
                FROM odds o JOIN games g USING (game_id)
                JOIN teams h ON h.team_id = g.home_team_id
                JOIN teams a ON a.team_id = g.away_team_id
                WHERE g.game_date = ? AND o.snapshot_kind = ?
                  AND o.snapshot_time = (SELECT MAX(x.snapshot_time) FROM odds x
                                         WHERE x.game_id = o.game_id
                                           AND x.snapshot_kind = o.snapshot_kind)
                GROUP BY o.game_id, o.player_name_raw, o.market, o.bookmaker, o.line
                ORDER BY zapas, trh, hrac, kniha""", (game_date, kind))


def quota() -> dict | None:
    """Last balance The Odds API reported (data/odds_quota.log), if any."""
    if not QUOTA_LOG.exists():
        return None
    lines = [ln for ln in QUOTA_LOG.read_text().splitlines() if "remaining=" in ln]
    if not lines:
        return None
    last = lines[-1].split()
    fields = dict(x.split("=", 1) for x in last if "=" in x)
    return {"cas": last[0], "zbyva": fields.get("remaining"), "utraceno": fields.get("used")}


# ------------------------------------------------------------ players

def skaters(season: str, min_games: int = 1) -> pd.DataFrame:
    return q("""SELECT p.player_id, pl.full_name AS jmeno, p.position AS pozice,
                       (SELECT t.abbreviation FROM player_game_logs z
                          JOIN games zg USING (game_id) JOIN teams t ON t.team_id = z.team_id
                         WHERE z.player_id = p.player_id AND zg.season = ?
                         ORDER BY zg.game_date DESC LIMIT 1) AS tym,
                       COUNT(*) AS zapasu, AVG(p.sog) AS strely,
                       AVG(p.sog_reg) AS strely_60, AVG(p.toi_s) / 60.0 AS toi_min
                FROM player_game_logs p JOIN games g USING (game_id)
                JOIN players pl ON pl.player_id = p.player_id
                WHERE g.season = ? AND g.season_type = 'regular'
                GROUP BY p.player_id HAVING COUNT(*) >= ?
                ORDER BY strely DESC""", (season, season, min_games))


def player_games(player_id: int, season: str) -> pd.DataFrame:
    return q("""SELECT g.game_date AS datum, g.game_id,
                       CASE WHEN p.team_id = g.home_team_id THEN 'vs ' || a.abbreviation
                            ELSE '@ ' || h.abbreviation END AS souper,
                       g.last_period_type AS konec,
                       p.toi_s / 60.0 AS toi, p.pp_toi_s / 60.0 AS pp_toi,
                       p.ot_toi_s / 60.0 AS ot_toi,
                       p.sog AS strely, p.sog_reg AS strely_60,
                       p.blocked_shots AS bloky, p.blocked_shots_reg AS bloky_60,
                       p.goals AS goly, p.assists AS asistence, p.points AS body,
                       p.hits AS hity, p.plus_minus AS plus_minus
                FROM player_game_logs p JOIN games g USING (game_id)
                JOIN teams h ON h.team_id = g.home_team_id
                JOIN teams a ON a.team_id = g.away_team_id
                WHERE p.player_id = ? AND g.season = ? AND g.season_type = 'regular'
                ORDER BY g.game_date""", (player_id, season))


# ------------------------------------------------------------ goalies

def goalies(season: str) -> pd.DataFrame:
    return q("""SELECT gl.player_id, pl.full_name AS jmeno,
                       (SELECT t.abbreviation FROM goalie_game_logs z
                          JOIN games zg USING (game_id) JOIN teams t ON t.team_id = z.team_id
                         WHERE z.player_id = gl.player_id AND zg.season = ?
                         ORDER BY zg.game_date DESC LIMIT 1) AS tym,
                       SUM(gl.started) AS startu, COUNT(*) AS zapasu,
                       AVG(CASE WHEN gl.started = 1 THEN gl.saves END) AS zasahy_start,
                       AVG(CASE WHEN gl.started = 1 THEN gl.saves_reg END) AS zasahy_60,
                       SUM(gl.saves) * 1.0 / NULLIF(SUM(gl.shots_against), 0) AS uspesnost
                FROM goalie_game_logs gl JOIN games g USING (game_id)
                JOIN players pl ON pl.player_id = gl.player_id
                WHERE g.season = ? AND g.season_type = 'regular'
                GROUP BY gl.player_id ORDER BY startu DESC""", (season, season))


def goalie_games(player_id: int, season: str) -> pd.DataFrame:
    return q("""SELECT g.game_date AS datum,
                       CASE WHEN gl.team_id = g.home_team_id THEN 'vs ' || a.abbreviation
                            ELSE '@ ' || h.abbreviation END AS souper,
                       gl.started AS start, gl.toi_s / 60.0 AS toi,
                       gl.shots_against AS strely_proti, gl.saves AS zasahy,
                       gl.saves_reg AS zasahy_60, gl.goals_against AS obdrzene,
                       gl.decision AS vysledek
                FROM goalie_game_logs gl JOIN games g USING (game_id)
                JOIN teams h ON h.team_id = g.home_team_id
                JOIN teams a ON a.team_id = g.away_team_id
                WHERE gl.player_id = ? AND g.season = ? AND g.season_type = 'regular'
                ORDER BY g.game_date""", (player_id, season))


# ------------------------------------------------------------ teams

def team_table(season: str) -> pd.DataFrame:
    return q("""SELECT t.abbreviation AS tym, t.full_name AS nazev,
                       COUNT(*) AS zapasu,
                       AVG(me.sog) AS strely_pro, AVG(op.sog) AS strely_proti,
                       AVG(me.goals) AS goly_pro, AVG(op.goals) AS goly_proti,
                       SUM(g.last_period_type IN ('OT', 'SO')) AS prodlouzeni
                FROM team_game_logs me
                JOIN team_game_logs op ON op.game_id = me.game_id AND op.team_id != me.team_id
                JOIN games g ON g.game_id = me.game_id
                JOIN teams t ON t.team_id = me.team_id
                WHERE g.season = ? AND g.season_type = 'regular'
                GROUP BY me.team_id ORDER BY strely_pro DESC""", (season,))


def team_games(abbr: str, season: str) -> pd.DataFrame:
    return q("""SELECT g.game_date AS datum,
                       CASE WHEN me.is_home = 1 THEN 'vs ' ELSE '@ ' END
                         || o.abbreviation AS souper,
                       me.sog AS strely_pro, op.sog AS strely_proti,
                       me.goals AS goly_pro, op.goals AS goly_proti,
                       g.last_period_type AS konec
                FROM team_game_logs me
                JOIN team_game_logs op ON op.game_id = me.game_id AND op.team_id != me.team_id
                JOIN games g ON g.game_id = me.game_id
                JOIN teams t ON t.team_id = me.team_id
                JOIN teams o ON o.team_id = op.team_id
                WHERE t.abbreviation = ? AND g.season = ? AND g.season_type = 'regular'
                ORDER BY g.game_date""", (abbr, season))


# ------------------------------------------------------------ tips

def tip_days() -> list[str]:
    """ET game dates that have tips, newest first."""
    if not _has_table("tips"):
        return []
    return q("SELECT DISTINCT game_date FROM tips ORDER BY game_date DESC")["game_date"].tolist()


def _has_table(name: str) -> bool:
    return not q("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).empty


def tips_on(game_date: str) -> pd.DataFrame:
    """All candidates of the day from the latest snapshot per game, with
    team abbreviations and the player's last two seasons (context, plan 7)."""
    if not _has_table("tips"):
        return pd.DataFrame()
    df = q("""SELECT t.*, tm.abbreviation AS tym, op.abbreviation AS souper,
                     g.home_team_id, g.game_state, g.home_score, g.away_score
              FROM tips t
              JOIN games g USING (game_id)
              LEFT JOIN teams tm ON tm.team_id = t.team_id
              LEFT JOIN teams op ON op.team_id = t.opp_id
              WHERE t.game_date = ?
                AND t.snapshot_time = (SELECT MAX(x.snapshot_time) FROM tips x
                                       WHERE x.game_id = t.game_id)""", (game_date,))
    if df.empty:
        return df
    season = q("SELECT season FROM games WHERE game_date = ? LIMIT 1", (game_date,))["season"][0]
    y = int(season[:4])
    prev1, prev2 = f"{y - 1}-{str(y)[2:]}", f"{y - 2}-{str(y - 1)[2:]}"
    ctx = q(f"""SELECT p.player_id, g.season, COUNT(*) AS gp, AVG(p.sog_reg) AS s60
                FROM player_game_logs p JOIN games g USING (game_id)
                WHERE g.season IN (?, ?) AND g.season_type = 'regular' AND p.toi_s > 0
                  AND p.player_id IN ({",".join(str(int(x)) for x in df.player_id.unique())})
                GROUP BY p.player_id, g.season""", (prev1, prev2))
    for label, season_ in (("loni", prev1), ("predloni", prev2)):
        part = ctx[ctx.season == season_].set_index("player_id")
        df[f"{label}_s60"] = df.player_id.map(part["s60"])
        df[f"{label}_gp"] = df.player_id.map(part["gp"])
    return df


def model_record() -> pd.DataFrame:
    """Settled playable tips (MODEL arm, paper), one row per tip."""
    if not _has_table("tips"):
        return pd.DataFrame()
    return q("""SELECT game_date, edge, outcome, profit_units FROM tips
                WHERE playable = 1 AND outcome IN ('win', 'loss')
                ORDER BY game_date""")

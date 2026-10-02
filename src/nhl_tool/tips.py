"""Tips of the live season from the frozen naive shots model (docs/tips_plan.md).

Rule (plan 6.4, entry D6): for every (game, player, line, book) quoting both
sides, p_market = that book's proportional de-vig converted to 60 minutes
(D3.3); edge = p_model - p_market for each side. Per (game, player) the
single candidate with the largest edge is the tip if edge >= 3 p.b. and the
player passes the live entry rule. Everything else is stored too.

Settlement (60 minutes, D3): a player without ice time in the game is void.
The MODEL arm is paid at the simulated Tipsport price of D1.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import naive_sog as ns

EDGE_MIN = 0.03
MARKET = "player_shots_on_goal"
ROOT = Path(__file__).resolve().parents[2]
MODEL_FILE = ROOT / "models" / "naive_sog.json"


def load_model(path: Path = MODEL_FILE) -> dict:
    return json.loads(Path(path).read_text())


def constants(model: dict) -> dict:
    return {k: model[k] for k in ("league_team_shots", "prior_rate_per_s", "ot_ratio")}


def devig_over(price_over: float, price_under: float) -> float:
    io, iu = 1.0 / price_over, 1.0 / price_under
    return io / (io + iu)


def min_price(p_model: float) -> float | None:
    """Lowest Tipsport price at which the tip still has edge >= EDGE_MIN
    against the raw 1/price (stricter than a de-vig: NBA rule_at_book)."""
    return 1.0 / (p_model - EDGE_MIN) if p_model > EDGE_MIN else None


def tip_id(model: str, game_id, player_id, line, side, snapshot_time) -> str:
    raw = f"{model}|{game_id}|{player_id}|{line}|{side}|{snapshot_time}"
    return hashlib.sha1(raw.encode()).hexdigest()


# ---------------------------------------------------------------- inputs

def latest_snapshot(conn, game_date: str, kind: str) -> pd.DataFrame:
    """Matched shots lines of the latest snapshot of `kind` for each game of
    the day - only games that had not started at that snapshot."""
    return pd.read_sql_query(
        """SELECT o.game_id, o.player_id, o.player_name_raw, o.bookmaker, o.line,
                  o.side, o.price, o.snapshot_time, g.start_time_utc, g.game_date
           FROM odds o JOIN games g USING (game_id)
           WHERE g.game_date = ? AND g.season_type = 'regular'
             AND o.market = ? AND o.snapshot_kind = ? AND o.player_id IS NOT NULL
             AND o.snapshot_time = (SELECT MAX(x.snapshot_time) FROM odds x
                                    WHERE x.game_id = o.game_id AND x.market = o.market
                                      AND x.snapshot_kind = o.snapshot_kind)
             AND o.snapshot_time < g.start_time_utc""",
        conn, params=(game_date, MARKET, kind))


def player_team(conn, player_id: int, season: str, game) -> int | None:
    """The player's side in this game: latest roster of the season that is
    one of the two teams, else his latest box-score team."""
    teams = (game["home_team_id"], game["away_team_id"])
    r = conn.execute("""SELECT team_id FROM rosters WHERE player_id = ? AND season = ?
                        AND team_id IN (?, ?) ORDER BY last_seen DESC LIMIT 1""",
                     (player_id, season, *teams)).fetchone()
    if r:
        return r[0]
    r = conn.execute("""SELECT p.team_id FROM player_game_logs p JOIN games g USING (game_id)
                        WHERE p.player_id = ? AND p.team_id IN (?, ?)
                        ORDER BY g.game_date DESC LIMIT 1""",
                     (player_id, *teams)).fetchone()
    return r[0] if r else None


def predict(conn, model: dict, game_date: str, players: pd.DataFrame) -> pd.DataFrame:
    """mu_60 + entry flags for (game_id, player_id) pairs on game_date, from
    history strictly before it (virtual rows; nothing of the day is known)."""
    games = {r["game_id"]: r for r in conn.execute(
        "SELECT game_id, season, home_team_id, away_team_id FROM games WHERE game_date = ?",
        (game_date,))}
    if players.empty or not games:
        return pd.DataFrame()
    season = next(iter(games.values()))["season"]
    hist = ns.load_skater_games(conn, [ns.prev_season(season), season])
    hist = hist[hist["game_date"] < game_date]
    pos = dict(conn.execute("SELECT player_id, position FROM players"))
    rows = []
    for gid, pid in players[["game_id", "player_id"]].drop_duplicates().itertuples(index=False):
        g = games[gid]
        team = player_team(conn, pid, season, g)
        if team is None or pos.get(pid) == "G":
            continue
        opp = g["away_team_id"] if team == g["home_team_id"] else g["home_team_id"]
        rows.append({"game_id": gid, "game_date": game_date, "season": season,
                     "player_id": pid, "team_id": team, "opp_id": opp,
                     "position": pos.get(pid), "toi_s": 0, "ot_toi_s": 0, "sog": 0,
                     "sog_reg": 0, "toi_reg": 0, "group": ns.pos_group(pos.get(pid))})
    if not rows:
        return pd.DataFrame()
    virt = pd.DataFrame(rows)
    f = ns.features(pd.concat([hist, virt], ignore_index=True), constants(model))
    f = f.merge(virt[["game_id", "player_id"]], on=["game_id", "player_id"])
    return f[["game_id", "player_id", "team_id", "opp_id", "group", "mu_60",
              "entry_live", "gp_before", "prev_gp"]]


# ----------------------------------------------------------------- build

def candidates(lines: pd.DataFrame, pred: pd.DataFrame, model: dict, margin: float) -> pd.DataFrame:
    """One row per (game, player, line, side): best book's edge."""
    if lines.empty or pred.empty:
        return pd.DataFrame()
    k = model["nb_k"]
    wide = (lines.pivot_table(index=["game_id", "player_id", "player_name_raw", "bookmaker",
                                     "line", "snapshot_time", "start_time_utc"],
                              columns="side", values="price", aggfunc="max")
                 .dropna(subset=["over", "under"]).reset_index())
    wide = wide[(wide["line"] * 2) % 2 == 1]            # half-point lines only
    wide = wide.merge(pred, on=["game_id", "player_id"])
    if wide.empty:
        return pd.DataFrame()
    rows = []
    for r in wide.itertuples(index=False):
        p_mod_over = float(ns.p_over(r.mu_60, r.line, k)[0])
        p_mkt_over = ns.market_p_60(devig_over(r.over, r.under), r.line, k,
                                    model["ot_ratio"][r.group])
        for side, pm, pk, price in (("over", p_mod_over, p_mkt_over, r.over),
                                    ("under", 1 - p_mod_over, 1 - p_mkt_over, r.under)):
            rows.append({"game_id": r.game_id, "player_id": r.player_id,
                         "player_name": r.player_name_raw, "line": r.line, "side": side,
                         "book": r.bookmaker, "price": price, "p_model": pm, "p_market": pk,
                         "edge": pm - pk, "mu_60": r.mu_60, "team_id": r.team_id,
                         "opp_id": r.opp_id, "entry_live": bool(r.entry_live),
                         "gp_season": int(r.gp_before), "gp_prev": int(r.prev_gp),
                         "snapshot_time": r.snapshot_time, "start_time_utc": r.start_time_utc})
    c = pd.DataFrame(rows)
    books = (c[c.side == "over"].groupby(["game_id", "player_id", "line"])["book"]
             .nunique().rename("books"))
    best_price = c.groupby(["game_id", "player_id", "line", "side"])["price"].max().rename("best_price")
    best = (c.sort_values("edge", ascending=False)
             .groupby(["game_id", "player_id", "line", "side"], as_index=False).first())
    best = best.merge(books, on=["game_id", "player_id", "line"]).merge(
        best_price, on=["game_id", "player_id", "line", "side"])
    best["sim_tipsport_price"] = 1.0 / (best["p_market"] * (1 + margin))
    best["tipsport_min_price"] = best["p_model"].map(min_price)
    top = best.sort_values("edge", ascending=False).groupby(["game_id", "player_id"]).head(1)
    best["playable"] = False
    keep = top[(top["edge"] >= EDGE_MIN) & top["entry_live"]].index
    best.loc[keep, "playable"] = True
    return best


def store(conn, cand: pd.DataFrame, model_name: str, game_date: str, kind: str) -> int:
    if cand.empty:
        return 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    for r in cand.itertuples(index=False):
        n += conn.execute(
            """INSERT OR IGNORE INTO tips (tip_id, model, game_id, game_date, start_time_utc,
                   player_id, player_name, team_id, opp_id, market, line, side, mu_60,
                   p_model, p_market, edge, books, best_book, best_price, tipsport_min_price,
                   sim_tipsport_price, entry_live, gp_season, gp_prev, playable,
                   snapshot_kind, snapshot_time, built_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?)""",
            (tip_id(model_name, r.game_id, r.player_id, r.line, r.side, r.snapshot_time),
             model_name, int(r.game_id), game_date, r.start_time_utc, int(r.player_id),
             r.player_name, int(r.team_id), int(r.opp_id), MARKET, float(r.line), r.side,
             float(r.mu_60), float(r.p_model), float(r.p_market), float(r.edge),
             int(r.books), r.book, float(r.best_price),
             None if r.tipsport_min_price is None or (isinstance(r.tipsport_min_price, float)
                                                      and math.isnan(r.tipsport_min_price))
             else float(r.tipsport_min_price),
             float(r.sim_tipsport_price), int(r.entry_live), int(r.gp_season),
             int(r.gp_prev), int(r.playable), kind, r.snapshot_time, now)).rowcount
    return n


def build(conn, game_date: str, kind: str = "live", model_path: Path = MODEL_FILE,
          margin: float = 0.0875) -> dict:
    model = load_model(model_path)
    lines = latest_snapshot(conn, game_date, kind)
    pred = predict(conn, model, game_date, lines)
    cand = candidates(lines, pred, model, margin)
    n = store(conn, cand, model["model"], game_date, kind)
    conn.commit()
    return {"games": int(lines["game_id"].nunique()) if not lines.empty else 0,
            "candidates": int(len(cand)), "inserted": n,
            "playable": int(cand["playable"].sum()) if not cand.empty else 0}


# ---------------------------------------------------------------- settle

def settle(conn, upto_date: str) -> int:
    """Settle tips of finished games up to upto_date whose 60-minute counts
    are loaded. Void when the player had no ice time."""
    pending = conn.execute(
        """SELECT t.tip_id, t.game_id, t.player_id, t.line, t.side, t.sim_tipsport_price
           FROM tips t JOIN games g USING (game_id)
           WHERE t.outcome IS NULL AND t.game_date <= ?
             AND g.game_state IN ('OFF', 'FINAL')
             AND EXISTS (SELECT 1 FROM backfill_state b WHERE b.task = 'pbp'
                         AND b.key = CAST(t.game_id AS TEXT) AND b.status = 'done')""",
        (upto_date,)).fetchall()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    for t in pending:
        r = conn.execute("""SELECT sog_reg, toi_s FROM player_game_logs
                            WHERE game_id = ? AND player_id = ?""",
                         (t["game_id"], t["player_id"])).fetchone()
        if r is None or not r["toi_s"]:
            outcome, actual, profit = "void", None, 0.0
        else:
            actual = int(r["sog_reg"])
            over = actual > t["line"]
            won = over if t["side"] == "over" else not over
            outcome = "win" if won else "loss"
            profit = t["sim_tipsport_price"] - 1.0 if won else -1.0
        conn.execute("""UPDATE tips SET actual_60 = ?, outcome = ?, profit_units = ?,
                        settled_at = ? WHERE tip_id = ?""",
                     (actual, outcome, profit, now, t["tip_id"]))
        n += 1
    conn.commit()
    return n

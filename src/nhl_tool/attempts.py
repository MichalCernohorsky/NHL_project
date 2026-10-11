"""Play-by-play -> shot attempts and their split by manpower, 60 minutes
(docs/models_v2_plan.md, step 0).

An attempt is a shot on goal, a missed shot or a blocked shot (credited to
the shooter). The situation code of an event is four digits: away goalie,
away skaters, home skaters, home goalie. An event is 'pp' for the shooter
when his team has more skaters on the ice and both goalies are in net,
'sh' when it has fewer; everything else (five on five, four on four, an
empty net) counts as even strength.

The same check as for shots (pbp.py) applies: the full-game shots on goal
of every skater must equal his box score, otherwise the game is not stored.
"""
from __future__ import annotations

from collections import defaultdict

ATTEMPTS = ("shot-on-goal", "goal", "missed-shot", "blocked-shot")
ON_GOAL = ("shot-on-goal", "goal")


def strength(code: str | None, shooter_is_home: bool) -> str:
    if not code or len(code) != 4 or not code.isdigit():
        return "ev"
    away_g, away_s, home_s, home_g = (int(c) for c in code)
    if away_g != 1 or home_g != 1:
        return "ev"                       # an empty net is not a power play
    own, opp = (home_s, away_s) if shooter_is_home else (away_s, home_s)
    return "pp" if own > opp else "sh" if own < opp else "ev"


def parse_attempts(payload: dict) -> list[dict]:
    """One dict per regulation attempt: shooter, on goal or not, situation code."""
    out = []
    for e in payload.get("plays") or []:
        kind = e.get("typeDescKey")
        if kind not in ATTEMPTS:
            continue
        if (e.get("periodDescriptor") or {}).get("periodType") != "REG":
            continue
        det = e.get("details") or {}
        if kind == "goal" and not det.get("shotType"):
            continue                      # a goal credited without a shot (pbp.py)
        shooter = det.get("scoringPlayerId") if kind == "goal" else det.get("shootingPlayerId")
        if not shooter:
            continue
        out.append({"player_id": int(shooter), "on_goal": kind in ON_GOAL,
                    "code": e.get("situationCode")})
    return out


def splits(events: list[dict], team_of: dict[int, int], home_team_id: int) -> dict[int, dict]:
    """Per skater of the game (keys of team_of): the stored counts. Skaters
    without an attempt get zeros; shooters not in team_of (goalies) are skipped."""
    out = {pid: {"team_id": team, "att_reg": 0, "sog_pp_reg": 0, "att_pp_reg": 0,
                 "sog_sh_reg": 0, "att_sh_reg": 0} for pid, team in team_of.items()}
    for e in events:
        row = out.get(e["player_id"])
        if row is None:
            continue
        row["att_reg"] += 1
        s = strength(e["code"], row["team_id"] == home_team_id)
        if s != "ev":
            row[f"att_{s}_reg"] += 1
            row[f"sog_{s}_reg"] += int(e["on_goal"])
    return out


def on_goal_reg(events: list[dict]) -> dict[int, int]:
    n: dict[int, int] = defaultdict(int)
    for e in events:
        n[e["player_id"]] += int(e["on_goal"])
    return n


def mismatches(conn, game_id: int, events: list[dict]) -> list[str]:
    """Skaters whose regulation shots on goal from these events differ from
    the stored 60-minute count (which was itself checked against the box score)."""
    return compare(conn.execute("SELECT player_id, sog_reg FROM player_game_logs WHERE game_id = ?",
                                (game_id,)), events)


def compare(rows, events: list[dict]) -> list[str]:
    """The same check against any rows (player_id, sog_reg)."""
    got = on_goal_reg(events)
    out = []
    for r in rows:
        if r["sog_reg"] is None:
            out.append(f"{r['player_id']} sog_reg missing")
        elif r["sog_reg"] != got.get(r["player_id"], 0):
            out.append(f"{r['player_id']} sog_reg db={r['sog_reg']} pbp={got.get(r['player_id'], 0)}")
    return out


def store(conn, game_id: int, events: list[dict]) -> int:
    g = conn.execute("SELECT home_team_id FROM games WHERE game_id = ?", (game_id,)).fetchone()
    team_of = {r["player_id"]: r["team_id"] for r in conn.execute(
        "SELECT player_id, team_id FROM player_game_logs WHERE game_id = ?", (game_id,))}
    rows = splits(events, team_of, g["home_team_id"])
    conn.execute("DELETE FROM player_shot_splits WHERE game_id = ?", (game_id,))
    conn.executemany(
        """INSERT INTO player_shot_splits (game_id, player_id, team_id, att_reg, sog_pp_reg,
               att_pp_reg, sog_sh_reg, att_sh_reg) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [(game_id, pid, r["team_id"], r["att_reg"], r["sog_pp_reg"], r["att_pp_reg"],
          r["sog_sh_reg"], r["att_sh_reg"]) for pid, r in rows.items()])
    return len(rows)

"""Box score (+ scratches from the game page's right rail) -> per-game logs.

Everything parsed here is POST-GAME truth. In particular the goalie
`starter` flag is who actually started - known for certain only after puck
drop - and must never be read as a pre-game attribute of the same game.
"""
from __future__ import annotations

from .parsing import default_name, saves_over_shots, toi_to_seconds

SIDES = (("homeTeam", 1), ("awayTeam", 0))


def parse_boxscore(payload: dict) -> dict:
    game_id = int(payload["id"])
    stats = payload.get("playerByGameStats") or {}
    players, skaters, goalies, teams = [], [], [], []
    for side, is_home in SIDES:
        team = payload[side]
        team_id = int(team["id"])
        teams.append({"game_id": game_id, "team_id": team_id, "is_home": is_home,
                      "goals": team.get("score"), "sog": team.get("sog")})
        block = stats.get(side) or {}
        for p in (block.get("forwards") or []) + (block.get("defense") or []):
            players.append({"player_id": int(p["playerId"]),
                            "short_name": default_name(p.get("name")),
                            "position": p.get("position")})
            skaters.append({
                "game_id": game_id, "player_id": int(p["playerId"]),
                "team_id": team_id, "position": p.get("position"),
                "toi_s": toi_to_seconds(p.get("toi")), "shifts": p.get("shifts"),
                "goals": p.get("goals"), "assists": p.get("assists"),
                "points": p.get("points"), "sog": p.get("sog"),
                "blocked_shots": p.get("blockedShots"), "hits": p.get("hits"),
                "pim": p.get("pim"), "plus_minus": p.get("plusMinus"),
                "pp_goals": p.get("powerPlayGoals"),
                "giveaways": p.get("giveaways"), "takeaways": p.get("takeaways"),
                "faceoff_pct": p.get("faceoffWinningPctg"),
            })
        for g in block.get("goalies") or []:
            players.append({"player_id": int(g["playerId"]),
                            "short_name": default_name(g.get("name")),
                            "position": "G"})
            goalies.append({
                "game_id": game_id, "player_id": int(g["playerId"]),
                "team_id": team_id, "started": int(bool(g.get("starter"))),
                "toi_s": toi_to_seconds(g.get("toi")),
                "shots_against": g.get("shotsAgainst"), "saves": g.get("saves"),
                "goals_against": g.get("goalsAgainst"),
                "ev_shots_against": saves_over_shots(g.get("evenStrengthShotsAgainst"))[1],
                "pp_shots_against": saves_over_shots(g.get("powerPlayShotsAgainst"))[1],
                "sh_shots_against": saves_over_shots(g.get("shorthandedShotsAgainst"))[1],
                "decision": g.get("decision"),
            })
    outcome = (payload.get("gameOutcome") or {}).get("lastPeriodType")
    game = {"game_id": game_id,
            "home_score": payload["homeTeam"].get("score"),
            "away_score": payload["awayTeam"].get("score"),
            "last_period_type": outcome, "game_state": payload.get("gameState")}
    return {"game": game, "players": players, "skaters": skaters,
            "goalies": goalies, "teams": teams}


def parse_scratches(payload: dict, game_id: int, home_id: int, away_id: int) -> list[dict]:
    info = payload.get("gameInfo") or {}
    rows = []
    for side, team_id in (("homeTeam", home_id), ("awayTeam", away_id)):
        for s in (info.get(side) or {}).get("scratches") or []:
            name = " ".join(x for x in (default_name(s.get("firstName")),
                                        default_name(s.get("lastName"))) if x)
            rows.append({"game_id": game_id, "team_id": team_id,
                         "player_id": int(s["id"]), "full_name": name or None})
    return rows


def is_finished(payload: dict) -> bool:
    return payload.get("gameState") in ("OFF", "FINAL")


def store(conn, parsed: dict, scratches: list[dict]):
    """Idempotent: re-running a game replaces its rows."""
    gid = parsed["game"]["game_id"]
    conn.executemany(
        """INSERT INTO players (player_id, short_name, position)
           VALUES (:player_id, :short_name, :position)
           ON CONFLICT(player_id) DO UPDATE SET
               short_name = excluded.short_name,
               position = COALESCE(players.position, excluded.position)""",
        parsed["players"])
    for table in ("player_game_logs", "goalie_game_logs", "team_game_logs", "scratches"):
        conn.execute(f"DELETE FROM {table} WHERE game_id = ?", (gid,))
    conn.executemany(
        """INSERT INTO player_game_logs (game_id, player_id, team_id, position,
               toi_s, shifts, goals, assists, points, sog, blocked_shots, hits,
               pim, plus_minus, pp_goals, giveaways, takeaways, faceoff_pct)
           VALUES (:game_id, :player_id, :team_id, :position, :toi_s, :shifts,
               :goals, :assists, :points, :sog, :blocked_shots, :hits, :pim,
               :plus_minus, :pp_goals, :giveaways, :takeaways, :faceoff_pct)""",
        parsed["skaters"])
    conn.executemany(
        """INSERT INTO goalie_game_logs (game_id, player_id, team_id, started,
               toi_s, shots_against, saves, goals_against, ev_shots_against,
               pp_shots_against, sh_shots_against, decision)
           VALUES (:game_id, :player_id, :team_id, :started, :toi_s,
               :shots_against, :saves, :goals_against, :ev_shots_against,
               :pp_shots_against, :sh_shots_against, :decision)""",
        parsed["goalies"])
    conn.executemany(
        """INSERT INTO team_game_logs (game_id, team_id, is_home, goals, sog)
           VALUES (:game_id, :team_id, :is_home, :goals, :sog)""",
        parsed["teams"])
    conn.executemany(
        """INSERT OR REPLACE INTO scratches (game_id, team_id, player_id, full_name)
           VALUES (:game_id, :team_id, :player_id, :full_name)""", scratches)
    g = parsed["game"]
    conn.execute(
        """UPDATE games SET home_score = ?, away_score = ?,
               last_period_type = COALESCE(?, last_period_type), game_state = ?
           WHERE game_id = ?""",
        (g["home_score"], g["away_score"], g["last_period_type"],
         g["game_state"], gid))

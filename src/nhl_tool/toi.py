"""Even-strength / power-play / short-handed / overtime time on ice.

The box score has only total TOI. The split comes from the stats REST API
(`skater/timeonice`, one row per player and game), queried one game day at a
time: a whole-season query would hit the API's 10 000-row cap silently.
The same rows carry the skater's full name, which the box score abbreviates.
"""
from __future__ import annotations

REPORT = "skater/timeonice"


def day_params(game_date: str, game_type: int = 2) -> dict:
    return {"isAggregate": "false", "isGame": "true", "limit": "-1",
            "cayenneExp": f'gameDate="{game_date}" and gameTypeId={game_type}'}


def parse_rows(payload: dict) -> list[dict]:
    rows = []
    for r in payload.get("data") or []:
        rows.append({"game_id": int(r["gameId"]), "player_id": int(r["playerId"]),
                     "ev_toi_s": r.get("evTimeOnIce"), "pp_toi_s": r.get("ppTimeOnIce"),
                     "sh_toi_s": r.get("shTimeOnIce"), "ot_toi_s": r.get("otTimeOnIce"),
                     "full_name": r.get("skaterFullName"),
                     "shoots": r.get("shootsCatches")})
    return rows


def store(conn, rows: list[dict]) -> int:
    """Updates rows the box-score step created; returns how many rows had no
    box-score row to update (the box score must be loaded first)."""
    unmatched = 0
    for r in rows:
        cur = conn.execute(
            """UPDATE player_game_logs SET ev_toi_s = ?, pp_toi_s = ?,
                   sh_toi_s = ?, ot_toi_s = ?
               WHERE game_id = ? AND player_id = ?""",
            (r["ev_toi_s"], r["pp_toi_s"], r["sh_toi_s"], r["ot_toi_s"],
             r["game_id"], r["player_id"]))
        unmatched += cur.rowcount == 0
        if r["full_name"]:
            conn.execute(
                """UPDATE players SET full_name = ?, shoots = COALESCE(?, shoots)
                   WHERE player_id = ?""",
                (r["full_name"], r["shoots"], r["player_id"]))
    return unmatched

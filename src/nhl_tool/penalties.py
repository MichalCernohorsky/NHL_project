"""Play-by-play -> penalty events (docs/team_markets_plan.md, step 2).

One row per penalty, with its kind and length, so that Tipsport's counting
rule for "dvouminutové tresty" (plan O1-O5) can be applied later without
downloading again. `eventOwnerTeamId` is the penalized team.

Check against the box score, as for shots (pbp.py): the penalty minutes the
play-by-play gives each skater over the whole game must equal his box-score
PIM; otherwise the game is marked as an error and nothing is stored. Bench
penalties have no player and are not covered by the check.
"""
from __future__ import annotations

from collections import Counter


def parse_penalties(payload: dict) -> list[dict]:
    out = []
    for e in payload.get("plays") or []:
        if e.get("typeDescKey") != "penalty":
            continue
        det = e.get("details") or {}
        per = e.get("periodDescriptor") or {}
        out.append({
            "event_id": int(e["eventId"]),
            "team_id": det.get("eventOwnerTeamId"),
            "period": per.get("number"),
            "period_type": per.get("periodType"),
            "time_in_period": e.get("timeInPeriod"),
            "type_code": det.get("typeCode"),
            "desc_key": det.get("descKey"),
            "duration": det.get("duration"),
            "committed_by": det.get("committedByPlayerId"),
            "served_by": det.get("servedByPlayerId"),
            "drawn_by": det.get("drawnByPlayerId"),
        })
    return out


def incomplete(rows: list[dict]) -> list[str]:
    """Events that cannot be stored (the feed left out a required field)."""
    return [f"event {r['event_id']} missing {k}" for r in rows
            for k in ("team_id", "period", "period_type", "type_code") if r.get(k) is None]


# A match penalty is 5 minutes on the clock in the play-by-play but 15 penalty
# minutes in the box score (found by the check: game 2025020222).
BOX_MINUTES = {"MAT": 15}


def box_minutes(row: dict) -> int:
    """Penalty minutes the box score charges the player for this event."""
    return BOX_MINUTES.get(row["type_code"], row["duration"] or 0)


def mismatches(conn, game_id: int, rows: list[dict]) -> list[str]:
    """Skaters whose play-by-play penalty minutes differ from the box score."""
    pim = Counter()
    for r in rows:
        if r["committed_by"] and r["period_type"] != "SO":
            pim[r["committed_by"]] += box_minutes(r)
    out = []
    for r in conn.execute("SELECT player_id, pim FROM player_game_logs WHERE game_id = ?",
                          (game_id,)):
        if (r["pim"] or 0) != pim[r["player_id"]]:
            out.append(f"{r['player_id']} pim box={r['pim']} pbp={pim[r['player_id']]}")
    return out


def store(conn, game_id: int, rows: list[dict]) -> int:
    conn.execute("DELETE FROM penalties WHERE game_id = ?", (game_id,))
    conn.executemany(
        """INSERT INTO penalties (game_id, event_id, team_id, period, period_type,
               time_in_period, type_code, desc_key, duration, committed_by, served_by, drawn_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(game_id, r["event_id"], r["team_id"], r["period"], r["period_type"],
          r["time_in_period"], r["type_code"], r["desc_key"], r["duration"],
          r["committed_by"], r["served_by"], r["drawn_by"]) for r in rows])
    return len(rows)

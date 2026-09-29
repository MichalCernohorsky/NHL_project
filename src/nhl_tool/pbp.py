"""Play-by-play -> regulation-only (periods 1-3) shots, blocks and saves.

Tipsport settles player statistics on 60 minutes; the box score counts
overtime too. The play-by-play marks every event with its period type, so
regulation counts are exact. Each game is checked against its box score:
the play-by-play FULL-game count must equal the box score for every player,
otherwise the game is not stored (a partial or corrected feed would put
wrong numbers under a correct-looking column).

Two things the play-by-play records that are NOT player statistics (both
found by that check on the first 20 games of 2025-26):
- shootout attempts (period type 'SO') - not game statistics anywhere;
- 'teammate-blocked' shots - a shot stopped by the shooter's own teammate
  is not a blocked shot of the blocker in the box score.
"""
from __future__ import annotations

from collections import Counter

SOG_EVENTS = ("shot-on-goal", "goal")


def parse_pbp(payload: dict) -> dict:
    sog, sog_reg = Counter(), Counter()
    blk, blk_reg = Counter(), Counter()
    sa_reg, sv_reg = Counter(), Counter()
    for e in payload.get("plays") or []:
        kind = e.get("typeDescKey")
        det = e.get("details") or {}
        period = (e.get("periodDescriptor") or {}).get("periodType")
        if period == "SO":
            continue
        reg = period == "REG"
        if kind in SOG_EVENTS:
            shooter = det.get("shootingPlayerId") if kind == "shot-on-goal" \
                else det.get("scoringPlayerId")
            if shooter:
                sog[shooter] += 1
                sog_reg[shooter] += reg
            goalie = det.get("goalieInNetId")
            if goalie and reg:
                sa_reg[goalie] += 1
                sv_reg[goalie] += kind == "shot-on-goal"
        elif kind == "blocked-shot" and det.get("blockingPlayerId") \
                and det.get("reason") != "teammate-blocked":
            blk[det["blockingPlayerId"]] += 1
            blk_reg[det["blockingPlayerId"]] += reg
    return {"sog": sog, "sog_reg": sog_reg, "blk": blk, "blk_reg": blk_reg,
            "sa_reg": sa_reg, "sv_reg": sv_reg}


def mismatches(conn, game_id: int, parsed: dict) -> list[str]:
    """Players whose full-game play-by-play count differs from the box score."""
    out = []
    for r in conn.execute("SELECT player_id, sog, blocked_shots FROM player_game_logs"
                          " WHERE game_id = ?", (game_id,)):
        pid = r["player_id"]
        if (r["sog"] or 0) != parsed["sog"][pid]:
            out.append(f"{pid} sog box={r['sog']} pbp={parsed['sog'][pid]}")
        if (r["blocked_shots"] or 0) != parsed["blk"][pid]:
            out.append(f"{pid} blk box={r['blocked_shots']} pbp={parsed['blk'][pid]}")
    return out


def store(conn, game_id: int, parsed: dict):
    for r in conn.execute("SELECT player_id FROM player_game_logs WHERE game_id = ?",
                          (game_id,)).fetchall():
        pid = r["player_id"]
        conn.execute("UPDATE player_game_logs SET sog_reg = ?, blocked_shots_reg = ?"
                     " WHERE game_id = ? AND player_id = ?",
                     (parsed["sog_reg"][pid], parsed["blk_reg"][pid], game_id, pid))
    for r in conn.execute("SELECT player_id FROM goalie_game_logs WHERE game_id = ?",
                          (game_id,)).fetchall():
        pid = r["player_id"]
        conn.execute("UPDATE goalie_game_logs SET shots_against_reg = ?, saves_reg = ?"
                     " WHERE game_id = ? AND player_id = ?",
                     (parsed["sa_reg"][pid], parsed["sv_reg"][pid], game_id, pid))

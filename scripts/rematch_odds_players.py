#!/usr/bin/env python3
"""Fill player_id on odds rows that were stored unmatched, now that more is
known (a roster sync, a debut box score). Never changes a row that already
has a player id; reports what is still unmatched. Reads every snapshot kind
on purpose: it repairs ids, it analyses nothing.

Usage:
    python scripts/rematch_odds_players.py
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.odds_import import build_roster_lookup, resolve_player


def main():
    conn = connect(resolve_db_path(load_config()))
    rows = conn.execute("""SELECT DISTINCT game_id, player_name_raw FROM odds
                           WHERE player_id IS NULL AND game_id IS NOT NULL""").fetchall()
    by_game = defaultdict(list)
    for r in rows:
        by_game[r["game_id"]].append(r["player_name_raw"])
    fixed, still = 0, set()
    for gid, names in by_game.items():
        lookup = build_roster_lookup(conn, gid)
        for name in names:
            pid = resolve_player(lookup, name)
            if pid is None:
                still.add(name)
                continue
            fixed += conn.execute("""UPDATE odds SET player_id = ? WHERE game_id = ?
                                     AND player_name_raw = ? AND player_id IS NULL""",
                                  (pid, gid, name)).rowcount
    conn.commit()
    print(f"dosparovano radku: {fixed} | stale nesparovanych jmen: {len(still)}"
          + (f" ({', '.join(sorted(still)[:10])}{', ...' if len(still) > 10 else ''})" if still else ""))


if __name__ == "__main__":
    main()

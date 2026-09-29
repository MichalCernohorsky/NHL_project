#!/usr/bin/env python3
"""What is in the database: games, box scores, TOI split and names per season.
No requests. Screenshot-friendly.

Usage:
    python scripts/report.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

QUERY = """
SELECT g.season,
       COUNT(*)                                                   AS games,
       SUM(g.game_state IN ('OFF', 'FINAL'))                      AS finished,
       SUM(g.last_period_type = 'OT')                             AS ot,
       SUM(g.last_period_type = 'SO')                             AS so,
       COUNT(DISTINCT t.game_id)                                  AS with_box,
       (SELECT COUNT(*) FROM player_game_logs p JOIN games x USING (game_id)
         WHERE x.season = g.season)                               AS skater_rows,
       (SELECT COUNT(*) FROM player_game_logs p JOIN games x USING (game_id)
         WHERE x.season = g.season AND p.pp_toi_s IS NOT NULL)    AS with_pp_toi,
       (SELECT COUNT(*) FROM goalie_game_logs p JOIN games x USING (game_id)
         WHERE x.season = g.season AND p.started = 1)             AS goalie_starts,
       (SELECT COUNT(*) FROM player_game_logs p JOIN games x USING (game_id)
         WHERE x.season = g.season AND p.sog_reg IS NOT NULL)     AS with_sog_60
FROM games g
LEFT JOIN team_game_logs t ON t.game_id = g.game_id AND t.is_home = 1
WHERE g.season_type = 'regular'
GROUP BY g.season ORDER BY g.season
"""


def main():
    conn = connect(resolve_db_path(load_config()))
    rows = conn.execute(QUERY).fetchall()
    head = ("sezona", "zapasu", "odehrano", "OT", "SO", "box score",
            "radku hracu", "s PP TOI", "starty G", "strely 60 min")
    print(" | ".join(head))
    for r in rows:
        print(" | ".join(str(v if v is not None else 0) for v in tuple(r)))
    no_name = conn.execute("SELECT COUNT(*) FROM players WHERE full_name IS NULL").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    print(f"\nhracu: {total}, bez celeho jmena: {no_name}")
    errors = conn.execute(
        "SELECT task, COUNT(*) FROM backfill_state WHERE status = 'error'"
        " GROUP BY task").fetchall()
    print("chyby v backfill_state: "
          + (", ".join(f"{t}={c}" for t, c in errors) if errors else "zadne"))
    odds = conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0]
    print(f"radku kurzu: {odds}")


if __name__ == "__main__":
    main()

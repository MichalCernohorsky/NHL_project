#!/usr/bin/env python3
"""Current rosters of every team of a season -> tables players + rosters.

One request per team (32), meant to run daily for the live season: the
first and last day a player was listed are kept, so a traded player stays
on both teams for name matching of that season's games.

Usage:
    python scripts/backfill_rosters.py                  # live season
    python scripts/backfill_rosters.py --season 2026-27
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import rosters
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.http_client import NotFoundError
from nhl_tool.nhl_client import NhlClient
from nhl_tool.parsing import ET


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season")
    args = ap.parse_args()
    cfg = load_config()
    season = args.season or cfg["live"]["season"]
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    today = datetime.now(ET).date().isoformat()
    teams = conn.execute(
        """SELECT DISTINCT t.team_id, t.abbreviation FROM teams t
           JOIN games g ON t.team_id IN (g.home_team_id, g.away_team_id)
           WHERE g.season = ? AND g.season_type = 'regular'
           ORDER BY t.abbreviation""", (season,)).fetchall()
    n = missing = 0
    for t in teams:
        try:
            payload = client.web(rosters.roster_path(t["abbreviation"], season))
        except NotFoundError:
            missing += 1
            continue
        n += rosters.store(conn, season, t["team_id"], rosters.parse_roster(payload), today)
        conn.commit()
    print(f"{season}: tymu {len(teams)}, hracu na soupiskach {n}, bez soupisky {missing}"
          f" | requestu {client.requests_made}")


if __name__ == "__main__":
    main()

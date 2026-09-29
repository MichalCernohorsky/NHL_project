#!/usr/bin/env python3
"""Season schedules -> tables teams + games (one request per week).

Historical seasons are cached on disk (their schedule cannot change); the
live season is always fetched fresh, because postponements move games.

Usage:
    python scripts/backfill_schedule.py                   # config seasons + live season
    python scripts/backfill_schedule.py --season 2025-26
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.nhl_client import NhlClient
from nhl_tool.schedule import (parse_week, season_bounds, season_probe_date,
                               upsert_games, upsert_teams, week_starts)


def sync_season(conn, client, season: str, live: bool, playoffs: bool) -> int:
    key = None if live else f"schedule/{season}/probe"
    probe = client.web(f"schedule/{season_probe_date(season)}", cache_key=key)
    start, end = season_bounds(probe, include_playoffs=playoffs,
                               include_preseason=live)
    n = 0
    for week in week_starts(start, end):
        key = None if live else f"schedule/{season}/{week}"
        teams, games = parse_week(client.web(f"schedule/{week}", cache_key=key), season)
        upsert_teams(conn, teams)
        upsert_games(conn, games)
        # Commit per week: holding the write lock across ~30 requests
        # (15 s) made a parallel backfill fail with "database is locked".
        conn.commit()
        n += len(games)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append",
                    help="e.g. 2025-26 (repeatable); default: config seasons + live")
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    live = cfg["live"]["season"]
    seasons = args.season or [*cfg["seasons"], live]
    playoffs = bool(cfg["season_types"].get("playoffs"))
    for season in seasons:
        n = sync_season(conn, client, season, live=(season == live), playoffs=playoffs)
        counts = conn.execute(
            "SELECT season_type, COUNT(*) FROM games WHERE season = ?"
            " GROUP BY season_type ORDER BY season_type", (season,)).fetchall()
        print(f"{season}: {n} zapasu v rozpisu | v DB: "
              + ", ".join(f"{t}={c}" for t, c in counts))
    print(f"requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

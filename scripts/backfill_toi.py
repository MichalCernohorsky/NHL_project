#!/usr/bin/env python3
"""EV / PP / SH / OT time on ice + full skater names, one game day per request.

Run AFTER backfill_boxscores.py: it fills columns of rows the box-score step
created. A day is marked done only when every row found its box-score row.

Usage:
    python scripts/backfill_toi.py                   # all config seasons
    python scripts/backfill_toi.py --season 2025-26
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import toi
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.nhl_client import NhlClient

TASK = "toi"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append")
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    seasons = args.season or [*cfg["seasons"], cfg["live"]["season"]]
    done = state_keys(conn, TASK)
    qs = ",".join("?" * len(seasons))
    # Only days whose every regular-season game already has its box score.
    days = [r["game_date"] for r in conn.execute(
        f"""SELECT g.game_date FROM games g
            LEFT JOIN backfill_state b ON b.task = 'boxscore'
                 AND b.key = CAST(g.game_id AS TEXT) AND b.status = 'done'
            WHERE g.season IN ({qs}) AND g.season_type = 'regular'
              AND g.game_state IN ('OFF', 'FINAL')
            GROUP BY g.game_date HAVING COUNT(*) = COUNT(b.key)
            ORDER BY g.game_date""", seasons)]
    todo = [d for d in days if d not in done]
    print(f"hernich dnu s box score: {len(days)} | ke stazeni: {len(todo)}")
    for i, day in enumerate(todo, 1):
        payload = client.stats(toi.REPORT, toi.day_params(day), cache_key=f"toi/{day}")
        rows = toi.parse_rows(payload)
        unmatched = toi.store(conn, rows)
        status = "done" if rows and not unmatched else "error"
        set_state(conn, TASK, day, status, f"rows={len(rows)} unmatched={unmatched}")
        conn.commit()
        if status == "error":
            print(f"  {day}: radku {len(rows)}, bez box score {unmatched}")
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} dnu")
    print(f"requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

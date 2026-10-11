#!/usr/bin/env python3
"""NHL corrections after a game (docs/models_v2_notes.md, amendment N-3).

Every regular game of the live season is read again (box score and
play-by-play, never from the cache) once a UTC day while it is 1-10 days
old, and any game a step left in error whatever its age. When something
stored differs and the fresh feed passes the usual checks, the game is
marked 'stale' and the steps after this one in the daily run download it
again with all their checks. Each check and each changed value is logged
(stat_checks, stat_corrections). Run BEFORE backfill_boxscores.py.

Usage:
    python scripts/check_corrections.py                  # live season
    python scripts/check_corrections.py --season 2026-27
"""
import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import boxscore, corrections
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.nhl_client import NhlClient


def check_game(conn, client, g, today: str) -> tuple[str, list[dict], str | None]:
    """(action, differences, detail) for one candidate game; marks it stale
    when it is to be downloaded again."""
    gid = g["game_id"]
    box = client.web(f"gamecenter/{gid}/boxscore")                  # no cache key: always fresh
    if not boxscore.is_finished(box):
        return "unfinished", [], box.get("gameState")
    diffs, problems = corrections.check(conn, gid, box, client.web(f"gamecenter/{gid}/play-by-play"))
    if not diffs:
        return "same", [], None
    if problems:
        return "inconsistent", diffs, "; ".join(problems)[:200]
    corrections.invalidate(conn, gid, g["game_date"], client.cache_dir, f"oprava NHL {today}")
    return "refreshed", diffs, corrections.summary(diffs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append")
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    seasons = args.season or [cfg["live"]["season"]]
    today = datetime.now(timezone.utc).date().isoformat()
    todo = corrections.candidates(conn, seasons, today)
    print(f"zapasu ke kontrole oprav NHL: {len(todo)} (1-{corrections.WINDOW_DAYS} dni po zapase"
          f" + zapasy s chybou)")
    n = Counter()
    for g in todo:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            action, diffs, detail = check_game(conn, client, g, today)
        except KeyboardInterrupt:
            conn.commit()
            print("\npreruseno - postup ulozen")
            raise
        except Exception as exc:  # noqa: BLE001 - logged, tried again at the next run
            action, diffs, detail = "error", [], f"{type(exc).__name__}: {exc}"[:200]
        corrections.record(conn, g["game_id"], stamp, g["age_days"], action, diffs, detail)
        conn.commit()
        n[action] += 1
        if action != "same":
            print(f"  {g['game_id']} ({g['age_days']} d) {action}: {detail}")
    print(f"beze zmeny: {n['same']} | obnoveno: {n['refreshed']} | oprava u NHL rozpracovana:"
          f" {n['inconsistent']} | chyby: {n['error']} | requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

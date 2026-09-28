#!/usr/bin/env python3
"""Box scores + scratches of finished games -> player/goalie/team game logs.

Two requests per game (boxscore, right-rail), resumable: a game marked done
in backfill_state is never downloaded again, and raw JSON of finished games
is cached, so an interrupted run loses nothing. Run backfill_schedule.py
first.

Usage:
    python scripts/backfill_boxscores.py                  # all config seasons
    python scripts/backfill_boxscores.py --season 2025-26
    python scripts/backfill_boxscores.py --season 2025-26 --limit 20   # quick test
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import boxscore
from nhl_tool.config import (enabled_season_types, load_config, resolve_cache_dir,
                             resolve_db_path)
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.http_client import NotFoundError
from nhl_tool.nhl_client import NhlClient

TASK = "boxscore"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append")
    ap.add_argument("--limit", type=int, default=0, help="stop after N games (0 = all)")
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    seasons = args.season or [*cfg["seasons"], cfg["live"]["season"]]
    types = enabled_season_types(cfg)
    done = state_keys(conn, TASK, statuses=("done", "missing"))

    qs, qt = ",".join("?" * len(seasons)), ",".join("?" * len(types))
    games = conn.execute(
        f"""SELECT game_id, season, home_team_id, away_team_id FROM games
            WHERE season IN ({qs}) AND season_type IN ({qt})
              AND game_state IN ('OFF', 'FINAL')
            ORDER BY game_date, game_id""", (*seasons, *types)).fetchall()
    todo = [g for g in games if str(g["game_id"]) not in done]
    print(f"odehranych zapasu: {len(games)} | hotovo: {len(games) - len(todo)}"
          f" | ke stazeni: {len(todo)} (~{2 * len(todo)} requestu)")
    if args.limit:
        todo = todo[:args.limit]
        print(f"--limit: tento beh jen {len(todo)} zapasu")

    n_ok = n_missing = n_err = 0
    for i, g in enumerate(todo, 1):
        gid = g["game_id"]
        try:
            box = client.web(f"gamecenter/{gid}/boxscore", cache_key=f"boxscore/{gid}",
                             keep=boxscore.is_finished)
            if not boxscore.is_finished(box):
                continue  # final score not official yet; next run picks it up
            rail = client.web(f"gamecenter/{gid}/right-rail", cache_key=f"right_rail/{gid}")
            parsed = boxscore.parse_boxscore(box)
            scratches = boxscore.parse_scratches(rail, gid, g["home_team_id"],
                                                 g["away_team_id"])
            boxscore.store(conn, parsed, scratches)
            set_state(conn, TASK, str(gid), "done",
                      f"skaters={len(parsed['skaters'])} goalies={len(parsed['goalies'])}")
            n_ok += 1
        except KeyboardInterrupt:
            conn.commit()
            print("\npreruseno - postup ulozen, spust znovu pro pokracovani")
            raise
        except NotFoundError as exc:
            set_state(conn, TASK, str(gid), "missing", str(exc)[:200])
            n_missing += 1
        except Exception as exc:  # noqa: BLE001 - mark and move on, resumable
            set_state(conn, TASK, str(gid), "error", f"{type(exc).__name__}: {exc}"[:200])
            n_err += 1
            print(f"  CHYBA {gid}: {type(exc).__name__}: {exc}")
        conn.commit()
        if i % 100 == 0:
            print(f"  {i}/{len(todo)} zapasu")
    print(f"hotovo: {n_ok} | chybi upstream: {n_missing} | chyby: {n_err}"
          f" | requestu: {client.requests_made}")
    if n_err:
        print("Chyby jsou v backfill_state (status='error'); dalsi beh je zkusi znovu.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Referees and linesmen of finished games (docs/team_markets_plan.md, step 2).

Reads the game page's right rail - the same file backfill_boxscores.py
already cached, so on a machine with the raw cache this makes no request.
A finished game that lists no referee is fetched once more without the
cache and, if still empty, marked 'error' so that a later run retries.

Usage:
    python scripts/backfill_officials.py                   # all config seasons
    python scripts/backfill_officials.py --season 2025-26 --limit 20
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import officials
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.http_client import NotFoundError
from nhl_tool.nhl_client import NhlClient

TASK = "officials"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    seasons = args.season or [*cfg["seasons"], cfg["live"]["season"]]
    done = state_keys(conn, TASK, statuses=("done", "missing"))
    qs = ",".join("?" * len(seasons))
    games = [r[0] for r in conn.execute(
        f"""SELECT g.game_id FROM games g
            JOIN backfill_state b ON b.task = 'boxscore'
                 AND b.key = CAST(g.game_id AS TEXT) AND b.status = 'done'
            WHERE g.season IN ({qs}) AND g.season_type = 'regular'
            ORDER BY g.game_date, g.game_id""", seasons)]
    todo = [g for g in games if str(g) not in done]
    print(f"zapasu s box score: {len(games)} | ke zpracovani: {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
    n_ok = n_err = 0
    for i, gid in enumerate(todo, 1):
        try:
            path = f"gamecenter/{gid}/right-rail"
            found = officials.parse_officials(client.web(path, cache_key=f"right_rail/{gid}"))
            if not any(role == "referee" for role, _ in found):
                found = officials.parse_officials(client.web(path))      # fresh, no cache
            if not any(role == "referee" for role, _ in found):
                set_state(conn, TASK, str(gid), "error", "no referee listed")
                n_err += 1
                print(f"  BEZ ROZHODCICH {gid}")
            else:
                officials.store(conn, gid, found)
                set_state(conn, TASK, str(gid), "done", f"officials={len(found)}")
                n_ok += 1
        except KeyboardInterrupt:
            conn.commit()
            print("\npreruseno - postup ulozen, spust znovu pro pokracovani")
            raise
        except NotFoundError as exc:
            set_state(conn, TASK, str(gid), "missing", str(exc)[:200])
        except Exception as exc:  # noqa: BLE001 - mark and move on, resumable
            set_state(conn, TASK, str(gid), "error", f"{type(exc).__name__}: {exc}"[:200])
            n_err += 1
            print(f"  CHYBA {gid}: {type(exc).__name__}: {exc}")
        conn.commit()
        if i % 500 == 0:
            print(f"  {i}/{len(todo)} zapasu", flush=True)
    print(f"hotovo: {n_ok} | bez rozhodcich / chyby: {n_err} | requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

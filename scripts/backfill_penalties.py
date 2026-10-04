#!/usr/bin/env python3
"""Penalty events from play-by-play (docs/team_markets_plan.md, step 2).

One request per game, resumable. Every game is checked against its box
score first (each skater's penalty minutes); a mismatch is marked 'error'
and nothing is written for that game. Run after backfill_boxscores.py.

Usage:
    python scripts/backfill_penalties.py                   # all config seasons
    python scripts/backfill_penalties.py --season 2025-26 --limit 20
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import penalties
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.http_client import NotFoundError
from nhl_tool.nhl_client import NhlClient

TASK = "penalties"


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
    print(f"zapasu s box score: {len(games)} | ke stazeni: {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
    n_ok = n_err = n_rows = 0
    for i, gid in enumerate(todo, 1):
        try:
            rows = penalties.parse_penalties(client.web(f"gamecenter/{gid}/play-by-play"))
            bad = penalties.incomplete(rows) or penalties.mismatches(conn, gid, rows)
            if bad:
                set_state(conn, TASK, str(gid), "error", "; ".join(bad)[:200])
                n_err += 1
                print(f"  NESEDI s box score {gid}: {bad[:2]}")
            else:
                n_rows += penalties.store(conn, gid, rows)
                set_state(conn, TASK, str(gid), "done", f"rows={len(rows)}")
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
        if i % 100 == 0:
            print(f"  {i}/{len(todo)} zapasu", flush=True)
    print(f"hotovo: {n_ok} | trestu: {n_rows} | nesedi / chyby: {n_err} | "
          f"requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

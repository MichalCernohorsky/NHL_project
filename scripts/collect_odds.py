#!/usr/bin/env python3
"""Live odds for today's NHL games (US/Eastern date).

    python scripts/collect_odds.py morning           # 16:00 CZ = 10:00 ET
    python scripts/collect_odds.py closing --watch   # evening; sleeps to puck drop -10 min
    python scripts/collect_odds.py status            # no credits

Each run first refreshes this week's schedule from the NHL API (free), so
postponed games and moved start times are respected. Credits: ~3 per game
per snapshot with the three phase 0 markets (markets returned x region us).
Stops below odds.reserve_live credits. Nothing here decides a bet.
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import odds_live
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.nhl_client import NhlClient
from nhl_tool.parsing import ET
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams


def refresh_schedule(conn, cfg, game_date: str):
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    teams, games = parse_week(client.web(f"schedule/{game_date}"), cfg["live"]["season"])
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    conn.commit()


def print_stats(kind, stats, client):
    print(f"{kind}: zapasu {stats['games']}, radku {stats['rows']},"
          f" bez eventu {stats['missing']}, nesparovanych jmen {len(stats['unmatched'])}"
          f" | zustatek {client.last_remaining}")
    if stats.get("stopped_reserve"):
        print("STOP: zustatek pod rezervou (odds.reserve_live).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("morning", "closing", "status"))
    ap.add_argument("--watch", action="store_true",
                    help="closing: keep running until every game of the day is priced")
    ap.add_argument("--date", help="ET game date (default: today in US/Eastern)")
    ap.add_argument("--early-minutes", type=int, default=odds_live.EARLY_MIN,
                    help="closing: price up to this many minutes before the closing "
                         "moment (cloud job every 10 min: 20)")
    ap.add_argument("--repeat", action="store_true",
                    help="closing: price again games already priced (cloud: the "
                         "LAST snapshot before puck drop is the closing line)")
    ap.add_argument("--changed-flag", metavar="PATH",
                    help="touch this file when any odds row was written")
    args = ap.parse_args()

    cfg = load_config()
    oc = cfg["odds"]
    conn = connect(resolve_db_path(cfg))
    game_date = args.date or datetime.now(ET).date().isoformat()
    refresh_schedule(conn, cfg, game_date)
    games = odds_live.todays_games(conn, game_date)

    if args.kind == "status":
        for kind in ("morning", "closing"):
            done = odds_live.done_keys(conn, kind)
            n = sum(str(g["game_id"]) in done for g in games)
            print(f"{game_date} {kind}: {n}/{len(games)} zapasu")
        return

    from nhl_tool.odds_client import OddsClient
    client = OddsClient()
    minutes, window = oc["closing_minutes_before_start"], oc["closing_window_minutes"]
    print(f"{game_date}: {len(games)} zapasu v rozpisu | trhy {', '.join(oc['markets'])}")
    while True:
        now = odds_live.utc_now()
        done = set() if (args.repeat and args.kind == "closing") \
            else odds_live.done_keys(conn, args.kind)
        due = odds_live.due_now(games, done, now, args.kind, minutes, window,
                                early_min=args.early_minutes)
        if due:
            stats = odds_live.collect(conn, client, due, kind=args.kind, oc=oc, now=now)
            print_stats(args.kind, stats, client)
            if stats["rows"] and args.changed_flag:
                Path(args.changed_flag).touch()
            if stats.get("stopped_reserve"):
                return
        if args.kind == "morning" or not args.watch:
            return
        wake = odds_live.next_wakeup(games, odds_live.done_keys(conn, args.kind),
                                     odds_live.utc_now(), minutes)
        if wake is None:
            print("closing: vsechny zapasy dne ocenene, konec.")
            return
        wait = (wake - odds_live.utc_now()).total_seconds()
        print(f"  cekam do {wake.astimezone(ET):%H:%M} ET ({wait / 60:.0f} min)")
        time.sleep(max(1.0, wait))


if __name__ == "__main__":
    main()

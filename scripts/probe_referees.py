#!/usr/bin/env python3
"""When does the NHL API know tonight's referees? (docs/team_markets_plan.md,
section 3). For every game that has not started and starts within 36 hours,
record how many referees the right rail lists right now. Part of the daily
job; one request per upcoming game, never cached.

Usage:
    python scripts/probe_referees.py
    python scripts/probe_referees.py --report      # what the probes say so far
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import officials
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.nhl_client import NhlClient

HORIZON_H = 36


def report(conn) -> None:
    rows = conn.execute(
        """SELECT game_id, start_time_utc, checked_at, referees FROM referee_probe
           ORDER BY start_time_utc, game_id, checked_at""").fetchall()
    print(f"zaznamu: {len(rows)}")
    for r in rows:
        lead = (datetime.fromisoformat(r["start_time_utc"].replace("Z", "+00:00"))
                - datetime.fromisoformat(r["checked_at"])).total_seconds() / 3600
        print(f"  {r['game_id']} zacatek {r['start_time_utc']} | {lead:5.1f} h predem | "
              f"rozhodcich {r['referees']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    if args.report:
        report(conn)
        return
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    now = datetime.now(timezone.utc)
    lo = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (now + timedelta(hours=HORIZON_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
    games = conn.execute(
        """SELECT game_id, start_time_utc FROM games
           WHERE season_type = 'regular' AND start_time_utc > ? AND start_time_utc <= ?
           ORDER BY start_time_utc""", (lo, hi)).fetchall()
    checked_at = now.isoformat(timespec="seconds")
    known = 0
    for g in games:
        rail = client.web(f"gamecenter/{g['game_id']}/right-rail")
        n = officials.probe(conn, g["game_id"], g["start_time_utc"], rail, checked_at)
        known += n > 0
    conn.commit()
    print(f"{checked_at}: zapasu do {HORIZON_H} h: {len(games)} | rozhodci uz znami u: {known}")


if __name__ == "__main__":
    main()

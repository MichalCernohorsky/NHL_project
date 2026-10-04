#!/usr/bin/env python3
"""Daily run for the live season: schedule -> box scores -> TOI split ->
names -> 60-minute counts -> penalties -> officials -> referee probe. Idempotent and resumable: a second run the same
day downloads only what is new (finished games since the last run).

Every step runs even when an earlier one failed (a failed TOI day must not
stop the play-by-play of games that are fine); the exit code is non-zero
when any step failed, so the launchd wrapper raises a notification.

Nothing here touches odds or decides a bet - odds have their own jobs
(make odds-morning / odds-closing).

Usage:
    python scripts/daily_collect.py
    python scripts/daily_collect.py --steps schedule,boxscores
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config

# (name, script, takes --season)
STEPS = [
    ("schedule", "backfill_schedule.py", True),
    ("rosters", "backfill_rosters.py", True),
    ("boxscores", "backfill_boxscores.py", True),
    ("toi", "backfill_toi.py", True),
    ("players", "backfill_players.py", False),
    ("pbp", "backfill_pbp.py", True),
    # team markets plan, step 2: penalty events, officials of finished games,
    # and whether tonight's referees are already known
    ("penalties", "backfill_penalties.py", True),
    ("officials", "backfill_officials.py", True),
    ("refprobe", "probe_referees.py", False),
    ("rematch", "rematch_odds_players.py", False),
]


def commands(season: str, only: set[str] | None = None) -> list[tuple[str, list[str]]]:
    out = []
    for name, script, seasonal in STEPS:
        if only and name not in only:
            continue
        cmd = [sys.executable, str(ROOT / "scripts" / script)]
        if seasonal:
            cmd += ["--season", season]
        out.append((name, cmd))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", help="comma-separated subset of: "
                    + ",".join(s[0] for s in STEPS))
    args = ap.parse_args()
    season = load_config()["live"]["season"]
    only = set(args.steps.split(",")) if args.steps else None
    failed = []
    for name, cmd in commands(season, only):
        t0 = time.monotonic()
        print(f"\n=== {name} ({season}) ===", flush=True)
        rc = subprocess.call(cmd, cwd=ROOT)
        print(f"=== {name}: kod {rc}, {time.monotonic() - t0:.0f} s ===", flush=True)
        if rc != 0:
            failed.append(name)
    if failed:
        print(f"\nSELHALY KROKY: {', '.join(failed)}")
        sys.exit(1)
    print("\ndenni beh hotov, vsechny kroky OK")


if __name__ == "__main__":
    main()

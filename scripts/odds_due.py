#!/usr/bin/env python3
"""Cheap gate for the cloud odds job: is there anything to price NOW?

Standard library only (runs before any pip install or database download):
asks the free NHL schedule for today's ET game date and prints one of
    morning   10:00-11:59 ET and a game still to start today
    closing   a game starts within the next CLOSING_AHEAD_MIN minutes
    none
When both apply, 'closing' wins (it is time-critical; the next run in ten
minutes still falls in the morning window). In GitHub Actions the result
also goes to $GITHUB_OUTPUT as due=<value>.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MORNING_FROM, MORNING_TO = 10, 12          # hours ET, [from, to)
CLOSING_AHEAD_MIN = 30                     # cron every 10 min + GitHub delays


def starts_today(now_et: datetime) -> list[datetime]:
    url = f"https://api-web.nhle.com/v1/schedule/{now_et.date().isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "nhl-tool research"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    day = next((d for d in payload.get("gameWeek", [])
                if d["date"] == now_et.date().isoformat()), {"games": []})
    return [datetime.fromisoformat(g["startTimeUTC"].replace("Z", "+00:00"))
            for g in day["games"]
            if g.get("gameType") in (2, 3) and g.get("gameScheduleState", "OK") == "OK"]


def decide(now_utc: datetime, starts: list[datetime]) -> str:
    ahead = [s for s in starts if s > now_utc]
    if any(s - now_utc <= timedelta(minutes=CLOSING_AHEAD_MIN) for s in ahead):
        return "closing"
    if ahead and MORNING_FROM <= now_utc.astimezone(ET).hour < MORNING_TO:
        return "morning"
    return "none"


def main():
    now = datetime.now(timezone.utc)
    try:
        due = decide(now, starts_today(now.astimezone(ET)))
    except Exception as exc:  # noqa: BLE001 - a dead gate must not spend credits
        print(f"brana: rozpis se nepodarilo nacist ({type(exc).__name__}) -> none")
        due = "none"
    print(f"brana: {due}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"due={due}\n")


if __name__ == "__main__":
    sys.exit(main())

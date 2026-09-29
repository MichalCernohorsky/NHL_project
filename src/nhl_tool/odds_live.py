"""Live odds snapshots for the running season: 'morning' and 'closing'.

Morning = one pass over the day's games at 10:00 ET (16:00 CZ), the entry
snapshot. Closing = puck drop minus 10 min per game; the watcher sleeps
between puck drops. Live event odds cost markets RETURNED x regions (no 10x
historical multiplier); the events list is free.

Nothing here decides a bet. Phase 0 only lets the dataset grow so that
phase 2 has 2026-27 lines to validate on.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .db import set_state, state_keys
from .odds_import import build_roster_lookup, find_event, insert_odds_rows, parse_event_odds


EARLY_MIN = 2


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def task(kind: str) -> str:
    return f"live_odds:{kind}"


def todays_games(conn, game_date: str):
    return conn.execute(
        """SELECT g.game_id, g.game_date, g.start_time_utc,
                  ht.full_name AS home, at.full_name AS away
           FROM games g
           JOIN teams ht ON ht.team_id = g.home_team_id
           JOIN teams at ON at.team_id = g.away_team_id
           WHERE g.game_date = ? AND g.season_type IN ('regular', 'playoffs')
             AND g.start_time_utc IS NOT NULL
             AND COALESCE(g.schedule_state, 'OK') = 'OK'
           ORDER BY g.start_time_utc""", (game_date,)).fetchall()


def closing_moment(start_utc: str, minutes_before: int) -> datetime:
    return parse_iso(start_utc) - timedelta(minutes=minutes_before)


def due_now(games, done: set[str], now: datetime, kind: str,
            minutes_before: int, window_min: int, early_min: int = EARLY_MIN):
    """Games to price in this pass.

    morning: every game not started yet. closing: games whose closing moment
    (puck drop - minutes_before) has come - up to early_min early (clock
    drift; the cloud job runs every 10 min and passes a larger value) - and
    passed by at most window_min, and ALWAYS strictly before puck drop: a
    price from a game already under way is not a closing line. (Before
    29. 9. the window alone allowed up to 10 min after puck drop.)"""
    out = []
    for g in games:
        if str(g["game_id"]) in done:
            continue
        start = parse_iso(g["start_time_utc"])
        if now >= start:
            continue
        if kind == "morning":
            out.append(g)
            continue
        moment = closing_moment(g["start_time_utc"], minutes_before)
        late = (now - moment).total_seconds()
        if -early_min * 60 <= late <= window_min * 60:
            out.append(g)
    return out


def next_wakeup(games, done: set[str], now: datetime, minutes_before: int):
    """Earliest future closing moment of a game not priced yet, or None."""
    future = [closing_moment(g["start_time_utc"], minutes_before) for g in games
              if str(g["game_id"]) not in done
              and closing_moment(g["start_time_utc"], minutes_before) > now]
    return min(future) if future else None


def collect(conn, client, games, *, kind: str, oc: dict, now: datetime) -> dict:
    """Price the given games once. Returns counts for the status line."""
    events, _ = client.get(f"/sports/{oc['sport']}/events")
    stats = {"games": 0, "rows": 0, "missing": 0, "unmatched": set()}
    for g in games:
        if (client.last_remaining or 1e9) <= oc["reserve_live"]:
            stats["stopped_reserve"] = True
            break
        event_id = find_event(events, g["home"], g["away"], g["start_time_utc"])
        if event_id is None:
            set_state(conn, task(kind), str(g["game_id"]), "missing", "event not listed")
            stats["missing"] += 1
            continue
        payload, _ = client.get(
            f"/sports/{oc['sport']}/events/{event_id}/odds",
            regions=oc["regions"], markets=",".join(oc["markets"]), oddsFormat="decimal")
        roster = build_roster_lookup(conn, g["game_id"])
        total = 0
        for market in oc["markets"]:
            rows = parse_event_odds(payload, market)
            n, unmatched = insert_odds_rows(
                conn, rows, event_id=event_id, game_id=g["game_id"], market=market,
                snapshot_time=iso(now), snapshot_kind=kind, roster=roster)
            total += n
            stats["unmatched"] |= unmatched
        set_state(conn, task(kind), str(g["game_id"]), "done", f"rows={total}")
        conn.commit()
        stats["games"] += 1
        stats["rows"] += total
    conn.commit()
    return stats


def done_keys(conn, kind: str) -> set[str]:
    return state_keys(conn, task(kind), statuses=("done", "missing"))

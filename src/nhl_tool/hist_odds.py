"""Buying ONE historical snapshot of ONE game from The Odds API archive.

Shared by scripts/backfill_props.py (the phase 0 sample of 2025-26) and
scripts/buy_snapshots.py (the live season, bought the day after - plan
amendment D4). Same snapshot anchors for both, fixed in the plan before any
row was bought: 'morning' = 10:00 US/Eastern on the game day, 'closing' =
puck drop minus 10 minutes.

CREDITS (v4 docs, measured on this account by NBA): historical event odds =
10 x markets RETURNED x regions; a market no book quotes costs nothing. The
historical events list = 1 credit per call, reused for all games of a day.
"""
from __future__ import annotations

from .odds_import import build_roster_lookup, find_event, insert_odds_rows, parse_event_odds
from .parsing import et_time_to_utc, minus_minutes

CREDITS_PER_MARKET_REGION = 10
KINDS = ("morning", "closing")


def snapshot_for(kind: str, start_utc: str, game_date: str, oc: dict) -> str:
    """UTC ISO of the moment to price."""
    if kind == "morning":
        return et_time_to_utc(game_date, oc["morning_et"])
    return minus_minutes(start_utc, oc["closing_minutes_before_start"])


class HistoricalBuyer:
    """Prices games one snapshot at a time; caches the day's events list."""

    def __init__(self, conn, client, oc: dict, markets: list[str], cache_fn=None):
        self.conn, self.client, self.oc, self.markets = conn, client, oc, markets
        self.cache_fn = cache_fn
        self.events_by_day: dict = {}

    def _events_at(self, iso: str):
        payload, _ = self.client.get(f"/historical/sports/{self.oc['sport']}/events", date=iso)
        return payload

    def event_id(self, game, snap: str) -> str | None:
        day = game["game_date"]
        if day not in self.events_by_day:
            payload = self._events_at(et_time_to_utc(day, self.oc["morning_et"]))
            if self.cache_fn:
                self.cache_fn("events", day, payload)
            self.events_by_day[day] = payload
        eid = find_event(self.events_by_day[day], game["home"], game["away"],
                         game["start_time_utc"])
        if eid is None:            # e.g. not listed yet at the morning anchor
            eid = find_event(self._events_at(snap), game["home"], game["away"],
                             game["start_time_utc"])
        return eid

    def price(self, game, kind: str) -> dict:
        """Buy one snapshot of one game. -> {status, detail, rows, unmatched}.

        status 'missing' (no credit spent on odds) when the snapshot would
        not be before puck drop or the event is not in the archive; 'done'
        when at least one row was stored, else 'missing'."""
        snap = snapshot_for(kind, game["start_time_utc"], game["game_date"], self.oc)
        if snap >= game["start_time_utc"]:
            return {"status": "missing", "detail": "snapshot not before puck drop",
                    "rows": {}, "unmatched": set()}
        eid = self.event_id(game, snap)
        if eid is None:
            return {"status": "missing", "detail": "event not found",
                    "rows": {}, "unmatched": set()}
        payload, _ = self.client.get(
            f"/historical/sports/{self.oc['sport']}/events/{eid}/odds",
            date=snap, regions=self.oc["regions"], markets=",".join(self.markets),
            oddsFormat="decimal")
        if self.cache_fn:
            self.cache_fn("event_odds", f"{game['game_id']}_{kind}_{'_'.join(self.markets)}",
                          payload)
        roster = build_roster_lookup(self.conn, game["game_id"])
        rows, unmatched = {}, set()
        for market in self.markets:
            parsed = parse_event_odds(payload.get("data", {}), market)
            n, miss = insert_odds_rows(
                self.conn, parsed, event_id=eid, game_id=game["game_id"], market=market,
                snapshot_time=payload.get("timestamp", snap), snapshot_kind=kind,
                roster=roster)
            rows[market] = n
            unmatched |= miss
        total = sum(rows.values())
        return {"status": "done" if total else "missing",
                "detail": " ".join(f"{m}={n}" for m, n in rows.items()),
                "rows": rows, "unmatched": unmatched}

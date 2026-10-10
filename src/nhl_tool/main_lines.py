"""Main lines of a game (moneyline and total goals) from The Odds API:
the snapshot purchase of models v2, block B (docs/models_v2_plan.md 2).

One historical call returns every listed game at one moment:
    GET /historical/sports/{sport}/odds?date=...&markets=h2h,totals&regions=us
and costs 10 x markets x regions = 20 credits, whatever the number of
games. The anchor is 15:00 UTC of the game day; a game that had started by
the snapshot's own timestamp gets no rows.
"""
from __future__ import annotations

from .odds_import import find_event, normalize_name

MARKETS = ("h2h", "totals")
ANCHOR_UTC = "15:00:00"
CREDITS_PER_CALL = 10 * len(MARKETS)          # one region
TASK = "main_lines:day"


def anchor(game_date: str) -> str:
    return f"{game_date}T{ANCHOR_UTC}Z"


def estimate(days: int) -> int:
    return days * CREDITS_PER_CALL


def parse_event(event: dict) -> list[dict]:
    """One event of a featured-odds payload -> rows {bookmaker, market, side,
    line, price}. Moneyline sides are 'home' / 'away' by the event's teams."""
    home, away = normalize_name(event.get("home_team")), normalize_name(event.get("away_team"))
    rows = []
    for bm in event.get("bookmakers") or []:
        for market in bm.get("markets") or []:
            key = market.get("key")
            if key not in MARKETS:
                continue
            for o in market.get("outcomes") or []:
                if o.get("price") is None:
                    continue
                name = normalize_name(o.get("name"))
                if key == "h2h":
                    side = "home" if name == home else "away" if name == away else None
                    line = None
                else:
                    side = name if name in ("over", "under") else None
                    line = o.get("point")
                    if line is None:
                        continue
                if side is None:
                    continue
                rows.append({"bookmaker": bm["key"], "market": key, "side": side,
                             "line": None if line is None else float(line),
                             "price": float(o["price"])})
    return rows


def store_snapshot(conn, payload: dict, games: list, kind: str = "day") -> dict:
    """Store the rows of `games` (dicts with game_id, home, away,
    start_time_utc) found in one snapshot payload. Games that had started by
    the snapshot's timestamp are skipped. -> {matched, started, rows}."""
    events = payload.get("data") or []
    by_id = {e["id"]: e for e in events}
    stamp = payload.get("timestamp")
    out = {"matched": 0, "started": 0, "rows": 0}
    for g in games:
        if not stamp or g["start_time_utc"] <= stamp:
            out["started"] += 1
            continue
        eid = find_event(events, g["home"], g["away"], g["start_time_utc"])
        if eid is None:
            continue
        rows = parse_event(by_id[eid])
        out["matched"] += bool(rows)
        for r in rows:
            out["rows"] += conn.execute(
                """INSERT OR IGNORE INTO main_odds (game_id, event_id, bookmaker, market, side,
                       line, price, snapshot_time, snapshot_kind)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g["game_id"], eid, r["bookmaker"], r["market"], r["side"], r["line"],
                 r["price"], stamp, kind)).rowcount
    return out


def days_to_buy(conn, seasons: list[str]) -> dict[str, list]:
    """Game day -> its finished regular-season games (with team names)."""
    marks = ",".join("?" * len(seasons))
    out: dict[str, list] = {}
    for g in conn.execute(
            f"""SELECT g.game_id, g.game_date, g.start_time_utc,
                       ht.full_name AS home, at.full_name AS away
                FROM games g
                JOIN teams ht ON ht.team_id = g.home_team_id
                JOIN teams at ON at.team_id = g.away_team_id
                WHERE g.season IN ({marks}) AND g.season_type = 'regular'
                  AND g.game_state IN ('OFF', 'FINAL') AND g.start_time_utc IS NOT NULL
                ORDER BY g.game_date, g.start_time_utc""", list(seasons)):
        out.setdefault(g["game_date"], []).append(dict(g))
    return out

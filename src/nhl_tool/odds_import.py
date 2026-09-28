"""The Odds API payloads -> rows of the odds table.

Three jobs: flatten an event-odds payload, find the event of one of our
games, and map the printed player name onto a player id. Matching is
restricted to the two teams of the game, and an ambiguous name is left
unmatched: unmatched is better than wrongly matched (NBA odds_import).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b")


def normalize_name(name: str | None) -> str:
    """'Montréal Canadiens' -> 'montreal canadiens'; 'St. Louis' -> 'st louis';
    "J.J. Moser" -> 'jj moser'; 'Tim Stützle' -> 'tim stutzle'."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace(".", "").replace("'", "").replace("-", " ")
    s = _SUFFIX.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_event_odds(event_data: dict, market_key: str) -> list[dict]:
    """One event-odds payload -> [{bookmaker, player_name, side, line, price}]."""
    rows = []
    for bm in event_data.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("description")
                side = (outcome.get("name") or "").lower()
                if not name or side not in ("over", "under"):
                    continue
                if outcome.get("point") is None or outcome.get("price") is None:
                    continue
                rows.append({"bookmaker": bm["key"], "player_name": name,
                             "side": side, "line": float(outcome["point"]),
                             "price": float(outcome["price"])})
    return rows


def _parse_utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _nickname(full: str) -> str:
    return normalize_name(full).split(" ")[-1] if full else ""


def find_event(events, home: str, away: str, start_utc: str | None,
               max_hours: float = 6.0) -> str | None:
    """Event id for (home, away) starting near start_utc.

    Exact normalized full names first; then the nickname ('Blues', 'Mammoth')
    of both teams, which survives place-name spellings such as 'St Louis' vs
    'St. Louis'. Always within max_hours of our start time, so a team's
    other game in the same snapshot cannot be picked up."""
    items = events.get("data", events) if isinstance(events, dict) else events
    target = _parse_utc(start_utc) if start_utc else None

    def near(ev):
        if target is None or not ev.get("commence_time"):
            return True
        return abs((_parse_utc(ev["commence_time"]) - target).total_seconds()) \
            <= max_hours * 3600

    h, a = normalize_name(home), normalize_name(away)
    for ev in items or []:
        if normalize_name(ev.get("home_team")) == h and \
                normalize_name(ev.get("away_team")) == a and near(ev):
            return ev["id"]
    hn, an = _nickname(home), _nickname(away)
    for ev in items or []:
        if _nickname(ev.get("home_team")) == hn and \
                _nickname(ev.get("away_team")) == an and near(ev):
            return ev["id"]
    return None


def build_roster_lookup(conn, game_id: int) -> dict[str, int]:
    """Normalized full name -> player_id over everyone who appeared for
    either team of the game in that season or the previous one (box
    scores), so rookies and trades are covered once they have played."""
    g = conn.execute("SELECT season, home_team_id, away_team_id FROM games"
                     " WHERE game_id = ?", (game_id,)).fetchone()
    if g is None:
        return {}
    start = int(g["season"][:4])
    seasons = (g["season"], f"{start - 1}-{str(start)[2:]}")
    rows = conn.execute(
        """SELECT DISTINCT p.player_id, p.full_name FROM players p
           JOIN (SELECT player_id, team_id, game_id FROM player_game_logs
                 UNION ALL
                 SELECT player_id, team_id, game_id FROM goalie_game_logs) l
             ON l.player_id = p.player_id
           JOIN games x ON x.game_id = l.game_id
           WHERE l.team_id IN (?, ?) AND x.season IN (?, ?)
             AND p.full_name IS NOT NULL""",
        (g["home_team_id"], g["away_team_id"], *seasons)).fetchall()
    lookup, ambiguous = {}, set()
    for r in rows:
        key = normalize_name(r["full_name"])
        if key in lookup and lookup[key] != r["player_id"]:
            ambiguous.add(key)
        lookup[key] = r["player_id"]
    for key in ambiguous:
        del lookup[key]
    return lookup


def insert_odds_rows(conn, rows, *, event_id: str, game_id: int | None, market: str,
                     snapshot_time: str, snapshot_kind: str,
                     roster: dict[str, int]) -> tuple[int, set[str]]:
    """-> (rows inserted, names that matched no player)."""
    unmatched, inserted = set(), 0
    for r in rows:
        pid = roster.get(normalize_name(r["player_name"]))
        if pid is None:
            unmatched.add(r["player_name"])
        cur = conn.execute(
            """INSERT OR IGNORE INTO odds (event_id, game_id, player_id,
                   player_name_raw, market, side, line, price, bookmaker,
                   snapshot_time, snapshot_kind)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, game_id, pid, r["player_name"], market, r["side"],
             r["line"], r["price"], r["bookmaker"], snapshot_time, snapshot_kind))
        inserted += cur.rowcount
    return inserted, unmatched

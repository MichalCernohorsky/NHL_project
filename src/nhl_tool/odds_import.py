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
    scores), plus everyone listed on either team's roster that season
    (table rosters: summer trades, injured stars, rookies before their
    debut - 48 of the first live names were unmatched without it)."""
    g = conn.execute("SELECT season, home_team_id, away_team_id FROM games"
                     " WHERE game_id = ?", (game_id,)).fetchone()
    if g is None:
        return {}
    start = int(g["season"][:4])
    seasons = (g["season"], f"{start - 1}-{str(start)[2:]}")
    rows = conn.execute(
        """SELECT DISTINCT p.player_id, p.full_name FROM players p
           JOIN (SELECT l.player_id FROM (
                     SELECT player_id, team_id, game_id FROM player_game_logs
                     UNION ALL
                     SELECT player_id, team_id, game_id FROM goalie_game_logs) l
                   JOIN games x ON x.game_id = l.game_id
                  WHERE l.team_id IN (?, ?) AND x.season IN (?, ?)
                 UNION
                 SELECT r.player_id FROM rosters r
                  WHERE r.team_id IN (?, ?) AND r.season = ?) m
             ON m.player_id = p.player_id
           WHERE p.full_name IS NOT NULL""",
        (g["home_team_id"], g["away_team_id"], *seasons,
         g["home_team_id"], g["away_team_id"], g["season"])).fetchall()
    lookup, ambiguous = {}, set()
    for r in rows:
        key = normalize_name(r["full_name"])
        if key in lookup and lookup[key] != r["player_id"]:
            ambiguous.add(key)
        lookup[key] = r["player_id"]
    for key in ambiguous:
        # Kept as None (not deleted): two players share the name, e.g. the two
        # Elias Petterssons of Vancouver. resolve_player must not fall back to
        # a surname match for them either.
        lookup[key] = None
    return lookup


def _first_compatible(a: str, b: str) -> bool:
    """Book vs NHL first names: JJ / John-Jason, Nick / Nicholas, Tommy /
    Thomas share the initial; Yegor / Egor, Yevgeni / Evgeni differ only by
    the transliterated Ye- of the Cyrillic E."""
    if not a or not b:
        return False
    strip = lambda x: x[1:] if x.startswith("y") and len(x) > 2 else x  # noqa: E731
    return a[0] == b[0] or strip(a)[0] == strip(b)[0]


def resolve_player(lookup: dict, name: str) -> int | None:
    """Exact normalized name first. Otherwise a surname that is unique among
    the two teams' players with a compatible first name - never when that
    surname belongs to an ambiguous full name."""
    key = normalize_name(name)
    if key in lookup:
        return lookup[key]
    parts = key.split(" ")
    if len(parts) < 2:
        return None
    first, last = parts[0], parts[-1]
    same = [(k, pid) for k, pid in lookup.items() if k.split(" ")[-1] == last]
    if any(pid is None for _, pid in same):
        return None
    ids = {pid for k, pid in same if _first_compatible(first, k.split(" ")[0])}
    return ids.pop() if len(ids) == 1 and len({pid for _, pid in same}) == 1 else None


def insert_odds_rows(conn, rows, *, event_id: str, game_id: int | None, market: str,
                     snapshot_time: str, snapshot_kind: str,
                     roster: dict[str, int]) -> tuple[int, set[str]]:
    """-> (rows inserted, names that matched no player)."""
    unmatched, inserted = set(), 0
    for r in rows:
        pid = resolve_player(roster, r["player_name"])
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

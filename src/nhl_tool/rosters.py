"""Team rosters from api-web.nhle.com/v1/roster/{team}/{season}."""
from __future__ import annotations

from .parsing import default_name, season_id

GROUPS = ("forwards", "defensemen", "goalies")


def roster_path(abbr: str, season: str) -> str:
    return f"roster/{abbr}/{season_id(season)}"


def parse_roster(payload: dict) -> list[dict]:
    out = []
    for group in GROUPS:
        for p in payload.get(group) or []:
            first = default_name(p.get("firstName")) or ""
            last = default_name(p.get("lastName")) or ""
            out.append({"player_id": int(p["id"]),
                        "full_name": f"{first} {last}".strip() or None,
                        "position": p.get("positionCode"),
                        "shoots": p.get("shootsCatches"),
                        "birth_date": p.get("birthDate")})
    return out


def store(conn, season: str, team_id: int, players: list[dict], today: str) -> int:
    for p in players:
        conn.execute(
            """INSERT INTO players (player_id, full_name, position, shoots, birth_date)
               VALUES (:player_id, :full_name, :position, :shoots, :birth_date)
               ON CONFLICT(player_id) DO UPDATE SET
                   full_name = COALESCE(players.full_name, excluded.full_name),
                   position = COALESCE(players.position, excluded.position),
                   shoots = COALESCE(players.shoots, excluded.shoots),
                   birth_date = COALESCE(players.birth_date, excluded.birth_date)""", p)
        conn.execute(
            """INSERT INTO rosters (season, team_id, player_id, position, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(season, team_id, player_id) DO UPDATE SET
                   position = excluded.position, last_seen = excluded.last_seen""",
            (season, team_id, p["player_id"], p["position"], today, today))
    return len(players)

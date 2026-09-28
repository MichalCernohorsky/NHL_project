"""Player details from api-web.nhle.com/v1/player/{id}/landing.

Only for players still missing a full name after the TOI step - in practice
goalies, whom the skater TOI report does not cover. The full name is what
The Odds API prints, so the odds-to-roster match depends on it.
"""
from __future__ import annotations

from .parsing import default_name


def parse_landing(payload: dict) -> dict:
    first = default_name(payload.get("firstName")) or ""
    last = default_name(payload.get("lastName")) or ""
    return {"player_id": int(payload["playerId"]),
            "full_name": f"{first} {last}".strip() or None,
            "position": payload.get("position"),
            "shoots": payload.get("shootsCatches"),
            "birth_date": payload.get("birthDate")}


def store(conn, row: dict):
    conn.execute(
        """UPDATE players SET full_name = COALESCE(?, full_name),
               position = COALESCE(?, position), shoots = COALESCE(?, shoots),
               birth_date = COALESCE(?, birth_date)
           WHERE player_id = ?""",
        (row["full_name"], row["position"], row["shoots"], row["birth_date"],
         row["player_id"]))

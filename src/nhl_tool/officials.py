"""Referees and linesmen from the game page's right rail (gameInfo).

Listed for finished games. For games that have not started the list is
empty until the NHL publishes the assignment; probe() records what the API
shows at a given moment (docs/team_markets_plan.md section 3).
"""
from __future__ import annotations

ROLES = (("referees", "referee"), ("linesmen", "linesman"))


def _name(entry) -> str | None:
    if not isinstance(entry, dict):
        return None
    for key in ("fullName", "default"):
        v = entry.get(key)
        if isinstance(v, dict):
            v = v.get("default")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def parse_officials(rail: dict) -> list[tuple[str, str]]:
    """-> [(role, name)], role in ('referee', 'linesman')."""
    info = rail.get("gameInfo") or {}
    out = []
    for key, role in ROLES:
        for entry in info.get(key) or []:
            name = _name(entry)
            if name and (role, name) not in out:
                out.append((role, name))
    return out


def store(conn, game_id: int, officials: list[tuple[str, str]]) -> int:
    conn.execute("DELETE FROM game_officials WHERE game_id = ?", (game_id,))
    conn.executemany("INSERT INTO game_officials (game_id, role, name) VALUES (?, ?, ?)",
                     [(game_id, role, name) for role, name in officials])
    return len(officials)


def probe(conn, game_id: int, start_time_utc: str, rail: dict, checked_at: str) -> int:
    """Record how many referees the API lists for a game right now."""
    refs = [name for role, name in parse_officials(rail) if role == "referee"]
    conn.execute(
        """INSERT OR REPLACE INTO referee_probe (game_id, checked_at, start_time_utc, referees, names)
           VALUES (?, ?, ?, ?, ?)""",
        (game_id, checked_at, start_time_utc, len(refs), "; ".join(refs) or None))
    return len(refs)

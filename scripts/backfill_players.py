#!/usr/bin/env python3
"""Full names / position / birth date for players still missing a full name
(mostly goalies: the skater TOI report does not cover them). One request per
player, only ever for players that need it.

Usage:
    python scripts/backfill_players.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import players
from nhl_tool.config import load_config, resolve_cache_dir, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.http_client import NotFoundError
from nhl_tool.nhl_client import NhlClient


def main():
    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    client = NhlClient(cfg, resolve_cache_dir(cfg))
    ids = [r[0] for r in conn.execute(
        "SELECT player_id FROM players WHERE full_name IS NULL ORDER BY player_id")]
    print(f"hracu bez celeho jmena: {len(ids)}")
    missing = 0
    for i, pid in enumerate(ids, 1):
        try:
            payload = client.web(f"player/{pid}/landing", cache_key=f"player/{pid}")
        except NotFoundError:
            missing += 1
            continue
        players.store(conn, players.parse_landing(payload))
        if i % 50 == 0:
            conn.commit()
            print(f"  {i}/{len(ids)}")
    conn.commit()
    left = conn.execute("SELECT COUNT(*) FROM players WHERE full_name IS NULL").fetchone()[0]
    print(f"hotovo | nenalezeno upstream: {missing} | stale bez jmena: {left}"
          f" | requestu: {client.requests_made}")


if __name__ == "__main__":
    main()

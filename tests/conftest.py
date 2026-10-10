import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    with open(FIXTURES / name) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _no_real_github(monkeypatch, tmp_path):
    """No test may reach the user's real data repository: the token the
    Mac's shell exports (docs/cloud.md step 5) is removed for every test,
    and the bets store writes into a temporary directory."""
    for name in ("NHL_DATA_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "NHL_DB_RELEASE_REPO",
                 "NHL_ACTIONS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NHL_BETS_DIR", str(tmp_path / "bets"))


@pytest.fixture
def conn():
    """Fresh in-memory database with every migration applied."""
    from migrate import apply_migrations, ensure_migrations_table
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    ensure_migrations_table(c)
    apply_migrations(c)
    yield c
    c.close()


def week(games, date="2025-10-09"):
    return {"gameWeek": [{"date": date, "games": games}]}


def game(gid, season=20252026, game_type=2, state="OFF", outcome="REG",
         home=(17, "DET", "Detroit", "Red Wings", 1),
         away=(8, "MTL", "Montréal", "Canadiens", 5)):
    def side(t):
        return {"id": t[0], "abbrev": t[1], "placeName": {"default": t[2]},
                "commonName": {"default": t[3]}, "score": t[4]}
    return {"id": gid, "season": season, "gameType": game_type,
            "startTimeUTC": "2025-10-09T23:00:00Z", "gameState": state,
            "gameScheduleState": "OK", "neutralSite": False,
            "homeTeam": side(home), "awayTeam": side(away),
            "gameOutcome": {"lastPeriodType": outcome}}

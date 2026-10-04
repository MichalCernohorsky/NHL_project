"""Penalty events and officials (docs/team_markets_plan.md, step 2): events
are stored one by one, checked against the box score, and the referee
probe records what the API knows before a game."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conftest import game, load_fixture, week  # noqa: E402

from nhl_tool import boxscore, officials, penalties  # noqa: E402
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams  # noqa: E402

GID = 2025020010


def _pen(event_id, type_code, duration, *, team=17, period=1, ptype="REG", by=None,
         served=None, desc="tripping"):
    det = {"typeCode": type_code, "descKey": desc, "duration": duration,
           "eventOwnerTeamId": team, "xCoord": 1, "yCoord": 2, "zoneCode": "N"}
    if by:
        det["committedByPlayerId"] = by
    if served:
        det["servedByPlayerId"] = served
    return {"eventId": event_id, "typeDescKey": "penalty", "timeInPeriod": "05:00",
            "periodDescriptor": {"number": period, "periodType": ptype}, "details": det}


def _payload(*plays):
    return {"plays": [{"eventId": 1, "typeDescKey": "faceoff",
                       "periodDescriptor": {"number": 1, "periodType": "REG"}, "details": {}},
                      *plays]}


def _db(conn):
    teams, games = parse_week(week([game(GID)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    boxscore.store(conn, boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json")), [])
    conn.execute("UPDATE player_game_logs SET pim = 0 WHERE game_id = ?", (GID,))
    return [r["player_id"] for r in conn.execute(
        "SELECT player_id FROM player_game_logs WHERE game_id = ? ORDER BY player_id", (GID,))]


def test_parse_keeps_every_penalty_with_its_kind_and_length():
    rows = penalties.parse_penalties(_payload(
        _pen(10, "MIN", 2, by=5), _pen(11, "MIN", 4, by=6, desc="high-sticking-double-minor"),
        _pen(12, "BEN", 2, served=7, desc="too-many-men-on-the-ice"),
        _pen(13, "MAJ", 5, by=5, team=8, period=4, ptype="OT")))
    assert [r["event_id"] for r in rows] == [10, 11, 12, 13]          # the faceoff is not one
    assert [(r["type_code"], r["duration"]) for r in rows] == \
        [("MIN", 2), ("MIN", 4), ("BEN", 2), ("MAJ", 5)]
    assert rows[2]["committed_by"] is None and rows[2]["served_by"] == 7
    assert rows[3]["team_id"] == 8 and rows[3]["period_type"] == "OT"
    assert penalties.incomplete(rows) == []


def test_incomplete_event_is_reported():
    play = _pen(20, "MIN", 2, by=5)
    del play["details"]["eventOwnerTeamId"]
    assert penalties.incomplete(penalties.parse_penalties(_payload(play))) == \
        ["event 20 missing team_id"]


def test_check_against_box_score_pim(conn):
    a, b, *_ = _db(conn)
    conn.execute("UPDATE player_game_logs SET pim = 2 WHERE player_id = ?", (a,))
    conn.execute("UPDATE player_game_logs SET pim = 20 WHERE player_id = ?", (b,))
    rows = penalties.parse_penalties(_payload(
        _pen(10, "MIN", 2, by=a),
        _pen(11, "MAT", 5, by=b, desc="match-penalty"),        # 15 minutes in the box score
        _pen(12, "MAJ", 5, by=b, desc="fighting"),
        _pen(13, "BEN", 2, served=a)))                         # bench: nobody's PIM
    assert penalties.mismatches(conn, GID, rows) == []
    short = [r for r in rows if r["event_id"] != 12]
    assert penalties.mismatches(conn, GID, short) == [f"{b} pim box=20 pbp=15"]


def test_store_is_idempotent_and_keeps_events(conn):
    a, *_ = _db(conn)
    rows = penalties.parse_penalties(_payload(_pen(10, "MIN", 2, by=a), _pen(11, "MIN", 4, by=a)))
    assert penalties.store(conn, GID, rows) == 2
    assert penalties.store(conn, GID, rows) == 2
    got = conn.execute("SELECT event_id, team_id, type_code, duration, period_type "
                       "FROM penalties WHERE game_id = ? ORDER BY event_id", (GID,)).fetchall()
    assert [tuple(r) for r in got] == [(10, 17, "MIN", 2, "REG"), (11, 17, "MIN", 4, "REG")]


RAIL = {"gameInfo": {
    "referees": [{"fullName": {"default": "Chris Rooney"}, "sweaterNumber": 5},
                 {"default": "Jake Brenk"}],
    "linesmen": [{"fullName": {"default": "Shandor Alphonso"}}, {"fullName": {"default": " "}}]}}


def test_officials_parse_both_shapes_and_store(conn):
    _db(conn)
    found = officials.parse_officials(RAIL)
    assert found == [("referee", "Chris Rooney"), ("referee", "Jake Brenk"),
                     ("linesman", "Shandor Alphonso")]
    assert officials.parse_officials({}) == [] and officials.parse_officials({"gameInfo": {}}) == []
    assert officials.store(conn, GID, found) == 3 and officials.store(conn, GID, found) == 3
    assert conn.execute("SELECT COUNT(*) FROM game_officials").fetchone()[0] == 3


def test_probe_records_unknown_and_known(conn):
    _db(conn)
    start = "2025-10-09T23:00:00Z"
    assert officials.probe(conn, GID, start, {"gameInfo": {"referees": []}},
                           "2025-10-09T10:30:00+00:00") == 0
    assert officials.probe(conn, GID, start, RAIL, "2025-10-09T17:30:00+00:00") == 2
    rows = conn.execute("SELECT checked_at, referees, names FROM referee_probe "
                        "ORDER BY checked_at").fetchall()
    assert [tuple(r) for r in rows] == [
        ("2025-10-09T10:30:00+00:00", 0, None),
        ("2025-10-09T17:30:00+00:00", 2, "Chris Rooney; Jake Brenk")]


def test_scripts_are_part_of_the_daily_run():
    from daily_collect import STEPS
    scripts = {name: script for name, script, _ in STEPS}
    for name in ("penalties", "officials", "refprobe"):
        assert (ROOT / "scripts" / scripts[name]).exists()

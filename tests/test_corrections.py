"""NHL corrections after a game (docs/models_v2_notes.md, amendment N-3):
games of the live season are checked again for 10 days and re-downloaded
when the NHL changed them; settled numbers stay."""
import copy
import hashlib
import re
import sqlite3
from pathlib import Path

import pytest

from conftest import game, load_fixture, week

from nhl_tool import attempts, boxscore, corrections, pbp, penalties
from nhl_tool.db import set_state, state_keys
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs" / "models_v2_notes.md"
GID = 2025020010                     # fixture game of 2025-10-09: home DET (17), away MTL (8)
DAY = "2025-10-09"
A, B = 8481540, 8476875              # two MTL skaters with 3 shots each in the box score
OLD = "2025-10-10 15:00:00"          # when the steps first stored the game


def test_amendment_n3_keeps_its_fingerprint():
    text = NOTES.read_text()
    start = text.index("**N-3 (11. 10. 2026")
    end = text.index("<!-- konec dodatku N-3 -->")
    m = re.search(r"Otisk dodatku N-3 .*?\*\*SHA-256\s+`([0-9a-f]{64})`\*\*", text[end:], re.S)
    assert m, "fingerprint of N-3 missing below its end marker"
    assert hashlib.sha256(text[start:end].encode()).hexdigest() == m.group(1)


# ------------------------------------------------------------------ feed

def _box():
    return load_fixture("boxscore_2025020010.json")


def _skaters(box_payload):
    stats = box_payload["playerByGameStats"]
    return [p for side in ("homeTeam", "awayTeam")
            for p in stats[side]["forwards"] + stats[side]["defense"]]


def _move_shot(box_payload, src, dst):
    """The NHL gives one of src's shots on goal to dst."""
    out = copy.deepcopy(box_payload)
    for p in _skaters(out):
        if p["playerId"] in (src, dst):
            p["sog"] += 1 if p["playerId"] == dst else -1
    return out


def _pbp(box_payload):
    """A play-by-play that agrees with the box score: every shot in
    regulation at five on five, every block, every penalty minute."""
    parsed = boxscore.parse_boxscore(box_payload)
    goalie = {g["team_id"]: g["player_id"] for g in parsed["goalies"]}
    plays, eid = [], 0

    def ev(kind, **det):
        nonlocal eid
        eid += 1
        plays.append({"eventId": eid, "typeDescKey": kind, "situationCode": "1551",
                      "timeInPeriod": "10:00",
                      "periodDescriptor": {"number": 1, "periodType": "REG"}, "details": det})
    for s in parsed["skaters"]:
        opp_goalie = next(g for t, g in goalie.items() if t != s["team_id"])
        for _ in range(s["sog"] or 0):
            ev("shot-on-goal", shootingPlayerId=s["player_id"], goalieInNetId=opp_goalie,
               eventOwnerTeamId=s["team_id"])
        for _ in range(s["blocked_shots"] or 0):
            ev("blocked-shot", blockingPlayerId=s["player_id"], eventOwnerTeamId=s["team_id"])
        for _ in range((s["pim"] or 0) // 2):
            ev("penalty", eventOwnerTeamId=s["team_id"], typeCode="MIN", descKey="tripping",
               duration=2, committedByPlayerId=s["player_id"])
    return {"plays": plays}


def _store_all(conn, box_payload, pbp_payload):
    """What the daily steps store for a game, each after its own check."""
    parsed = boxscore.parse_boxscore(box_payload)
    boxscore.store(conn, parsed, [])
    counts = pbp.parse_pbp(pbp_payload)
    assert pbp.mismatches(conn, GID, counts) == []
    pbp.store(conn, GID, counts)
    rows = penalties.parse_penalties(pbp_payload)
    assert penalties.mismatches(conn, GID, rows) == []
    penalties.store(conn, GID, rows)
    events = attempts.parse_attempts(pbp_payload)
    assert attempts.mismatches(conn, GID, events) == []
    attempts.store(conn, GID, events)
    for task in corrections.GAME_TASKS:
        set_state(conn, task, str(GID), "done")
    set_state(conn, "toi", DAY, "done")
    conn.execute("UPDATE backfill_state SET updated_at = ?", (OLD,))


@pytest.fixture
def seeded(conn):
    teams, games = parse_week(week([game(GID)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    _store_all(conn, _box(), _pbp(_box()))
    return conn


class FakeClient:
    def __init__(self, box_payload, pbp_payload, cache_dir):
        self.payloads = {f"gamecenter/{GID}/boxscore": box_payload,
                         f"gamecenter/{GID}/play-by-play": pbp_payload}
        self.cache_dir = cache_dir
        self.requests_made = 0

    def web(self, path, cache_key=None, keep=None):
        assert cache_key is None                  # the check never reads the cache
        self.requests_made += 1
        return self.payloads[path]


def _check_game(conn, box_payload, pbp_payload, cache_dir, today="2025-10-12"):
    from check_corrections import check_game
    g = {"game_id": GID, "game_date": DAY, "age_days": 3}
    return check_game(conn, FakeClient(box_payload, pbp_payload, cache_dir), g, today)


# ------------------------------------------------------------------ compare

def test_unchanged_game_has_no_differences(seeded, tmp_path):
    assert corrections.check(seeded, GID, _box(), _pbp(_box())) == ([], [])
    assert _check_game(seeded, _box(), _pbp(_box()), tmp_path) == ("same", [], None)
    assert state_keys(seeded, "pbp") == {str(GID)}


def test_a_moved_shot_is_found_everywhere_it_is_stored(seeded):
    fresh = _move_shot(_box(), A, B)
    diffs, problems = corrections.check(seeded, GID, fresh, _pbp(fresh))
    assert problems == []
    got = {(d["player_id"], d["field"]): (d["old"], d["new"]) for d in diffs}
    assert got == {(A, "sog"): (3, 2), (B, "sog"): (3, 4),
                   (A, "sog_reg"): (3, 2), (B, "sog_reg"): (3, 4),
                   (A, "att_reg"): (3, 2), (B, "att_reg"): (3, 4)}
    assert all(d["team_id"] == 8 for d in diffs)


def test_goalie_team_game_and_penalty_changes_are_found(seeded):
    fresh = _box()
    fresh["playerByGameStats"]["awayTeam"]["goalies"][1]["saves"] += 1
    fresh["awayTeam"]["sog"] += 1
    fresh["homeTeam"]["score"] += 1
    feed = _pbp(fresh)
    pen = next(p for p in feed["plays"] if p["typeDescKey"] == "penalty")
    pen["details"]["descKey"] = "holding"
    fields = {d["field"] for d in corrections.check(seeded, GID, fresh, feed)[0]}
    assert {"goalie.saves", "team.sog", "team.goals", "game.home_score",
            f"penalty {pen['eventId']}.desc_key"} <= fields


def test_missing_regulation_counts_are_not_a_correction(seeded):
    """A game whose 60-minute counts were never stored (pbp step in error)
    is not reported for them - only for what the NHL really changed."""
    seeded.execute("UPDATE player_game_logs SET sog_reg = NULL, blocked_shots_reg = NULL")
    seeded.execute("UPDATE goalie_game_logs SET shots_against_reg = NULL, saves_reg = NULL")
    assert corrections.check(seeded, GID, _box(), _pbp(_box()))[0] == []


def test_a_new_skater_row_is_reported(seeded):
    seeded.execute("DELETE FROM player_game_logs WHERE player_id = ?", (A,))
    diffs = corrections.check(seeded, GID, _box(), _pbp(_box()))[0]
    assert {"player_id": A, "team_id": 8, "field": "row", "old": 0, "new": 1} in diffs


# ------------------------------------------------------------------ act

def test_refresh_marks_the_game_stale_and_the_steps_then_pass_the_strict_check(seeded, tmp_path):
    """The failure of 10. 10. 2026: the stored count lost to an NHL
    correction, so the attempts check (kept strict) refused the game."""
    fresh = _move_shot(_box(), A, B)
    assert attempts.mismatches(seeded, GID, attempts.parse_attempts(_pbp(fresh))) != []
    for key in (f"boxscore/{GID}", f"right_rail/{GID}", f"toi/{DAY}", "boxscore/1"):
        (tmp_path / f"{key}.json").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f"{key}.json").write_text("{}")

    action, diffs, detail = _check_game(seeded, fresh, _pbp(fresh), tmp_path)
    assert action == "refreshed" and len(diffs) == 6 and f"{A} sog 3->2" in detail
    for task in corrections.GAME_TASKS:
        assert state_keys(seeded, task, statuses=("stale",)) == {str(GID)}
        assert state_keys(seeded, task) == set()          # not done: the steps run again
    assert state_keys(seeded, "toi", statuses=("stale",)) == {DAY}
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json")) \
        == ["boxscore/1.json"]                              # only the other game's cache stays

    _store_all(seeded, fresh, _pbp(fresh))                  # the rest of the daily run
    assert corrections.check(seeded, GID, fresh, _pbp(fresh)) == ([], [])


def test_a_correction_in_progress_changes_nothing(seeded, tmp_path):
    fresh = _move_shot(_box(), A, B)
    action, diffs, detail = _check_game(seeded, fresh, _pbp(_box()), tmp_path)   # pbp not yet
    assert action == "inconsistent" and diffs and "sog box=" in detail
    assert state_keys(seeded, "boxscore") == {str(GID)} and state_keys(seeded, "toi") == {DAY}


def test_record_logs_the_values_only_of_a_refresh(seeded):
    diffs = corrections.check(seeded, GID, _move_shot(_box(), A, B), _pbp(_move_shot(_box(), A, B)))[0]
    corrections.record(seeded, GID, "2025-10-11T12:00:00+00:00", 2, "inconsistent", diffs, "x")
    corrections.record(seeded, GID, "2025-10-12T12:00:00+00:00", 3, "refreshed", diffs, "y")
    checks = seeded.execute("SELECT age_days, action, n_diff FROM stat_checks ORDER BY checked_at").fetchall()
    assert [tuple(r) for r in checks] == [(2, "inconsistent", 6), (3, "refreshed", 6)]
    rows = seeded.execute("SELECT * FROM stat_corrections WHERE field = 'sog_reg'").fetchall()
    assert sorted((r["player_id"], r["age_days"], r["old_value"], r["new_value"]) for r in rows) \
        == sorted([(A, 3, 3, 2), (B, 3, 3, 4)])
    assert seeded.execute("SELECT COUNT(*) FROM stat_corrections").fetchone()[0] == 6


# ------------------------------------------------------------------ which games

def _games(conn, dates_ids):
    conn.executemany("INSERT INTO teams (team_id, abbreviation, full_name) VALUES (?, ?, ?)",
                     [(1, "AAA", "A"), (2, "BBB", "B")])
    for gid, day, season in dates_ids:
        conn.execute("""INSERT INTO games (game_id, season, season_type, game_date,
                            home_team_id, away_team_id, game_state)
                        VALUES (?, ?, 'regular', ?, 1, 2, 'OFF')""", (gid, season, day))
        set_state(conn, "boxscore", str(gid), "done")
    conn.execute("UPDATE backfill_state SET updated_at = '2026-10-10 15:00:00'")


def test_candidates_are_live_games_1_to_10_days_old_once_a_day_and_errors(conn):
    today = "2026-10-20"
    _games(conn, [(1, "2026-10-20", "2026-27"),      # age 0: played today
                  (2, "2026-10-19", "2026-27"),      # 1
                  (3, "2026-10-10", "2026-27"),      # 10
                  (4, "2026-10-09", "2026-27"),      # 11: too old
                  (5, "2026-10-01", "2026-27"),      # old, but attempts in error
                  (6, "2026-10-15", "2026-27"),      # already checked today
                  (7, "2026-10-15", "2026-27"),      # checked today, but the download failed
                  (8, "2026-10-18", "2026-27"),      # box score downloaded today
                  (9, "2026-10-18", "2025-26")])     # another season
    set_state(conn, "attempts", "5", "error", "8477404 sog_reg db=4 pbp=3")
    set_state(conn, "attempts", "4", "done")
    conn.execute("UPDATE backfill_state SET updated_at = '2026-10-10 15:00:00' WHERE task = 'attempts'")
    conn.execute("UPDATE backfill_state SET updated_at = '2026-10-20 13:00:00' WHERE key = '8'")
    corrections.record(conn, 6, "2026-10-20T11:30:00+00:00", 5, "same", [])
    corrections.record(conn, 6, "2026-10-19T11:30:00+00:00", 4, "same", [])
    corrections.record(conn, 7, "2026-10-20T11:30:00+00:00", 5, "error", [], "ReadTimeout")
    got = [(r["game_id"], r["age_days"]) for r in corrections.candidates(conn, ["2026-27"], today)]
    assert got == [(5, 19), (3, 10), (7, 5), (2, 1)]


# ------------------------------------------------------------------ settlement

def test_a_settled_ticket_keeps_the_number_known_at_settlement(seeded, tmp_path, monkeypatch):
    """User's decision of 11. 10. 2026: the ticket shows the first number,
    the database (and the models) the corrected one."""
    from dashboard import data
    path = tmp_path / "nhl.db"
    fresh = _move_shot(_box(), A, B)
    corrections.record(seeded, GID, "2025-10-12T12:00:00+00:00", 3, "refreshed",
                       corrections.check(seeded, GID, fresh, _pbp(fresh))[0])
    _store_all(seeded, fresh, _pbp(fresh))
    twice = _move_shot(fresh, A, B)                         # a second correction later on
    corrections.record(seeded, GID, "2025-10-15T12:00:00+00:00", 6, "refreshed",
                       corrections.check(seeded, GID, twice, _pbp(twice))[0])
    _store_all(seeded, twice, _pbp(twice))
    seeded.commit()
    seeded.execute("VACUUM INTO ?", (str(path),))
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))

    assert seeded.execute("SELECT sog_reg FROM player_game_logs WHERE player_id = ?", (A,)).fetchone()[0] == 1
    assert data.bet_facts(GID, A)["actual"] == 3           # what was known when it was settled
    assert data.bet_facts(GID, B)["actual"] == 3
    other = next(p["playerId"] for p in _skaters(_box()) if p["playerId"] not in (A, B))
    assert data.bet_facts(GID, other)["actual"] == seeded.execute(
        "SELECT sog_reg FROM player_game_logs WHERE player_id = ?", (other,)).fetchone()[0]


def test_settled_tips_and_team_predictions_keep_their_number_after_a_refresh(seeded):
    """tips and team_predictions store the number at settlement and the
    settlement only fills empty ones, so a refresh cannot change them."""
    from nhl_tool import team_tips, tips
    seeded.execute("""INSERT INTO tips (tip_id, model, game_id, game_date, player_id, player_name,
                          team_id, opp_id, market, line, side, mu_60, p_model, p_market, edge,
                          books, sim_tipsport_price, entry_live, playable, snapshot_kind,
                          snapshot_time, built_at)
                      VALUES ('t', 'm', ?, ?, ?, 'A', 8, 17, 'player_shots_on_goal', 2.5, 'over',
                              2.0, 0.6, 0.5, 0.1, 3, 1.9, 1, 1, 'live', 'x', 'x')""", (GID, DAY, A))
    seeded.execute("""INSERT INTO team_predictions (game_id, team_id, market, game_date, opp_id,
                          is_home, mu, model, built_at)
                      VALUES (?, 8, 'S-T', ?, 17, 0, 26.0, 'm', 'x')""", (GID, DAY))
    assert tips.settle(seeded, DAY) == 1 and team_tips.settle(seeded, DAY) == 1
    before = (seeded.execute("SELECT actual_60, outcome FROM tips").fetchone()[:],
              seeded.execute("SELECT actual_60 FROM team_predictions").fetchone()[0])
    assert before[0] == (3, "win")

    fresh = _move_shot(_move_shot(_box(), A, 8477429), A, 8478891)   # two of A's shots go to DET
    assert sum(r[0] for r in seeded.execute(
        "SELECT sog_reg FROM player_game_logs WHERE game_id = ? AND team_id = 8", (GID,))) == 6
    _store_all(seeded, fresh, _pbp(fresh))
    assert seeded.execute("SELECT sog_reg FROM player_game_logs WHERE player_id = ?", (A,)).fetchone()[0] == 1
    assert team_tips.actual_60(seeded, GID, 8, "S-T") == 4      # what a new settlement would read
    assert tips.settle(seeded, DAY) == 0 and team_tips.settle(seeded, DAY) == 0
    assert (seeded.execute("SELECT actual_60, outcome FROM tips").fetchone()[:],
            seeded.execute("SELECT actual_60 FROM team_predictions").fetchone()[0]) == before


def test_the_daily_run_checks_corrections_before_the_box_scores():
    from daily_collect import STEPS
    names = [s[0] for s in STEPS]
    assert names.index("corrections") < names.index("boxscores") < names.index("attempts")
    assert ("corrections", "check_corrections.py", True) in STEPS


def test_the_window_is_the_one_of_the_amendment():
    assert corrections.WINDOW_DAYS == 10
    assert "1 až 10 dní" in NOTES.read_text()

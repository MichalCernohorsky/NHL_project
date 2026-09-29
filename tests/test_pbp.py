from conftest import game, load_fixture, week

from nhl_tool import boxscore, pbp
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams

GID = 2025020010


def _seed(conn):
    teams, games = parse_week(week([game(GID)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    parsed = boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json"))
    boxscore.store(conn, parsed, [])
    return parsed


def _ev(kind, period_type, **details):
    return {"typeDescKey": kind, "periodDescriptor": {"periodType": period_type},
            "details": details}


def _pbp_matching(parsed, ot_shooter=None):
    """Synthetic play-by-play reproducing the box score; one of the shooter's
    shots is moved to overtime."""
    plays = []
    goalie = parsed["goalies"][0]["player_id"]
    for s in parsed["skaters"]:
        for k in range(s["sog"] or 0):
            period = "OT" if s["player_id"] == ot_shooter and k == 0 else "REG"
            plays.append(_ev("shot-on-goal", period, shootingPlayerId=s["player_id"],
                             goalieInNetId=goalie))
        for _ in range(s["blocked_shots"] or 0):
            plays.append(_ev("blocked-shot", "REG", blockingPlayerId=s["player_id"]))
    plays.append(_ev("missed-shot", "REG", shootingPlayerId=1))   # never counted
    return {"plays": plays}


def test_regulation_counts_exclude_overtime(conn):
    parsed = _seed(conn)
    shooter = next(s for s in parsed["skaters"] if (s["sog"] or 0) >= 1)
    counts = pbp.parse_pbp(_pbp_matching(parsed, ot_shooter=shooter["player_id"]))
    assert pbp.mismatches(conn, GID, counts) == []
    pbp.store(conn, GID, counts)
    row = conn.execute("SELECT sog, sog_reg FROM player_game_logs WHERE player_id = ?",
                       (shooter["player_id"],)).fetchone()
    assert row["sog_reg"] == row["sog"] - 1
    others = conn.execute("SELECT COUNT(*) FROM player_game_logs WHERE sog_reg != sog"
                          " AND game_id = ?", (GID,)).fetchone()[0]
    assert others == 1


def test_goal_counts_as_a_shot_but_not_a_save():
    counts = pbp.parse_pbp({"plays": [
        _ev("goal", "REG", scoringPlayerId=7, goalieInNetId=30, shotType="snap"),
        _ev("shot-on-goal", "REG", shootingPlayerId=7, goalieInNetId=30),
        _ev("shot-on-goal", "OT", shootingPlayerId=7, goalieInNetId=30)]})
    assert counts["sog"][7] == 3 and counts["sog_reg"][7] == 2
    assert counts["sa_reg"][30] == 2 and counts["sv_reg"][30] == 1


def test_disagreement_with_the_box_score_is_reported(conn):
    parsed = _seed(conn)
    counts = pbp.parse_pbp(_pbp_matching(parsed))
    victim = next(iter(counts["sog"]))
    counts["sog"][victim] += 1
    assert any(str(victim) in m for m in pbp.mismatches(conn, GID, counts))


def test_shootout_and_teammate_blocks_are_not_statistics():
    """Both found by the box-score check on real 2025-26 games."""
    counts = pbp.parse_pbp({"plays": [
        _ev("shot-on-goal", "REG", shootingPlayerId=7, goalieInNetId=30),
        _ev("shot-on-goal", "SO", shootingPlayerId=7, goalieInNetId=30),
        _ev("goal", "SO", scoringPlayerId=7, goalieInNetId=30, shotType="wrist"),
        _ev("blocked-shot", "REG", blockingPlayerId=4, reason="blocked"),
        _ev("blocked-shot", "REG", blockingPlayerId=4, reason="teammate-blocked")]})
    assert counts["sog"][7] == 1 and counts["sa_reg"][30] == 1
    assert counts["blk"][4] == 1


def test_goal_without_a_shot_is_not_a_shot():
    """Own goals / awarded goals carry no shot type; the box score does not
    count them as shots (found on 4 of the first 500 games of 2023-24)."""
    counts = pbp.parse_pbp({"plays": [
        _ev("goal", "REG", scoringPlayerId=7, goalieInNetId=30, shotType="wrist"),
        _ev("goal", "REG", scoringPlayerId=7, goalieInNetId=30)]})
    assert counts["sog"][7] == 1 and counts["sog_reg"][7] == 1
    assert counts["sa_reg"][30] == 1 and counts["sv_reg"][30] == 0

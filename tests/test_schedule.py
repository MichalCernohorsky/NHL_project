from conftest import game, week

from nhl_tool.schedule import (parse_week, season_bounds, upsert_games,
                               upsert_teams, week_starts)


def test_parse_week_keeps_only_the_requested_season_and_known_types():
    payload = week([game(2025020010), game(2026010001, season=20262027, game_type=1),
                    game(2025040001, game_type=4)])
    teams, games = parse_week(payload, "2025-26")
    assert [g["game_id"] for g in games] == [2025020010]
    assert teams[8]["full_name"] == "Montréal Canadiens"
    assert games[0]["last_period_type"] == "REG"


def test_unfinished_game_carries_no_score_and_no_outcome():
    _, games = parse_week(week([game(2026020001, season=20262027, state="FUT",
                                     outcome=None)]), "2026-27")
    g = games[0]
    assert g["home_score"] is None and g["last_period_type"] is None


def test_resync_never_erases_a_result(conn):
    teams, games = parse_week(week([game(2025020010, outcome="SO")]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    # a later, poorer payload (e.g. cached week fetched before the game ended)
    _, stale = parse_week(week([game(2025020010, state="LIVE", outcome=None)]), "2025-26")
    upsert_games(conn, stale)
    row = conn.execute("SELECT home_score, last_period_type FROM games").fetchone()
    assert tuple(row) == (1, "SO")


def test_week_starts_cover_the_whole_range():
    starts = week_starts("2025-10-07", "2025-10-21")
    assert starts == ["2025-10-07", "2025-10-14", "2025-10-21"]


def test_season_bounds():
    probe = {"preSeasonStartDate": "2025-09-20", "regularSeasonStartDate": "2025-10-07",
             "regularSeasonEndDate": "2026-04-17", "playoffEndDate": "2026-06-15"}
    assert season_bounds(probe) == ("2025-10-07", "2026-04-17")
    assert season_bounds(probe, include_playoffs=True, include_preseason=True) == \
        ("2025-09-20", "2026-06-15")

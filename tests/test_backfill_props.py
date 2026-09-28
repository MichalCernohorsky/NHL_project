from conftest import game, week

from backfill_props import estimate_credits, load_sample, snapshot_for, task_name
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams

OC = {"morning_et": "10:00", "closing_minutes_before_start": 10}


def test_snapshots():
    assert snapshot_for("closing", "2025-10-09T23:00:00Z", "2025-10-09", OC) == \
        "2025-10-09T22:50:00Z"
    assert snapshot_for("morning", "2025-10-09T23:00:00Z", "2025-10-09", OC) == \
        "2025-10-09T14:00:00Z"


def test_cost_matches_the_plan():
    # docs/market_discovery_plan.md 4.3: 330 games x 3 markets x 10 = 9 900
    assert estimate_credits(330, 3, 0) == 9900
    assert estimate_credits(330, 2, 44) == 6644


def test_morning_and_closing_are_separate_tasks():
    m = ["player_total_saves", "player_shots_on_goal"]
    assert task_name(m, "closing") != task_name(m, "morning")
    assert task_name(m, "closing") == task_name(list(reversed(m)), "closing")


def test_sample_is_whole_days(conn):
    games = []
    for day in range(1, 21):
        for k in range(3):
            g = game(2025020000 + day * 10 + k)
            games.append((f"2025-10-{day:02d}", g))
    for d, g in games:
        teams, rows = parse_week(week([g], date=d), "2025-26")
        upsert_teams(conn, teams)
        upsert_games(conn, rows)
    all_games, days, sample = load_sample(conn, "2025-26", 10)
    assert len(all_games) == 60 and len(days) == 4 and len(sample) == 12
    assert {g["game_date"] for g in sample} == set(days)

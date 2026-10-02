from datetime import datetime, timedelta, timezone

from conftest import game, load_fixture, week

from nhl_tool import boxscore, odds_live, toi
from nhl_tool.odds_import import (build_roster_lookup, find_event, insert_odds_rows,
                                  normalize_name, parse_event_odds)
from nhl_tool.sampling import sample_days, spread_order
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams

OC = {"sport": "icehockey_nhl", "regions": "us",
      "markets": ["player_shots_on_goal", "player_total_saves"],
      "reserve_live": 2000}


def _seed(conn, games=None):
    teams, rows = parse_week(week(games or [game(2025020010)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, rows)
    parsed = boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json"))
    boxscore.store(conn, parsed, [])
    toi.store(conn, toi.parse_rows(load_fixture("toi_2025-10-09.json")))


def _event_payload():
    return {"id": "ev1", "bookmakers": [{"key": "draftkings", "markets": [
        {"key": "player_shots_on_goal", "outcomes": [
            {"name": "Over", "description": "Andrew Copp", "point": 1.5, "price": 1.8},
            {"name": "Under", "description": "Andrew Copp", "point": 1.5, "price": 2.0},
            {"name": "Over", "description": "Somebody Else", "point": 2.5, "price": 1.9},
            {"name": "Over", "description": "No Line", "price": 1.9}]}]}]}


def test_normalize_name():
    assert normalize_name("Montréal Canadiens") == "montreal canadiens"
    assert normalize_name("St. Louis Blues") == normalize_name("St Louis Blues")
    assert normalize_name("Tim Stützle") == "tim stutzle"
    assert normalize_name("J.T. Miller") == "jt miller"


def test_find_event_by_name_and_time():
    events = [
        {"id": "a", "home_team": "Detroit Red Wings", "away_team": "Montreal Canadiens",
         "commence_time": "2025-10-09T23:00:00Z"},
        {"id": "b", "home_team": "Detroit Red Wings", "away_team": "Montreal Canadiens",
         "commence_time": "2025-12-01T23:00:00Z"},
        {"id": "c", "home_team": "St Louis Blues", "away_team": "Utah Mammoth",
         "commence_time": "2025-10-09T00:00:00Z"}]
    assert find_event(events, "Detroit Red Wings", "Montréal Canadiens",
                      "2025-10-09T23:00:00Z") == "a"
    assert find_event(events, "St. Louis Blues", "Utah Mammoth",
                      "2025-10-09T00:00:00Z") == "c"
    # same pairing, wrong date: never the other game
    assert find_event(events, "Detroit Red Wings", "Montréal Canadiens",
                      "2026-03-01T23:00:00Z") is None


def test_parse_and_insert_with_roster_match(conn):
    _seed(conn)
    rows = parse_event_odds(_event_payload(), "player_shots_on_goal")
    assert len(rows) == 3                        # outcome without a point is dropped
    roster = build_roster_lookup(conn, 2025020010)
    n, unmatched = insert_odds_rows(conn, rows, event_id="ev1", game_id=2025020010,
                                    market="player_shots_on_goal",
                                    snapshot_time="2025-10-09T22:50:00Z",
                                    snapshot_kind="closing", roster=roster)
    assert n == 3 and unmatched == {"Somebody Else"}
    pid = conn.execute("SELECT player_id FROM odds WHERE player_name_raw = 'Andrew Copp'"
                       " AND snapshot_kind = 'closing' LIMIT 1").fetchone()[0]
    assert pid == 8477429
    # re-inserting the same snapshot adds nothing
    n2, _ = insert_odds_rows(conn, rows, event_id="ev1", game_id=2025020010,
                             market="player_shots_on_goal",
                             snapshot_time="2025-10-09T22:50:00Z",
                             snapshot_kind="closing", roster=roster)
    assert n2 == 0


def test_spread_order_prefix_is_even():
    days = [f"d{i:03d}" for i in range(180)]
    prefix = spread_order(days)[:45]
    quarters = [sum(1 for d in prefix if int(d[1:]) // 45 == q) for q in range(4)]
    assert max(quarters) - min(quarters) <= 2
    assert spread_order(days) == spread_order(list(reversed(days)))   # deterministic


def test_sample_days_stops_at_target_and_keeps_whole_days():
    per_day = {f"2025-10-{i:02d}": 7 for i in range(1, 31)}
    picked = sample_days(per_day, 50)
    assert sum(per_day[d] for d in picked) >= 50
    assert sum(per_day[d] for d in picked[:-1]) < 50


class FakeClient:
    def __init__(self):
        self.calls = []
        self.last_remaining = 50000

    def get(self, path, **params):
        self.calls.append(path)
        if path.endswith("/events"):
            return [{"id": "ev1", "home_team": "Detroit Red Wings",
                     "away_team": "Montreal Canadiens",
                     "commence_time": "2025-10-09T23:00:00Z"}], {}
        return _event_payload(), {}


def test_morning_prices_unstarted_games_once(conn):
    _seed(conn)
    games = odds_live.todays_games(conn, "2025-10-09")
    now = datetime(2025, 10, 9, 14, 0, tzinfo=timezone.utc)
    due = odds_live.due_now(games, set(), now, "morning", 10, 20)
    assert [g["game_id"] for g in due] == [2025020010]
    client = FakeClient()
    stats = odds_live.collect(conn, client, due, kind="morning", oc=OC, now=now)
    assert stats["games"] == 1 and stats["rows"] == 3
    kinds = {r[0] for r in conn.execute(
        "SELECT DISTINCT snapshot_kind FROM odds WHERE snapshot_kind IS NOT NULL")}
    assert kinds == {"morning"}
    done = odds_live.done_keys(conn, "morning")
    assert odds_live.due_now(games, done, now, "morning", 10, 20) == []


def test_closing_window():
    g = {"game_id": 1, "start_time_utc": "2025-10-09T23:00:00Z"}
    moment = datetime(2025, 10, 9, 22, 50, tzinfo=timezone.utc)
    due = lambda t: odds_live.due_now([g], set(), t, "closing", 10, 20)  # noqa: E731
    assert due(moment) and due(moment + timedelta(minutes=5))
    assert not due(moment + timedelta(minutes=15))     # 5 min into the game (the old bug)
    assert not due(moment - timedelta(minutes=10))     # too early: not a closing line
    assert not due(moment + timedelta(minutes=25))     # mid-game: not a closing line
    assert not due(moment + timedelta(minutes=10))     # exactly puck drop: too late
    assert due(moment + timedelta(minutes=9, seconds=59))
    # the cloud job (every 10 min) prices from 30 min before puck drop
    cloud = lambda t: odds_live.due_now([g], set(), t, "closing", 10, 20, early_min=20)  # noqa: E731
    assert cloud(moment - timedelta(minutes=20)) and not cloud(moment - timedelta(minutes=21))
    assert odds_live.next_wakeup([g], set(), moment - timedelta(hours=1), 10) == moment
    assert odds_live.next_wakeup([g], {"1"}, moment - timedelta(hours=1), 10) is None


def test_reserve_stops_live_collection(conn):
    _seed(conn)
    games = odds_live.todays_games(conn, "2025-10-09")
    client = FakeClient()
    client.last_remaining = 1500
    stats = odds_live.collect(conn, client, games, kind="morning", oc=OC,
                              now=datetime(2025, 10, 9, 14, tzinfo=timezone.utc))
    assert stats.get("stopped_reserve") and stats["rows"] == 0


def test_watcher_follows_the_wall_clock_through_system_sleep():
    """30. 9.: one long sleep did not advance while the lid was closed and the
    watcher hung for days. A system sleep shows up as the wall clock jumping
    forward between two chunks; the watcher must notice and stop waiting."""
    t0 = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)
    clock = {"now": t0}
    slept = []

    def fake_sleep(s):
        slept.append(s)
        clock["now"] += timedelta(seconds=s)
        if len(slept) == 3:                         # lid closed for 9 hours
            clock["now"] += timedelta(hours=9)

    target = t0 + timedelta(hours=8)
    odds_live.sleep_until(target, now_fn=lambda: clock["now"], sleep_fn=fake_sleep)
    assert len(slept) == 3 and max(slept) <= odds_live.SLEEP_CHUNK_S
    # after waking, the games whose closing passed are skipped, not priced late
    g = {"game_id": 1, "start_time_utc": "2026-10-01T23:00:00Z"}
    assert odds_live.due_now([g], set(), clock["now"], "closing", 10, 20) == []
    assert odds_live.next_wakeup([g], set(), clock["now"], 10) is None


def test_odds_key_from_environment_is_validated(monkeypatch):
    import pytest
    from nhl_tool.odds_client import OddsApiError, load_api_key
    monkeypatch.setenv("ODDS_API_KEY", " abc123DEF \n")
    assert load_api_key() == "abc123DEF"
    monkeypatch.setenv("ODDS_API_KEY", "abc 123SECRET")
    with pytest.raises(OddsApiError) as e:
        load_api_key()
    assert "SECRET" not in str(e.value)

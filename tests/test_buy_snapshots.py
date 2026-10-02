"""Buying the live season the day after (plan D4): what gets bought, that
nothing is bought twice, and that the switch keeps the wallet closed."""
from conftest import game, load_fixture, week

import buy_snapshots as bs
from nhl_tool import boxscore, toi
from nhl_tool.db import set_state
from nhl_tool.hist_odds import HistoricalBuyer
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams

OC = {"sport": "icehockey_nhl", "regions": "us", "morning_et": "10:00",
      "closing_minutes_before_start": 10,
      "markets": ["player_shots_on_goal", "player_total_saves", "player_blocked_shots"]}


def _seed(conn, with_box=True, state="OFF"):
    g = game(2025020010, state=state)
    g["season"] = 20262027
    g["id"] = 2026020010
    g["startTimeUTC"] = "2026-10-01T23:00:00Z"
    teams, games = parse_week(week([g], date="2026-10-01"), "2026-27")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    if with_box:
        box = load_fixture("boxscore_2025020010.json")
        box["id"] = 2026020010
        boxscore.store(conn, boxscore.parse_boxscore(box), [])
        rows = toi.parse_rows(load_fixture("toi_2025-10-09.json"))
        for r in rows:
            r["game_id"] = 2026020010
        toi.store(conn, rows)
    conn.commit()


def _kinds(items):
    return sorted(k for _, k in items)


def test_finished_game_with_box_score_needs_both_snapshots(conn):
    _seed(conn)
    assert _kinds(bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01")) == ["closing", "morning"]


def test_unfinished_or_unboxed_games_are_not_bought(conn):
    _seed(conn, with_box=False)
    assert bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01") == []


def test_outside_the_window_is_not_bought(conn):
    _seed(conn)
    assert bs.todo(conn, "2026-27", "2026-10-02", "2026-10-08") == []


def test_kind_already_collected_live_or_marked_is_not_bought_again(conn):
    _seed(conn)
    conn.execute("""INSERT INTO odds (event_id, game_id, market, side, line, price, bookmaker,
                    snapshot_time, snapshot_kind, player_name_raw)
                    VALUES ('e', 2026020010, 'player_shots_on_goal', 'over', 2.5, 1.9, 'dk',
                            '2026-10-01T22:50:00Z', 'closing', 'X')""")
    assert _kinds(bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01")) == ["morning"]
    set_state(conn, bs.task("morning"), "2026020010", "missing", "event not found")
    assert bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01") == []


class FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, path, **params):
        self.calls.append((path, params.get("date")))
        if path.endswith("/events"):
            return [{"id": "ev1", "home_team": "Detroit Red Wings",
                     "away_team": "Montreal Canadiens",
                     "commence_time": "2026-10-01T23:00:00Z"}], {}
        return {"timestamp": params["date"], "data": {"bookmakers": [
            {"key": "draftkings", "markets": [{"key": "player_shots_on_goal", "outcomes": [
                {"name": "Over", "description": "Andrew Copp", "point": 1.5, "price": 1.8},
                {"name": "Under", "description": "Andrew Copp", "point": 1.5, "price": 2.0}]}]}]}}, {}


def test_buyer_prices_at_the_pre_registered_moments(conn):
    _seed(conn)
    items = bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01")
    client = FakeClient()
    buyer = HistoricalBuyer(conn, client, OC, OC["markets"])
    for g, kind in items:
        res = buyer.price(g, kind)
        assert res["status"] == "done" and res["rows"]["player_shots_on_goal"] == 2
    odds_calls = [d for p, d in client.calls if p.endswith("/odds")]
    assert "2026-10-01T22:50:00Z" in odds_calls          # closing = puck drop - 10 min
    assert "2026-10-01T14:00:00Z" in odds_calls          # morning = 10:00 EDT
    events_calls = [p for p, _ in client.calls if p.endswith("/events")]
    assert len(events_calls) == 1                        # one events list per day, reused
    kinds = {r[0] for r in conn.execute("SELECT DISTINCT snapshot_kind FROM odds"
                                        " WHERE snapshot_kind IN ('morning', 'closing')")}
    assert kinds == {"morning", "closing"}


def test_switch_off_buys_nothing(conn, monkeypatch, tmp_path, capsys):
    """With hist_daily_enabled false the script must exit before creating a
    client: no key read, no request, no credit."""
    _seed(conn)
    import sqlite3
    db = tmp_path / "nhl.db"
    disk = sqlite3.connect(db)
    conn.backup(disk)
    disk.close()
    cfg = {"live": {"season": "2026-27"},
           "odds": {**OC, "hist_daily_enabled": False, "hist_daily_days": 7,
                    "hist_daily_budget": 1000, "reserve_backfill": 15000}}
    monkeypatch.setattr(bs, "load_config", lambda: cfg)
    monkeypatch.setattr(bs, "resolve_db_path", lambda c: db)

    def boom(*a, **k):
        raise AssertionError("a client was created while the switch is off")
    import nhl_tool.odds_client as oc_mod
    monkeypatch.setattr(oc_mod, "OddsClient", boom)
    monkeypatch.setattr("sys.argv", ["buy_snapshots.py", "--until", "2026-10-01"])
    bs.main()
    assert "VYPNUTO" in capsys.readouterr().out


def test_snapshot_at_or_after_puck_drop_is_never_bought(conn):
    """The inconsistency the first version of this test had (morning anchor
    after puck drop) must be refused, not priced: a line from a game under
    way is no entry price."""
    _seed(conn)
    conn.execute("UPDATE games SET start_time_utc = '2026-10-01T13:30:00Z'")  # 09:30 ET
    items = [x for x in bs.todo(conn, "2026-27", "2026-09-25", "2026-10-01") if x[1] == "morning"]
    client = FakeClient()
    res = HistoricalBuyer(conn, client, OC, OC["markets"]).price(items[0][0], "morning")
    assert res["status"] == "missing" and not any(p.endswith("/odds") for p, _ in client.calls)

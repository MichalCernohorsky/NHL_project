"""Main lines for models v2, block B: parsing, storing only pre-game rows,
the cost, and the rule that nothing is bought without the go-ahead or above
the user's cap."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from nhl_tool import main_lines as ml  # noqa: E402

EVENT = {"id": "ev1", "commence_time": "2025-10-07T23:00:00Z",
         "home_team": "Montréal Canadiens", "away_team": "St Louis Blues",
         "bookmakers": [
             {"key": "bookA", "markets": [
                 {"key": "h2h", "outcomes": [{"name": "Montréal Canadiens", "price": 1.80},
                                             {"name": "St Louis Blues", "price": 2.10}]},
                 {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 6.5},
                                                {"name": "Under", "price": 1.87, "point": 6.5}]},
                 {"key": "spreads", "outcomes": [{"name": "Montréal Canadiens", "price": 2.6, "point": -1.5}]}]},
             {"key": "bookB", "markets": [
                 {"key": "h2h", "outcomes": [{"name": "St Louis Blues", "price": 2.05},
                                             {"name": "Montréal Canadiens", "price": 1.83},
                                             {"name": "Draw", "price": 4.2}]}]}]}


def _game(conn, gid=2025020001, start="2025-10-07T23:00:00Z"):
    conn.executemany("INSERT OR IGNORE INTO teams (team_id, abbreviation, full_name) VALUES (?, ?, ?)",
                     [(8, "MTL", "Montréal Canadiens"), (19, "STL", "St. Louis Blues")])
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, game_state)
                    VALUES (?, '2025-26', 'regular', '2025-10-07', ?, 8, 19, 'OFF')""", (gid, start))
    conn.commit()


def test_parse_event_sides_and_lines():
    rows = ml.parse_event(EVENT)
    got = {(r["bookmaker"], r["market"], r["side"]): (r["line"], r["price"]) for r in rows}
    assert got == {("bookA", "h2h", "home"): (None, 1.80), ("bookA", "h2h", "away"): (None, 2.10),
                   ("bookA", "totals", "over"): (6.5, 1.95), ("bookA", "totals", "under"): (6.5, 1.87),
                   ("bookB", "h2h", "away"): (None, 2.05), ("bookB", "h2h", "home"): (None, 1.83)}


def test_store_only_before_puck_drop_and_once(conn):
    _game(conn)
    days = ml.days_to_buy(conn, ["2025-26"])
    assert list(days) == ["2025-10-07"] and days["2025-10-07"][0]["home"] == "Montréal Canadiens"
    payload = {"timestamp": "2025-10-07T14:55:00Z", "data": [EVENT]}
    res = ml.store_snapshot(conn, payload, days["2025-10-07"])
    assert res == {"matched": 1, "started": 0, "rows": 6}
    assert ml.store_snapshot(conn, payload, days["2025-10-07"])["rows"] == 0          # idempotent
    row = conn.execute("SELECT * FROM main_odds WHERE bookmaker = 'bookA' AND market = 'totals' "
                       "AND side = 'over' AND snapshot_kind = 'day'").fetchone()
    assert (row["line"], row["price"], row["snapshot_time"], row["event_id"]) == \
        (6.5, 1.95, "2025-10-07T14:55:00Z", "ev1")
    # a game that had started by the snapshot gets nothing
    _game(conn, gid=2025020002, start="2025-10-07T13:00:00Z")
    early = [g for g in ml.days_to_buy(conn, ["2025-26"])["2025-10-07"] if g["game_id"] == 2025020002]
    assert ml.store_snapshot(conn, payload, early) == {"matched": 0, "started": 1, "rows": 0}
    assert conn.execute("SELECT COUNT(*) FROM main_odds WHERE game_id = 2025020002").fetchone()[0] == 0


def test_cost_and_anchor():
    assert ml.CREDITS_PER_CALL == 20 and ml.estimate(528) == 10560
    assert ml.anchor("2025-10-07") == "2025-10-07T15:00:00Z"


def test_script_is_dry_by_default_and_refuses_above_the_cap():
    src = (ROOT / "scripts" / "buy_main_lines.py").read_text()
    buy_at = src.index("if not args.buy:")
    assert src.index("OddsClient()") > buy_at                    # no client, no key before the gate
    assert "if over or not todo:" in src and src.index("if over or not todo:") < src.index("OddsClient()")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "buy_main_lines.py"), "--help"],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "--buy" in out.stdout


def test_workflow_buys_only_on_the_go_ahead():
    import yaml
    text = (ROOT / ".github" / "workflows" / "mainlines.yml").read_text()
    wf = yaml.safe_load(text)
    trig = wf[True] if True in wf else wf["on"]
    assert set(trig) == {"workflow_dispatch"} and wf["concurrency"]["group"] == "nhl-db"
    steps = wf["jobs"]["mainlines"]["steps"]
    with_key = [s for s in steps if "ODDS_API_KEY" in str(s.get("env", ""))]
    assert len(with_key) == 1 and with_key[0]["if"] == "inputs.confirm == 'jed'"
    assert "--buy" in with_key[0]["run"]
    dry = next(s for s in steps if s.get("name", "").startswith("Suchy"))
    assert "--buy" not in dry["run"] and "env" not in dry
    assert trig["workflow_dispatch"]["inputs"]["budget"]["default"] == "10500"


def test_goals_from_a_total_line():
    assert ml.poisson_over(6.0, 5.5) == pytest.approx(1 - sum(
        2.718281828459045 ** -6 * 6 ** k / __import__("math").factorial(k) for k in range(6)))
    for lam, line in ((5.8, 5.5), (6.4, 6.5), (6.1, 6.0), (5.2, 6.0)):
        assert ml.goals_from_total(ml.poisson_over(lam, line), line) == pytest.approx(lam, abs=1e-6)
    # an even price on 6.5 means a mean a little above 6.5; on a whole line 6 a little above 6
    assert 6.6 < ml.goals_from_total(0.5, 6.5) < 6.8 and 6.1 < ml.goals_from_total(0.5, 6.0) < 6.3
    assert ml.goals_from_total(0.6, 6.5) > ml.goals_from_total(0.5, 6.5)


def test_game_script_needs_three_books(conn):
    _game(conn)
    books = [("a", 1.80, 2.10, 6.5, 1.95, 1.87), ("b", 1.83, 2.05, 6.5, 1.91, 1.91), ("c", 1.77, 2.15, 6.0, 1.80, 2.02)]

    def put(rows):
        for b, home, away, line, over, under in rows:
            for market, side, ln, price in (("h2h", "home", None, home), ("h2h", "away", None, away),
                                            ("totals", "over", line, over), ("totals", "under", line, under)):
                conn.execute("""INSERT INTO main_odds (game_id, event_id, bookmaker, market, side, line, price,
                                    snapshot_time, snapshot_kind) VALUES (2025020001, 'e', ?, ?, ?, ?, ?,
                                    '2025-10-07T14:55:00Z', 'day')""", (b, market, side, ln, price))
    put(books[:2])
    two = ml.game_script(conn).iloc[0]
    assert two["books_p_home"] == 2 and two["p_home"] != two["p_home"] and two["goals"] != two["goals"]   # NaN
    put(books[2:])
    r = ml.game_script(conn).iloc[0]
    ps = sorted((1 / h) / (1 / h + 1 / a) for _, h, a, *_ in books)
    assert r["p_home"] == pytest.approx(ps[1]) and 0.5 < r["p_home"] < 0.56
    gs = sorted(ml.goals_from_total((1 / o) / (1 / o + 1 / u), line) for *_, line, o, u in books)
    assert r["goals"] == pytest.approx(gs[1]) and r["books_goals"] == 3
    assert ml.game_script(conn, kind="live").empty


def test_renamed_team_is_matched_by_place_and_time():
    game = {"home": "Utah Mammoth", "away": "St. Louis Blues", "start_time_utc": "2024-11-05T02:00:00Z"}
    events = [{"id": "x", "commence_time": "2024-11-05T02:10:00Z", "home_team": "Utah Hockey Club",
               "away_team": "St Louis Blues"},
              {"id": "y", "commence_time": "2024-11-07T02:00:00Z", "home_team": "Utah Hockey Club",
               "away_team": "St Louis Blues"},
              {"id": "z", "commence_time": "2024-11-05T00:00:00Z", "home_team": "New York Rangers",
               "away_team": "New York Islanders"}]
    assert ml.match_event(events, game) == "x"
    # the two New York teams are never confused: the other side must agree too
    ny = {"home": "New York Islanders", "away": "Boston Bruins", "start_time_utc": "2024-11-05T00:00:00Z"}
    assert ml.match_event(events, ny) is None
    assert ml.match_event(events, {**game, "start_time_utc": "2024-11-06T02:00:00Z"}) is None


def test_purchase_stops_early_when_snapshots_cannot_be_read():
    assert ml.coverage_stop(2, 0, 20) is None
    assert "zadny zapas" in ml.coverage_stop(3, 0, 20)
    assert ml.coverage_stop(3, 1, 20) is None and ml.coverage_stop(24, 10, 180) is None
    assert "pod 80" in ml.coverage_stop(25, 100, 180) and ml.coverage_stop(25, 150, 180) is None
    src = (ROOT / "scripts" / "buy_main_lines.py").read_text()
    assert src.index("ml.coverage_stop(") < src.index('client.get(f"/historical')

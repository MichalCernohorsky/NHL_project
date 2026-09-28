from conftest import game, load_fixture, week

from nhl_tool import boxscore, toi
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams


def _seed_game(conn):
    teams, games = parse_week(week([game(2025020010)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)


def _load(conn):
    box = load_fixture("boxscore_2025020010.json")
    rail = load_fixture("right_rail_2025020010.json")
    parsed = boxscore.parse_boxscore(box)
    scratches = boxscore.parse_scratches(rail, 2025020010, 17, 8)
    boxscore.store(conn, parsed, scratches)
    return parsed


def test_parse_boxscore_fields():
    parsed = boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json"))
    copp = next(s for s in parsed["skaters"] if s["player_id"] == 8477429)
    assert copp["toi_s"] == 16 * 60 + 3 and copp["sog"] == 1
    assert copp["blocked_shots"] == 1 and copp["team_id"] == 17
    gibson = next(g for g in parsed["goalies"] if g["player_id"] == 8476434)
    assert gibson["started"] == 1 and gibson["saves"] == 8
    assert gibson["shots_against"] == 13 and gibson["pp_shots_against"] == 4
    assert gibson["toi_s"] == 37 * 60 + 12
    # exactly one starter per team
    for team_id in (17, 8):
        assert sum(g["started"] for g in parsed["goalies"] if g["team_id"] == team_id) == 1


def test_store_is_idempotent(conn):
    _seed_game(conn)
    _load(conn)
    counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("player_game_logs", "goalie_game_logs", "team_game_logs", "scratches")]
    _load(conn)
    again = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("player_game_logs", "goalie_game_logs", "team_game_logs", "scratches")]
    assert counts == again == [6, 4, 2, 4]


def test_scratches_carry_full_names(conn):
    _seed_game(conn)
    _load(conn)
    names = {r[0] for r in conn.execute("SELECT full_name FROM scratches")}
    assert "Erik Gustafsson" in names


def test_toi_split_fills_box_score_rows_and_reports_orphans(conn):
    _seed_game(conn)
    _load(conn)
    rows = toi.parse_rows(load_fixture("toi_2025-10-09.json"))
    unmatched = toi.store(conn, rows)
    assert unmatched == 1                      # the fixture's fake player
    filled = conn.execute(
        "SELECT COUNT(*) FROM player_game_logs WHERE pp_toi_s IS NOT NULL").fetchone()[0]
    assert filled == 6
    # EV + PP + SH adds up to total TOI (box score) for every skater
    for r in conn.execute("SELECT toi_s, ev_toi_s, pp_toi_s, sh_toi_s FROM player_game_logs"):
        assert r["ev_toi_s"] + r["pp_toi_s"] + r["sh_toi_s"] == r["toi_s"]
    named = conn.execute("SELECT COUNT(*) FROM players WHERE full_name IS NOT NULL"
                         " AND position != 'G'").fetchone()[0]
    assert named == 6


def test_toi_query_is_per_day():
    p = toi.day_params("2025-10-09")
    assert 'gameDate="2025-10-09"' in p["cayenneExp"] and p["isGame"] == "true"

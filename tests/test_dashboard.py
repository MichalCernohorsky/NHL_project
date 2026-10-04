"""Every dashboard page renders without an exception on a small database,
and on an empty one (the first morning of a season)."""
import shutil
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from conftest import game, load_fixture, week  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIEWS = sorted((ROOT / "dashboard" / "views").glob("*.py"))


def _build_db(path: Path, with_data: bool):
    from migrate import apply_migrations, ensure_migrations_table
    from nhl_tool import boxscore, odds_import, pbp, toi
    from nhl_tool.schedule import parse_week, upsert_games, upsert_teams
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_migrations_table(conn)
    apply_migrations(conn)
    if with_data:
        teams, games = parse_week(week([game(2025020010)]), "2025-26")
        upsert_teams(conn, teams)
        upsert_games(conn, games)
        parsed = boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json"))
        boxscore.store(conn, parsed, [])
        toi.store(conn, toi.parse_rows(load_fixture("toi_2025-10-09.json")))
        conn.execute("UPDATE player_game_logs SET sog_reg = sog, blocked_shots_reg = blocked_shots")
        conn.execute("UPDATE goalie_game_logs SET saves_reg = saves")
        roster = odds_import.build_roster_lookup(conn, 2025020010)
        odds_import.insert_odds_rows(
            conn, [{"bookmaker": "draftkings", "player_name": "Andrew Copp", "side": s,
                    "line": 1.5, "price": p} for s, p in (("over", 1.8), ("under", 2.0))],
            event_id="e1", game_id=2025020010, market="player_shots_on_goal",
            snapshot_time="2025-10-09T14:00:00Z", snapshot_kind="morning", roster=roster)
        _today_with_tips(conn)
    conn.commit()
    conn.close()


def _today_with_tips(conn):
    """A finished game today (ET) with a settled tip, a pending one with the
    big-disagreement warning, and a candidate that is not a tip."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, home_score, away_score, last_period_type,
                        game_state) VALUES (2026029999, '2026-27', 'regular', ?, ?, 17, 8, 3, 2,
                        'REG', 'OFF')""", (today, f"{today}T23:00:00Z"))
    base = dict(model="t", game_id=2026029999, game_date=today, start_time_utc=f"{today}T23:00:00Z",
                team_id=17, opp_id=8, market="player_shots_on_goal", mu_60=1.4, p_market=0.5,
                books=3, best_book="dk", best_price=1.9, sim_tipsport_price=1.84,
                entry_live=1, gp_season=0, gp_prev=80, snapshot_kind="live",
                snapshot_time=f"{today}T14:00:00Z", built_at=f"{today}T15:00:00Z")
    factors = dict(f_rate_60=5.2, f_prior_60=6.0, f_season_shots=3.0, f_season_toi_min=33.0,
                   f_toi_l10_min=16.1, f_opp_factor=0.97, f_opp_mean=27.0, f_opp_n=2, pos_group="F")
    rows = [dict(base, **factors, tip_id="a", player_id=8477429, player_name="Andrew Copp", line=1.5,
                 side="under", p_model=0.6, edge=0.10 - 1e-9, tipsport_min_price=1.75, playable=1,
                 arm_top=1, actual_60=1, outcome="win", profit_units=0.84, settled_at=today),
            dict(base, tip_id="b", player_id=8475279, player_name="Ben Chiarot", line=2.5,
                 side="over", p_model=0.65, edge=0.15, tipsport_min_price=1.61, playable=1),
            dict(base, tip_id="c", player_id=8475279, player_name="Ben Chiarot", line=2.5,
                 side="under", p_model=0.35, edge=-0.15, tipsport_min_price=3.13, playable=0)]
    for r in rows:
        cols = ",".join(r)
        conn.execute(f"INSERT INTO tips ({cols}) VALUES ({','.join('?' * len(r))})", list(r.values()))


@pytest.fixture(params=[True, False], ids=["data", "empty"])
def db(tmp_path, monkeypatch, request):
    path = tmp_path / "nhl.db"
    _build_db(path, request.param)
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    return path


@pytest.mark.parametrize("view", VIEWS, ids=[v.stem for v in VIEWS])
def test_page_renders(db, view):
    at = AppTest.from_file(str(view), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]


def test_router_lists_every_view():
    app = (ROOT / "dashboard" / "app.py").read_text()
    for v in VIEWS:
        assert v.name in app, v.name


def test_tips_page_renders_cards_and_calculator(tmp_path, monkeypatch):
    path = tmp_path / "nhl.db"
    _build_db(path, True)
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    at = AppTest.from_file(str(ROOT / "dashboard" / "views" / "0_Tipy_dne.py"),
                           default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(m.value for m in at.markdown)
    assert "Andrew Copp" in page and "Ben Chiarot" in page
    assert "⚠" in page and "✅" in page                 # warning and a settled win
    assert "splňuje pravidlo" in page                   # calculator verdict rendered
    # contributions: only for the tip that has stored factors (Copp), in p.b.
    assert page.count("proč: střelba") == 1 and "soupeř" in page


def test_game_page_shows_reasons_and_decision_rows(tmp_path, monkeypatch):
    """Rozbor zápasu: tip rows, the 'why' breakdown for a tip with stored
    factors, and no crash for one without (older record)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    path = tmp_path / "nhl.db"
    _build_db(path, True)
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    at = AppTest.from_file(str(ROOT / "dashboard" / "views" / "6_Rozbor_zapasu.py"),
                           default_timeout=30)
    at.session_state["game_id"] = 2026029999
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Andrew Copp" in page and "⭐ TOP" in page
    assert "Proč model tipuje" in page and "Střelba hráče" in page
    assert "není uložený" in page                        # the tip without factors
    # the waterfall's reading: from the average player of the position to the model
    assert "průměrný útočník by sázku" in page and "Ve střelách: průměr" in page
    assert "zamčeno" in page or "vyšel" in page          # game finished: locked / settled


def test_my_bets_page_with_a_ticket(tmp_path, monkeypatch):
    from dashboard import bets
    path = tmp_path / "nhl.db"
    _build_db(path, True)
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    tip = {"tip_id": "a", "game_id": 2026029999, "game_date": "2099-01-01",
           "start_time_utc": "2099-01-01T00:00:00Z", "player_id": 8477429,
           "player_name": "Andrew Copp", "side": "under"}
    bets.decide(tip, "bet")
    bets.save_bet(tip, 1.5, 1.80, 200, "Tipsport")
    at = AppTest.from_file(str(ROOT / "dashboard" / "views" / "7_Moje_sazky.py"),
                           default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(m.value for m in at.markdown)
    assert "Andrew Copp" in page and "200 Kč" in page

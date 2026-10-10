"""Market-as-model, stage 2 (docs/topdown_plan.md 4): the ticket rule is
enforced in code - three books, a fresh US snapshot, the minimum price, the
lock at puck drop - and live odds can be refreshed at most three times."""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest  # noqa: E402

from dashboard import bets  # noqa: E402
from nhl_tool import odds_live  # noqa: E402
from test_dashboard import _build_db  # noqa: E402

NOW = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
ROW = {"game_id": 5, "game_date": "2026-10-20", "start_time_utc": "2026-10-20T23:00:00Z",
       "player_id": 10, "player_name": "P", "line": 2.5, "p_over": 0.50, "books": 4,
       "snapshot_time": "2026-10-20T15:30:00Z"}


def test_minimum_price_is_three_percent_over_fair():
    assert bets.fair_min_price(0.5) == pytest.approx(2.06)
    assert bets.fair_min_price(0.4) == pytest.approx(1.03 / 0.4)


def test_ticket_rule_is_enforced_in_code():
    ok = bets.save_fair_bet(ROW, "over", 2.10, 100, "Tipsport", True, now=NOW)
    assert ok["market"] == bets.FAIR and ok["paper"] is True
    assert ok["p_fair"] == 0.5 and ok["ev"] == pytest.approx(0.05) and ok["min_price"] == pytest.approx(2.06)
    assert bets.fair_bets() == [ok] and bets.player_bets() == [] and bets.team_bets() == []
    with pytest.raises(ValueError, match="minimální kurz"):                 # below the minimum price
        bets.save_fair_bet(ROW, "over", 2.05, 100, "Tipsport", True, now=NOW)
    with pytest.raises(ValueError, match="aspoň 3"):                        # too few books
        bets.save_fair_bet({**ROW, "books": 2}, "over", 2.30, 100, "Tipsport", True, now=NOW)
    with pytest.raises(ValueError, match="starý"):                          # stale US snapshot
        bets.save_fair_bet(ROW, "over", 2.30, 100, "Tipsport", True, now=NOW + timedelta(minutes=45))
    with pytest.raises(bets.Locked):                                        # after puck drop
        bets.save_fair_bet({**ROW, "snapshot_time": "2026-10-20T22:59:00Z"}, "over", 2.30, 100,
                           "Tipsport", True, now=datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc))
    under = bets.save_fair_bet({**ROW, "p_over": 0.60}, "under", 2.60, 50, "Tipsport", False, now=NOW)
    assert under["p_fair"] == pytest.approx(0.40) and under["paper"] is False
    assert bets.settle(under, 2, True) == ("win", pytest.approx(80.0))
    assert len(bets.fair_bets()) == 2


def test_refresh_is_limited_to_three_extra_snapshots_and_games_not_started(conn):
    conn.executemany("INSERT INTO teams (team_id, abbreviation, full_name) VALUES (?, ?, ?)",
                     [(1, "AAA", "A"), (2, "BBB", "B")])
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, game_state)
                    VALUES (5, '2026-27', 'regular', '2026-10-20', '2026-10-20T23:00:00Z', 1, 2, 'FUT'),
                           (6, '2026-27', 'regular', '2026-10-20', '2026-10-20T15:00:00Z', 2, 1, 'LIVE')""")
    games = odds_live.todays_games(conn, "2026-10-20")
    markets = ["player_shots_on_goal"]
    assert [g["game_id"] for g in odds_live.refresh_due(conn, games, NOW, markets)] == [5]   # 6 has started
    for i in range(4):                                                    # the daily snapshot + 3 refreshes
        conn.execute("""INSERT INTO odds (event_id, game_id, player_name_raw, bookmaker, market, line,
                            side, price, snapshot_time, snapshot_kind)
                        VALUES ('e', 5, 'P', 'dk', 'player_shots_on_goal', 2.5, 'over', 1.9, ?, 'live')""",
                     (f"2026-10-20T1{i}:00:00Z",))
        left = odds_live.refresh_due(conn, games, NOW, markets)
        assert (len(left) == 1) == (i < 3)


def test_page_shows_fair_prices_and_refuses_a_stale_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "nhl.db"
    _build_db(path, True)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE games SET start_time_utc = '2099-01-01T00:00:00Z', game_state = 'FUT' "
                 "WHERE game_id = 2026029999")
    conn.execute("UPDATE tips SET start_time_utc = '2099-01-01T00:00:00Z'")
    conn.commit()
    conn.close()
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    at = AppTest.from_file(str(ROOT / "dashboard" / "views" / "9_Ferove_kurzy.py"),
                           default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    page = " ".join(m.value for m in at.markdown)
    assert "Ben Chiarot" in page and "min. kurz více" in page
    assert "2,06" in page                                   # 1.03 / 0.5
    assert "starý" in page and not at.selectbox             # old snapshot: no ticket form


def test_live_refresh_workflow_is_manual_and_locked():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "live.yml").read_text())
    trig = wf[True] if True in wf else wf["on"]
    assert set(trig) == {"workflow_dispatch"} and wf["concurrency"]["group"] == "nhl-db"
    run = " ".join(s.get("run", "") for s in wf["jobs"]["live"]["steps"])
    assert "collect_odds.py live --refresh" in run and "build_tips.py" in run

"""Team markets, stage 2 (docs/team_markets_plan.md 6, T-5): predictions are
written once before puck drop from earlier games only, the lines and the
minimum price follow the plan, settlement uses the 60-minute counts, and
team tickets live in the bets store next to the player ones."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dashboard import bets  # noqa: E402
from nhl_tool import team_tips  # noqa: E402

TEAMS = {1: "AAA", 2: "BBB", 3: "CCC", 4: "DDD"}
DAY = "2026-10-20"
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def _player(conn, pid):
    conn.execute("INSERT OR IGNORE INTO players (player_id, full_name) VALUES (?, ?)", (pid, f"P{pid}"))


def _db(conn, past_games=24):
    """Four teams, `past_games` finished games with 60-minute counts on
    earlier days, and two games on DAY (one already started)."""
    conn.executemany("INSERT INTO teams (team_id, abbreviation, full_name) VALUES (?, ?, ?)",
                     [(t, ab, ab) for t, ab in TEAMS.items()])
    rng = np.random.default_rng(1)
    gid = 1000
    for i in range(past_games):
        date = f"2026-09-{1 + i % 28:02d}" if i < 28 else "2026-10-01"
        home, away = (1 + i % 4), (1 + (i + 1) % 4)
        gid += 1
        conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                            home_team_id, away_team_id, home_score, away_score, game_state)
                        VALUES (?, '2026-27', 'regular', ?, ?, ?, ?, 2, 1, 'OFF')""",
                     (gid, date, f"{date}T23:00:00Z", home, away))
        for team in (home, away):
            shots = int(rng.poisson(28))
            _player(conn, team * 100 + i)
            conn.execute("""INSERT INTO player_game_logs (game_id, player_id, team_id, position,
                                toi_s, sog, sog_reg, pim) VALUES (?, ?, ?, 'C', 1000, ?, ?, 0)""",
                         (gid, team * 100 + i, team, shots, shots))
            for e in range(int(rng.poisson(3))):
                conn.execute("""INSERT INTO penalties (game_id, event_id, team_id, period, period_type,
                                    type_code, duration) VALUES (?, ?, ?, 1, 'REG', 'MIN', 2)""",
                             (gid, team * 10 + e, team))
        conn.executemany("INSERT INTO backfill_state (task, key, status, updated_at) VALUES (?, ?, 'done', 'x')",
                         [("pbp", str(gid)), ("penalties", str(gid)), ("boxscore", str(gid))])
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, game_state)
                    VALUES (2001, '2026-27', 'regular', ?, ?, 1, 2, 'FUT'),
                           (2002, '2026-27', 'regular', ?, ?, 3, 4, 'LIVE')""",
                 (DAY, f"{DAY}T23:00:00Z", DAY, f"{DAY}T14:00:00Z"))
    conn.commit()


def test_lines_and_minimum_price_follow_the_plan():
    models = team_tips.load_models()
    assert team_tips.lines_for("S-T", 27.4) == [24.5, 25.5, 26.5, 27.5, 28.5, 29.5]
    assert team_tips.lines_for("S-T", 27.6) == [25.5, 26.5, 27.5, 28.5, 29.5, 30.5]
    assert team_tips.lines_for("T-T", 3.2) == [3.5, 4.5]
    p = team_tips.p_over("S-T", 27.4, 26.5, models)
    assert 0.5 < p < 0.7
    assert team_tips.p_over("T-T", 3.3, 5.5, models) is None          # no calibration there
    assert 0.3 < team_tips.p_over("T-T", 3.3, 3.5, models) < 0.5
    t = team_tips.table("T-T", 3.3, models)
    assert t["line"].tolist() == [3.5, 4.5] and (t["p_over"] + t["p_under"] == 1).all()
    assert t["min_over"][0] == pytest.approx(1 / (t["p_over"][0] - 0.03))
    assert team_tips.min_price(0.02) is None


def test_build_writes_once_before_puck_drop_and_settles(conn):
    _db(conn)
    stats = team_tips.build(conn, DAY, NOW)
    assert stats["games"] == 2 and stats["inserted"] == 4 and stats["started"] == 4
    rows = conn.execute("SELECT game_id, team_id, market, mu, f_n, model FROM team_predictions "
                        "ORDER BY game_id, team_id, market").fetchall()
    assert [(r["game_id"], r["team_id"], r["market"]) for r in rows] == \
        [(2001, 1, "S-T"), (2001, 1, "T-T"), (2001, 2, "S-T"), (2001, 2, "T-T")]
    assert all(r["mu"] > 0 for r in rows) and all(r["f_n"] > 0 for r in rows)
    assert {r["model"] for r in rows} == {"naive_team_v1", "naive_team_v1+naive_team_tt_cal"}
    shots = [r["mu"] for r in rows if r["market"] == "S-T"]
    assert 20 < shots[0] < 36 and 1.5 < [r["mu"] for r in rows if r["market"] == "T-T"][0] < 5
    # a second build the same day writes nothing new, even with different past data
    conn.execute("UPDATE player_game_logs SET sog_reg = sog_reg + 10")
    assert team_tips.build(conn, DAY, NOW)["inserted"] == 0
    assert conn.execute("SELECT mu FROM team_predictions WHERE game_id = 2001 AND team_id = 1 "
                        "AND market = 'S-T'").fetchone()[0] == shots[0]
    # settlement: nothing until the game is final and its counts loaded
    assert team_tips.settle(conn, DAY) == 0
    conn.execute("UPDATE games SET game_state = 'OFF' WHERE game_id = 2001")
    assert team_tips.settle(conn, DAY) == 0
    for pid in (1, 2):
        _player(conn, pid)
    conn.executemany("INSERT INTO player_game_logs (game_id, player_id, team_id, position, toi_s, sog, sog_reg) "
                     "VALUES (2001, ?, ?, 'C', 900, ?, ?)", [(1, 1, 31, 30), (2, 2, 22, 22)])
    conn.executemany("INSERT INTO penalties (game_id, event_id, team_id, period, period_type, type_code, duration) "
                     "VALUES (2001, ?, ?, ?, ?, ?, ?)",
                     [(1, 1, 1, "REG", "MIN", 2), (2, 1, 2, "REG", "MIN", 4), (3, 1, 3, "OT", "MIN", 2),
                      (4, 1, 1, "REG", "MAJ", 5), (5, 2, 1, "REG", "BEN", 2)])
    conn.executemany("INSERT INTO backfill_state (task, key, status, updated_at) VALUES (?, '2001', 'done', 'x')",
                     [("pbp",), ("penalties",)])
    assert team_tips.settle(conn, DAY) == 4
    got = {(r["team_id"], r["market"]): r["actual_60"] for r in
           conn.execute("SELECT team_id, market, actual_60 FROM team_predictions WHERE game_id = 2001")}
    assert got == {(1, "S-T"): 30, (1, "T-T"): 3, (2, "S-T"): 22, (2, "T-T"): 1}


def test_features_come_from_earlier_days_only(conn):
    _db(conn)
    before = team_tips.frame_for(conn, DAY, "shots")
    today = before[before["game_date"] == DAY]
    assert len(today) == 4 and today["y"].isna().all()
    assert today["n"].between(1, 20).all() and today["L_t"].isna().all()   # < 100 league rows
    # a finished game ON the day must not feed the day's features
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, game_state)
                    VALUES (2003, '2026-27', 'regular', ?, ?, 1, 3, 'OFF')""", (DAY, f"{DAY}T17:00:00Z"))
    for pid in (7, 8):
        _player(conn, pid)
    conn.executemany("INSERT INTO player_game_logs (game_id, player_id, team_id, position, toi_s, sog, sog_reg) "
                     "VALUES (2003, ?, ?, 'C', 900, 90, 90)", [(7, 1), (8, 3)])
    conn.execute("INSERT INTO backfill_state (task, key, status, updated_at) VALUES ('pbp', '2003', 'done', 'x')")
    after = team_tips.frame_for(conn, DAY, "shots")
    a = after[(after["game_date"] == DAY) & (after["team_id"] == 1) & (after["game_id"] == 2001)].iloc[0]
    b = today[today["team_id"] == 1].iloc[0]
    assert a["form_for"] == pytest.approx(b["form_for"])


def test_team_tickets_in_the_bets_store():
    pred = {"market": "S-T", "game_id": 2001, "game_date": DAY, "start_time_utc": f"{DAY}T23:00:00Z",
            "team_id": 1, "tym": "AAA", "souper": "BBB", "mu": 27.9}
    b = bets.save_team_bet(pred, 27.5, 1.88, 100, "Tipsport", "over", True, now=NOW)
    assert b["paper"] is True and b["market"] == "S-T" and "player_id" not in b
    assert bets.team_bets() == [b] and bets.player_bets() == []
    assert bets.settle(b, 31, True) == ("win", pytest.approx(88.0))
    assert bets.settle(b, 27, True) == ("loss", -100.0)
    with pytest.raises(bets.Locked):
        bets.save_team_bet(pred, 27.5, 1.88, 100, "Tipsport", "over", False,
                           now=datetime(2026, 10, 21, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        bets.save_team_bet({**pred, "market": "S-Z"}, 50.5, 1.9, 100, "Tipsport", "over", True, now=NOW)
    # team penalties are paused (plan amendment T-6): refused in code, not only hidden
    assert bets.paused("T-T", DAY) and bets.paused("T-T", "2026-09-30") and not bets.paused("S-T", DAY)
    assert not bets.paused("T-T", "2026-11-01") and not bets.paused("T-T", "2027-01-15")
    with pytest.raises(ValueError, match="netipují"):
        bets.save_team_bet({**pred, "market": "T-T"}, 3.5, 1.9, 100, "Tipsport", "under", True, now=NOW)
    assert len(bets.team_bets()) == 1
    november = {**pred, "market": "T-T", "game_date": "2026-11-03", "start_time_utc": "2026-11-03T23:00:00Z"}
    ok = bets.save_team_bet(november, 3.5, 1.9, 100, "Tipsport", "under", True,
                            now=datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc))
    assert ok["market"] == "T-T" and len(bets.team_bets()) == 2
    # a player ticket stays a player ticket
    tip = {"tip_id": "x", "game_id": 2001, "player_id": 5, "side": "over",
           "start_time_utc": f"{DAY}T23:00:00Z"}
    bets.save_bet(tip, 2.5, 1.9, 50, "Tipsport", now=NOW)
    assert len(bets.player_bets()) == 1 and len(bets.team_bets()) == 2


def test_daily_workflow_builds_team_tips_after_player_tips():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "daily.yml").read_text())
    names = [s.get("name") for s in wf["jobs"]["daily"]["steps"]]
    assert names.index("Tipy dne a vyhodnoceni") < names.index("Tymove trhy") < names.index("Ulozeni databaze")
    crons = [c["cron"] for c in (wf[True] if True in wf else wf["on"])["schedule"]]
    assert all(int(c.split()[1]) >= 11 for c in crons) and len(crons) >= 5     # not before 11:30 UTC

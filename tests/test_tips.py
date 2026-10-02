"""Tips: the rule of plan 6.4 on the frozen model, 60-minute market
conversion, one tip per player, settlement and the MODEL arm's payout."""
import pandas as pd
import pytest

from nhl_tool import naive_sog as ns
from nhl_tool import tips

MODEL = {"model": "test", "nb_k": 16.84, "ot_ratio": {"F": 0.0137, "D": 0.0108},
         "league_team_shots": 28.9, "prior_rate_per_s": {"F": 7.0 / 3600, "D": 4.1 / 3600}}


def _lines(rows):
    out = []
    for pid, book, line, over, under in rows:
        for side, price in (("over", over), ("under", under)):
            out.append({"game_id": 1, "player_id": pid, "player_name_raw": f"P{pid}",
                        "bookmaker": book, "line": line, "side": side, "price": price,
                        "snapshot_time": "2026-10-02T14:00:00Z",
                        "start_time_utc": "2026-10-02T23:00:00Z", "game_date": "2026-10-02"})
    return pd.DataFrame(out)


def _pred(rows):
    return pd.DataFrame([{"game_id": 1, "player_id": pid, "team_id": 1, "opp_id": 2,
                          "group": "F", "mu_60": mu, "entry_live": entry, "gp_before": 0,
                          "prev_gp": 80} for pid, mu, entry in rows])


def test_rule_picks_one_side_per_player_at_3_points():
    lines = _lines([(10, "dk", 2.5, 2.10, 1.75), (10, "fd", 2.5, 2.05, 1.80),
                    (10, "dk", 1.5, 1.45, 2.80), (20, "dk", 2.5, 1.90, 1.90)])
    pred = _pred([(10, 1.6, True), (20, ns.mu_from_p_over(0.5, 2.5, 16.84), True)])
    c = tips.candidates(lines, pred, MODEL, 0.0875)
    play = c[c.playable]
    assert list(play.player_id) == [10]                    # player 20: model = market
    top = play.iloc[0]
    assert top.side == "under" and top.edge >= 0.03
    # best book per (line, side): the edge is the max over books
    under25 = c[(c.player_id == 10) & (c.line == 2.5) & (c.side == "under")].iloc[0]
    assert under25.books == 2 and under25.best_price == 1.80
    # 60-minute conversion lowers the market's over probability
    p_full = tips.devig_over(1.90, 1.90)
    assert c[(c.player_id == 20) & (c.side == "over")].p_market.iloc[0] < p_full
    assert top.tipsport_min_price == pytest.approx(1 / (top.p_model - 0.03))
    assert top.sim_tipsport_price == pytest.approx(1 / (top.p_market * 1.0875))


def test_no_entry_no_tip():
    c = tips.candidates(_lines([(10, "dk", 2.5, 2.10, 1.75)]), _pred([(10, 1.2, False)]),
                        MODEL, 0.0875)
    assert not c.playable.any() and len(c) == 2


def test_whole_number_lines_are_skipped():
    c = tips.candidates(_lines([(10, "dk", 2.0, 2.10, 1.75)]), _pred([(10, 1.2, True)]),
                        MODEL, 0.0875)
    assert c.empty


def test_store_and_settle(conn):
    from conftest import game, load_fixture, week

    from nhl_tool import boxscore
    from nhl_tool.schedule import parse_week, upsert_games, upsert_teams
    from nhl_tool.db import set_state
    teams, games = parse_week(week([game(2025020010)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    boxscore.store(conn, boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json")), [])
    conn.execute("UPDATE player_game_logs SET sog_reg = 1 WHERE player_id = 8477429")
    set_state(conn, "pbp", "2025020010", "done")
    cand = pd.DataFrame([{
        "game_id": 2025020010, "player_id": pid, "player_name": "X", "line": 1.5, "side": side,
        "book": "dk", "price": 1.9, "p_model": 0.6, "p_market": 0.5, "edge": 0.1, "mu_60": 1.2,
        "team_id": 17, "opp_id": 8, "entry_live": True, "gp_season": 0, "gp_prev": 80,
        "snapshot_time": "2025-10-09T14:00:00Z", "start_time_utc": "2025-10-09T23:00:00Z",
        "books": 3, "best_price": 1.9, "sim_tipsport_price": 1.84, "tipsport_min_price": 1.75,
        "playable": True} for pid, side in ((8477429, "under"), (9999, "over"))])
    assert tips.store(conn, cand, "test", "2025-10-09", "live") == 2
    assert tips.store(conn, cand, "test", "2025-10-09", "live") == 0   # written once
    assert tips.settle(conn, "2025-10-09") == 2
    res = {r[0]: r[1:] for r in conn.execute(
        "SELECT player_id, outcome, actual_60, profit_units FROM tips")}
    assert res[8477429] == ("win", 1, pytest.approx(0.84))             # 1 shot < 1.5, under wins
    assert res[9999] == ("void", None, 0.0)                             # did not play
    assert tips.settle(conn, "2025-10-09") == 0                         # never twice

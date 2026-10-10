"""Phase 0 evaluation (docs/market_discovery_plan.md 6, D1-D3): the rule,
the payout and the settlement are exactly the plan's - checked on small
hand-made markets, never on the purchased data."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns  # noqa: E402
from nhl_tool import phase0  # noqa: E402

MODEL = {"nb_k": 16.84, "ot_ratio": {"F": 0.0137, "D": 0.0108}}
M = 0.0874


def _lines(quotes):
    """quotes: (game, player, book, line, over, under-or-None)"""
    rows = []
    for g, p, book, line, over, under in quotes:
        base = dict(game_id=g, game_date="2025-11-01", player_id=p, player_name_raw=f"P{p}",
                    bookmaker=book, line=line, snapshot_time="x", start_time_utc="y")
        rows.append({**base, "side": "over", "price": over})
        if under is not None:
            rows.append({**base, "side": "under", "price": under})
    return pd.DataFrame(rows)


def _feats(rows):
    """rows: (game, player, mu_60, sog, sog_reg, toi_s, entry)"""
    return pd.DataFrame([dict(game_id=g, player_id=p, group="F", mu_60=mu, mu_full=mu * 1.0137,
                              sog=sog, sog_reg=reg, toi_s=toi, entry_phase0=entry, game_date="2025-11-01")
                         for g, p, mu, sog, reg, toi, entry in rows])


def test_both_sides_consensus_and_main_line():
    lines = _lines([(1, 7, "a", 2.5, 1.90, 1.90), (1, 7, "b", 2.5, 2.00, 1.80), (1, 7, "c", 2.5, 2.10, 1.72),
                    (1, 7, "a", 3.5, 3.00, 1.40), (1, 7, "b", 3.5, 3.10, 1.36), (1, 7, "c", 3.5, 3.20, 1.33),
                    (1, 7, "d", 1.5, 1.40, None),                    # one side only: not a quote
                    (1, 7, "d", 3.0, 2.50, 1.50)])                   # whole-number line: dropped
    wide = phase0.both_sides(lines)
    assert set(wide["line"]) == {2.5, 3.5} and len(wide) == 6
    cons = phase0.consensus(wide)
    at25 = cons[cons["line"] == 2.5].iloc[0]
    assert at25["books"] == 3
    assert at25["p_over_full"] == pytest.approx((1 / 2.00) / (1 / 2.00 + 1 / 1.80))   # the median book
    assert at25["best_over"] == 2.10 and at25["best_under"] == 1.90
    main = phase0.main_lines(cons)
    assert len(main) == 1 and main["line"][0] == 2.5                # 3 books each: the lower line


def test_one_bet_per_player_from_the_largest_edge_and_paid_at_the_consensus():
    # player 7: three books at 2.5; book "c" is the outlier that makes the edge largest
    lines = _lines([(1, 7, "a", 2.5, 1.90, 1.90), (1, 7, "b", 2.5, 1.92, 1.88), (1, 7, "c", 2.5, 2.30, 1.60),
                    (1, 7, "a", 3.5, 3.00, 1.40),
                    (1, 8, "a", 1.5, 1.90, 1.90), (1, 8, "b", 1.5, 1.90, 1.90),    # no edge
                    (1, 9, "a", 2.5, 2.60, 1.50),                                   # edge, but too few games
                    (1, 10, "a", 2.5, 2.60, 1.50)])                                 # edge, but did not play
    feats = _feats([(1, 7, 3.0, 4, 2, 900, True), (1, 8, 1.68, 1, 1, 900, True),
                    (1, 9, 3.0, 5, 5, 900, False), (1, 10, 3.0, 0, 0, 0, True)])
    wide = phase0.both_sides(lines)
    cons = phase0.consensus(wide)
    bets = phase0.select_bets(wide, cons, feats, MODEL, M)
    assert bets["player_id"].tolist() == [7]                        # one bet, one player
    b = bets.iloc[0]
    assert (b["line"], b["side"], b["bookmaker"]) == (2.5, "over", "c")
    k = MODEL["nb_k"]
    p_model = float(ns.p_over(3.0, 2.5, k)[0])
    p_book = ns.market_p_60((1 / 2.30) / (1 / 2.30 + 1 / 1.60), 2.5, k, 0.0137)
    assert b["edge"] == pytest.approx(p_model - p_book, abs=1e-6) and b["edge"] >= 0.03
    # the payout comes from the consensus (median book "b"), not from the outlier that was selected
    p_cons = ns.market_p_60((1 / 1.92) / (1 / 1.92 + 1 / 1.88), 2.5, k, 0.0137)
    assert b["p_market"] == pytest.approx(p_cons, abs=1e-6)
    assert b["price_tipsport"] == pytest.approx(1 / (p_cons * (1 + M)), abs=1e-6)
    assert b["price_tipsport"] < 1 / (p_book * (1 + M))             # the outlier would have paid more
    assert b["price_us"] == 2.30                                    # best US price of the side: secondary
    # 60 minutes for Tipsport (2 shots: lost), the full game for the US books (4 shots: won)
    assert b["won"] == 0 and b["profit_units"] == -1.0 and b["profit_us"] == pytest.approx(1.30)


def test_under_side_is_selected_and_settled_on_60_minutes():
    lines = _lines([(2, 7, "a", 2.5, 1.60, 2.30), (2, 7, "b", 2.5, 1.62, 2.26)])
    feats = _feats([(2, 7, 1.6, 3, 2, 900, True)])                   # few shots expected -> under
    wide = phase0.both_sides(lines)
    bets = phase0.select_bets(wide, phase0.consensus(wide), feats, MODEL, M)
    b = bets.iloc[0]
    assert b["side"] == "under" and b["won"] == 1                    # 2 in 60 minutes: under 2.5 wins
    assert b["profit_units"] == pytest.approx(b["price_tipsport"] - 1)
    assert b["profit_us"] == -1.0                                    # 3 with overtime: the book's under lost
    assert b["p_model"] == pytest.approx(1 - float(ns.p_over(1.6, 2.5, MODEL["nb_k"])[0]))
    assert b["p_market"] + 0.0 < 0.5 + 0.2                           # a probability, of the under side


def test_k4a_uses_the_full_game_and_the_threshold():
    rng = np.random.default_rng(1)
    n = 400
    mu = rng.uniform(1.5, 3.5, n)
    sog = rng.poisson(mu * 1.0137)
    cons = pd.DataFrame({"game_id": np.arange(n), "game_date": [f"d{i % 40}" for i in range(n)],
                         "player_id": 7, "line": 2.5, "books": 3,
                         "p_over_full": [float(ns.p_over(m * 1.0137, 2.5, 16.84)[0]) for m in mu],
                         "best_over": 1.9, "best_under": 1.9})
    feats = pd.DataFrame({"game_id": np.arange(n), "player_id": 7, "mu_full": mu * 1.0137, "sog": sog,
                          "toi_s": 900, "entry_phase0": True})
    rows = phase0.brier_rows(cons, feats, 16.84)
    res = phase0.k4a(rows, n_boot=500)
    assert res["n"] == n and res["gap"] == pytest.approx(0.0, abs=1e-9) and res["pass"]
    bad = rows.assign(p_model=0.5 + (rows["p_model"] - 0.5) * -1)    # an inverted model
    assert not phase0.k4a(bad, n_boot=500)["pass"]
    cal = phase0.calibration(rows, "p_market")
    assert cal["n"].sum() == n and len(cal) == 10
    # players without ice time or below the entry rule are not rows
    feats.loc[:9, "toi_s"] = 0
    feats.loc[10:19, "entry_phase0"] = False
    assert len(phase0.brier_rows(cons, feats, 16.84)) == n - 20


def test_null_simulation_cannot_beat_the_margin():
    bets = pd.DataFrame({"p_market": np.full(1500, 0.52), "price_tipsport": 1 / (0.52 * (1 + M)),
                         "game_date": "d"})
    res = phase0.null_sim(bets, sims=500)
    assert res["roi_mean"] == pytest.approx(1 / (1 + M) - 1, abs=0.01)   # about -8 %
    assert res["pass_rate"] < 0.01
    fair = bets.assign(price_tipsport=1 / 0.52)
    assert 0.3 < phase0.null_sim(fair, sims=500)["pass_rate"] < 0.7     # without margin: a coin flip


def test_k4b_and_k5_follow_the_plan():
    bets = pd.DataFrame({"game_date": np.repeat([f"d{i}" for i in range(20)], 10),
                         "profit_units": np.tile([0.9, -1.0], 100), "profit_us": np.tile([1.0, -1.0], 100),
                         "won": np.tile([1, 0], 100), "price_tipsport": 1.9, "p_model": 0.56,
                         "p_market": 0.48, "edge": 0.05, "side": "over"})
    res = phase0.k4b(bets, sample_days=40, n_boot=500)
    assert res["n"] == 200 and res["roi"] == pytest.approx(-0.05) and not res["pass"]
    assert res["per_day"] == 5.0 and res["hit"] == 0.5 and res["break_even"] == pytest.approx(1 / 1.9)
    assert res["roi_us"] == pytest.approx(0.0)
    assert phase0.k5(10.0, 24.0, 6.0) == {"per_day_all": 10.0, "players_per_game": 24.0,
                                         "per_day_tipsport": 2.5, "pass": False}
    assert phase0.k5(13.0, 24.0, 6.0)["pass"]
    assert phase0.k4b(bets.iloc[:0], sample_days=40)["pass"] is False

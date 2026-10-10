"""Stage 1 of the market-as-model plan (docs/topdown_plan.md 3, TD-1): the
leave-one-book-out rule and the two simulations, on hand-made markets."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import phase0, topdown  # noqa: E402


def _lines(quotes, day="2025-11-01"):
    rows = []
    for g, p, book, line, over, under in quotes:
        base = dict(game_id=g, game_date=day, player_id=p, player_name_raw=f"P{p}", bookmaker=book,
                    line=line, snapshot_time="x", start_time_utc="y")
        rows += [{**base, "side": "over", "price": over}, {**base, "side": "under", "price": under}]
    return pd.DataFrame(rows)


RESULTS = pd.DataFrame({"game_id": [1, 1, 1], "player_id": [7, 8, 9], "sog": [3, 1, 4],
                        "toi_s": [900, 900, 0]})


def test_fair_price_comes_from_the_other_books_only():
    # four books at 2.5; "soft" pays far more for the over than the rest
    wide = phase0.both_sides(_lines([(1, 7, "a", 2.5, 1.90, 1.90), (1, 7, "b", 2.5, 1.92, 1.88),
                                     (1, 7, "c", 2.5, 1.88, 1.92), (1, 7, "soft", 2.5, 2.30, 1.62)]))
    cand = topdown.loo_candidates(wide)
    assert len(cand) == 4
    soft = cand[cand["bookmaker"] == "soft"].iloc[0]
    others = sorted([(1 / 1.90) / (1 / 1.90 + 1 / 1.90), (1 / 1.92) / (1 / 1.92 + 1 / 1.88),
                     (1 / 1.88) / (1 / 1.88 + 1 / 1.92)])
    assert soft["p_others"] == pytest.approx(others[1])              # its own quote is left out
    assert soft["ev_over"] == pytest.approx(2.30 * others[1] - 1) and soft["ev_over"] > 0.03
    a = cand[cand["bookmaker"] == "a"].iloc[0]
    assert a["p_others"] != soft["p_others"]                          # the outlier is among a's others
    bets = topdown.select_bets(cand, RESULTS)
    assert bets["bookmaker"].tolist() == ["soft"] and bets["side"][0] == "over"
    assert bets["won"][0] == 1 and bets["profit_units"][0] == pytest.approx(1.30)   # 3 shots > 2.5
    assert bets["p_fair"][0] == pytest.approx(others[1])


def test_needs_three_other_books_and_ice_time_and_one_bet_per_book():
    wide = phase0.both_sides(_lines([
        (1, 8, "a", 1.5, 1.90, 1.90), (1, 8, "b", 1.5, 1.90, 1.90), (1, 8, "soft", 1.5, 2.60, 1.45),   # 2 others
        (1, 9, "a", 2.5, 1.90, 1.90), (1, 9, "b", 2.5, 1.90, 1.90), (1, 9, "c", 2.5, 1.90, 1.90),
        (1, 9, "soft", 2.5, 2.60, 1.45),                                                              # no ice time
        (1, 7, "a", 2.5, 1.90, 1.90), (1, 7, "b", 2.5, 1.90, 1.90), (1, 7, "c", 2.5, 1.90, 1.90),
        (1, 7, "soft", 2.5, 2.20, 1.66),
        (1, 7, "a", 3.5, 3.00, 1.38), (1, 7, "b", 3.5, 3.00, 1.38), (1, 7, "c", 3.5, 3.00, 1.38),
        (1, 7, "soft", 3.5, 3.80, 1.25)]))
    cand = topdown.loo_candidates(wide)
    assert 8 not in set(cand["player_id"])                           # only two other books
    bets = topdown.select_bets(cand, RESULTS)
    assert bets["player_id"].tolist() == [7]                         # player 9 did not play
    b = bets.iloc[0]
    # two lines qualify at "soft"; the one with the larger expected value is the bet
    ev25, ev35 = 2.20 * 0.5 - 1, 3.80 * ((1 / 3.0) / (1 / 3.0 + 1 / 1.38)) - 1
    assert (b["line"], b["ev"]) == ((2.5, pytest.approx(ev25)) if ev25 > ev35 else (3.5, pytest.approx(ev35)))
    assert b["won"] == (1 if 3 > b["line"] else 0)


def test_summary_and_the_two_simulations():
    rng = np.random.default_rng(3)
    quotes = []
    for g in range(300):
        p = rng.uniform(0.40, 0.60)                                   # the truth the three books share
        fair_over, fair_under = 1 / p, 1 / (1 - p)
        for book in ("a", "b", "c"):
            quotes.append((g, 7, book, 2.5, fair_over / 1.03, fair_under / 1.03))
        quotes.append((g, 7, "soft", 2.5, fair_over * 1.06, fair_under / 1.12))   # pays 6 % over fair
    days = {g: f"d{g % 30}" for g in range(300)}
    lines = _lines(quotes)
    lines["game_date"] = lines["game_id"].map(days)
    wide = phase0.both_sides(lines)
    cand = topdown.loo_candidates(wide)
    truth = {g: float(cand[(cand.game_id == g) & (cand.bookmaker == "soft")]["p_others"].iloc[0])
             for g in range(300)}
    res = pd.DataFrame({"game_id": range(300), "player_id": 7, "toi_s": 900,
                        "sog": [3 if rng.random() < truth[g] else 2 for g in range(300)]})
    bets = topdown.select_bets(cand, res)
    assert set(bets["bookmaker"]) == {"soft"} and len(bets) == 300 and (bets["side"] == "over").all()
    s = topdown.summary(bets, n_boot=500)
    assert s["n"] == 300 and s["ev_rule"] == pytest.approx(0.06, abs=0.005)
    assert s["pass"] == (s["roi"] > 0) and s["supported"] == (s["lo"] > 0)
    sim = topdown.simulate(bets, wide, 16.84, sims=400)
    assert sim["holds_mean"] == pytest.approx(0.06, abs=0.03) and sim["holds_positive"] > 0.6
    assert sim["null_mean"] < 0 and sim["null_positive"] < sim["holds_positive"]
    assert topdown.summary(bets.iloc[:0]) == {"n": 0, "pass": False}

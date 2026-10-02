"""Naive shots model (plan 6.2 + D3 + D6): distribution maths, shrinkage,
entry rules, and above all that a game's features never see that game or
any later one."""
import math

import numpy as np
import pandas as pd
import pytest

from nhl_tool import naive_sog as ns

CONST = {"league_team_shots": 28.0, "prior_rate_per_s": {"F": 2.0 / 3600, "D": 1.2 / 3600},
         "ot_ratio": {"F": 0.015, "D": 0.012}}


def _frame(n_games=30, seasons=("2024-25", "2025-26"), seed=1):
    """Two teams (1, 2) playing each other, two skaters each, synthetic."""
    rng = np.random.default_rng(seed)
    rows, gid = [], 0
    for season in seasons:
        y = int(season[:4])
        for i in range(n_games):
            gid += 1
            date = f"{y}-11-01" if i == 0 else str(pd.Timestamp(f"{y}-11-01") + pd.Timedelta(days=i))[:10]
            for team, opp in ((1, 2), (2, 1)):
                for pid, pos in ((team * 10 + 1, "C"), (team * 10 + 2, "D")):
                    sog = int(rng.poisson(2.5 if pos == "C" else 1.2))
                    rows.append({"game_id": gid, "game_date": date, "season": season,
                                 "player_id": pid, "team_id": team, "opp_id": opp,
                                 "position": pos, "toi_s": 1100, "ot_toi_s": 0,
                                 "sog": sog, "sog_reg": sog})
    df = pd.DataFrame(rows)
    df["toi_reg"] = df["toi_s"] - df["ot_toi_s"]
    df["group"] = df["position"].map(ns.pos_group)
    return df


def test_nb_pmf_is_a_distribution_with_the_right_mean():
    pmf = ns.nb_pmf_upto([0.7, 2.4, 5.0], 8.0, 80)
    assert np.allclose(pmf.sum(axis=1), 1.0, atol=1e-9)
    assert np.allclose(pmf @ np.arange(81), [0.7, 2.4, 5.0], atol=1e-6)


def test_large_k_is_poisson():
    mu = 2.3
    pois = [math.exp(-mu) * mu ** y / math.factorial(y) for y in range(6)]
    assert np.allclose(ns.nb_pmf_upto(mu, 1e7, 5)[0], pois, atol=1e-5)


def test_p_over_and_its_inversion():
    for line in (0.5, 1.5, 2.5, 3.5):
        p = ns.p_over(2.2, line, 15.0)[0]
        assert abs(ns.mu_from_p_over(p, line, 15.0) - 2.2) < 1e-6
    assert ns.p_over(3.0, 2.5, 15.0)[0] > ns.p_over(2.0, 2.5, 15.0)[0]


def test_market_conversion_to_60_minutes_lowers_the_over():
    p_full = 0.55
    p60 = ns.market_p_60(p_full, 2.5, 15.0, 0.015)
    assert p60 < p_full and p_full - p60 < 0.02


def test_dispersion_fit_recovers_k():
    rng = np.random.default_rng(3)
    mu = rng.uniform(1.0, 4.0, 20000)
    k_true = 6.0
    y = rng.poisson(rng.gamma(k_true, mu / k_true))
    assert abs(ns.fit_dispersion(y, mu) - k_true) / k_true < 0.15


def test_no_game_sees_itself_or_the_future():
    df = _frame()
    base = ns.features(df, CONST)
    target = base[(base.season == "2025-26")].iloc[40]
    later = df.game_date >= target.game_date
    poisoned = df.copy()
    poisoned.loc[later, "sog"] = 99
    poisoned.loc[later, "sog_reg"] = 99
    poisoned.loc[later, "toi_s"] = 3000
    poisoned.loc[later, "toi_reg"] = 3000
    again = ns.features(poisoned, CONST)
    key = ["game_id", "player_id"]
    a = base.set_index(key).loc[tuple(target[key])]
    b = again.set_index(key).loc[tuple(target[key])]
    for col in ("r", "toi_l10", "o", "mu_60", "gp_before"):
        assert a[col] == pytest.approx(b[col]), col


def test_first_game_of_a_season_uses_the_prior_and_neutral_opponent():
    df = _frame()
    f = ns.features(df, CONST)
    first = f[(f.season == "2025-26") & (f.gp_before == 0)]
    assert (first["o"] == 1.0).all()
    # previous season had 30 games (>= 20): prior = last season's own rate
    row = first[first.player_id == 11].iloc[0]
    prev = df[(df.season == "2024-25") & (df.player_id == 11)]
    assert row["r"] == pytest.approx(prev.sog_reg.sum() / prev.toi_reg.sum())
    # first season in the data: position prior
    row0 = f[(f.season == "2024-25") & (f.gp_before == 0) & (f.player_id == 12)].iloc[0]
    assert row0["r"] == pytest.approx(CONST["prior_rate_per_s"]["D"])


def test_entry_rules():
    f = ns.features(_frame(), CONST)
    s2 = f[f.season == "2025-26"]
    assert not s2[s2.gp_before < 10]["entry_phase0"].any()
    assert s2[s2.gp_before >= 10]["entry_phase0"].all()
    # D6: 30 games last season -> live entry from game one
    assert s2["entry_live"].all()
    s1 = f[f.season == "2024-25"]
    assert not s1[s1.gp_before < 10]["entry_live"].any()


def test_shrinkage_weight_is_three_hours():
    f = ns.features(_frame(), CONST)
    row = f[(f.season == "2025-26") & (f.gp_before == 5)].iloc[0]
    expect = (row.S_before + row.r_prior * 3 * 3600) / (row.T_before + 3 * 3600)
    assert row.r == pytest.approx(expect)

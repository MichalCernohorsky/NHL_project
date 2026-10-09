"""Naive team models (docs/team_models.md): as-of features leak nothing,
the formula is the documented one, the counting rule is amendment T-1, and
the bootstrap is the project's (seed 17, days resampled)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns  # noqa: E402
from nhl_tool import stats  # noqa: E402
from nhl_tool import team_model as tm  # noqa: E402


def _league(seed=0, seasons=("2023-24", "2024-25"), teams=6, rounds=30, mean=28.0, home=1.05):
    """A small round-robin league: every round all teams play, one game a day per team."""
    rng = np.random.default_rng(seed)
    strength = dict(zip(range(1, teams + 1), rng.normal(1.0, 0.08, teams)))
    rows, gid = [], 0
    for s_i, season in enumerate(seasons):
        for r in range(rounds):
            date = (pd.Timestamp(f"{2023 + s_i}-10-01") + pd.Timedelta(days=2 * r)).date().isoformat()
            order = rng.permutation(np.arange(1, teams + 1))
            for a, b in zip(order[::2], order[1::2]):
                gid += 1
                ya = rng.poisson(mean * strength[a] * home)
                yb = rng.poisson(mean * strength[b] / home)
                rows.append((gid, season, date, a, b, 1, ya, yb))
                rows.append((gid, season, date, b, a, 0, yb, ya))
    return pd.DataFrame(rows, columns=["game_id", "season", "game_date", "team_id", "opp_id",
                                       "is_home", "y", "y_opp"])


def test_nb_logpmf_matches_the_player_model_pmf():
    mu, k = np.array([2.3, 27.0, 6.5]), 9.0
    y = np.array([0, 31, 6])
    want = np.log(ns.nb_pmf_upto(mu, k, 40)[np.arange(3), y])
    assert tm.nb_logpmf(y, mu, k) == pytest.approx(want)
    assert np.exp(tm.nb_logpmf(np.arange(200), np.full(200, 6.5), k)).sum() == pytest.approx(1.0)


def test_asof_uses_only_earlier_dates():
    df = _league()
    a = tm.add_asof(df)
    cols = ["L_t", "n", "form_for", "form_against", "season_for", "season_total",
            "prev_for", "prev_against"]
    cut = sorted(df["game_date"].unique())[40]
    changed = df.copy()
    late = changed["game_date"] >= cut
    changed.loc[late, ["y", "y_opp"]] += 50                    # the future and the same day change
    b = tm.add_asof(changed)
    early = a["game_date"] <= cut                               # incl. the games of `cut` itself
    # last season's level is a whole-season fact: only compare it for the first season
    first = a["season"] == "2023-24"
    pd.testing.assert_frame_equal(a.loc[early, cols[:6]], b.loc[early, cols[:6]])
    assert (a.loc[first, ["prev_for", "prev_against"]] == 1.0).all().all()
    assert (b.loc[~early, "form_for"] > a.loc[~early, "form_for"]).any()


def test_form_window_and_first_game_of_a_season():
    a = tm.add_asof(_league(rounds=30))
    team = a[(a["team_id"] == 1) & (a["season"] == "2024-25")].reset_index(drop=True)
    assert team.loc[0, "n"] == 0 and np.isnan(team.loc[0, "form_for"])
    assert team.loc[5, "form_for"] == pytest.approx(team.loc[:4, "y"].mean())
    assert team.loc[25, "n"] == tm.WINDOW
    assert team.loc[25, "form_for"] == pytest.approx(team.loc[5:24, "y"].mean())
    assert team.loc[25, "season_for"] == pytest.approx(team.loc[:24, "y"].mean())
    assert team.loc[5, "form_against"] == pytest.approx(team.loc[:4, "y_opp"].mean())
    # last season: team mean over league mean, both of 2023-24
    raw = _league(rounds=30)
    prev = raw[raw["season"] == "2023-24"]
    assert team.loc[0, "prev_for"] == pytest.approx(
        prev.loc[prev["team_id"] == 1, "y"].mean() / prev["y"].mean())


def test_prediction_is_the_documented_formula():
    a = tm.add_asof(_league())
    const = {"w": 8, "c": 0.5, "h": 1.04, "league_mean_train": 28.0}
    mu = tm.predict(a, const)
    i = a.index[(a["season"] == "2024-25") & (a["n"] == 7) & (a["is_home"] == 1)][0]
    row = a.loc[i]
    opp = a[(a["game_id"] == row["game_id"]) & (a["team_id"] == row["opp_id"])].iloc[0]
    L = row["L_t"]
    attack = (7 * row["form_for"] / L + 8 * (1 + 0.5 * (row["prev_for"] - 1))) / 15
    n_o = opp["n"]
    defence = (n_o * opp["form_against"] / opp["L_t"] + 8 * (1 + 0.5 * (opp["prev_against"] - 1))) / (n_o + 8)
    assert mu[i] == pytest.approx(L * attack * defence * 1.04)
    # the away row of the same game is divided by h
    j = opp.name
    assert mu[j] / (tm.predict(a, {**const, "h": 1.0})[j]) == pytest.approx(1 / 1.04)
    # first days of the data: no league history -> the training mean
    assert np.isnan(a.loc[0, "L_t"]) and tm.factors(a, 8, 0.5, 28.0).loc[0, "L"] == 28.0


def test_fit_stays_on_the_grid_and_finds_home_advantage():
    train = tm.add_asof(_league(seed=3, rounds=60, teams=8, home=1.06))
    const = tm.fit(train)
    assert const["w"] in tm.W_GRID and const["c"] in tm.C_GRID
    assert const["h"] == pytest.approx(1.06, abs=0.02)
    assert set(const["baselines"]) == {"z0", "z1"} and const["k_game"] > 0
    with pytest.raises(AssertionError):
        tm.fit(tm.add_asof(_league(seasons=("2024-25", "2025-26"))))   # validation season refused


def test_bootstrap_is_the_projects_bootstrap():
    rng = np.random.default_rng(5)
    df = pd.DataFrame({"game_date": rng.integers(0, 40, 600).astype(str),
                       "profit_units": rng.normal(0.1, 1.0, 600)})
    day_idx, counts = tm.boot_counts(df["game_date"].to_numpy())
    got = tm.mean_ci(df["profit_units"].to_numpy(), day_idx, counts)
    assert got == pytest.approx(stats.roi_ci(df))


def test_t1_passes_for_the_truth_and_fails_for_noise():
    rng = np.random.default_rng(11)
    n = 4000
    true_mu = rng.uniform(22, 34, n)
    y = rng.poisson(true_mu)
    days = np.repeat(np.arange(200), 20).astype(str)
    day_idx, counts = tm.boot_counts(days, n_boot=2000)
    flat = np.full(n, true_mu.mean())
    base_mu, base_k = {"z0": flat, "z1": flat}, {"z0": 500.0, "z1": 500.0}
    assert tm.t1(y, true_mu, 500.0, base_mu, base_k, day_idx, counts)["pass"]
    noise = rng.permutation(true_mu)
    res = tm.t1(y, noise, 500.0, base_mu, base_k, day_idx, counts)
    assert not res["pass"] and res["z0"]["gain"] < 0


def test_calibration_bands_cover_all_rows():
    rng = np.random.default_rng(2)
    mu = rng.uniform(24, 32, 1000)
    y = rng.poisson(mu)
    cal = tm.calibration(y, mu, 800.0, [25.5, 27.5, 29.5])
    assert cal["n"].sum() == 3000 and len(cal) == 5
    assert cal["predicted"].is_monotonic_increasing
    assert (cal["predicted"] - cal["observed"]).abs().max() < 0.08


def test_penalty_counting_rule_is_amendment_t1(conn):
    conn.executemany("INSERT INTO teams (team_id, abbreviation, full_name) VALUES (?, ?, ?)",
                     [(1, "AAA", "A"), (2, "BBB", "B")])
    conn.execute("""INSERT INTO games (game_id, season, season_type, game_date, start_time_utc,
                        home_team_id, away_team_id, game_state)
                    VALUES (10, '2024-25', 'regular', '2024-10-10', '2024-10-10T23:00:00Z', 1, 2, 'OFF'),
                           (11, '2024-25', 'regular', '2024-10-12', '2024-10-12T23:00:00Z', 2, 1, 'OFF')""")
    pens = [(10, 1, 1, 1, "REG", "MIN", 2), (10, 2, 1, 2, "REG", "MIN", 4),     # double minor = 2
            (10, 3, 1, 3, "REG", "BEN", 2), (10, 4, 1, 3, "REG", "MAJ", 5),     # bench counts, major not
            (10, 5, 1, 3, "REG", "MIS", 10), (10, 6, 1, 4, "OT", "MIN", 2),     # overtime not
            (10, 7, 2, 2, "REG", "MIN", 2), (10, 8, 2, 2, "REG", "PS", 0)]      # penalty shot not
    conn.executemany("""INSERT INTO penalties (game_id, event_id, team_id, period, period_type,
                            type_code, duration) VALUES (?, ?, ?, ?, ?, ?, ?)""", pens)
    conn.execute("INSERT INTO backfill_state (task, key, status, updated_at) "
                 "VALUES ('penalties', '10', 'done', 'x')")
    df = tm.load_team_games(conn, ["2024-25"], "penalties")
    assert len(df) == 2                                        # game 11 has no counts yet
    home = df[df["is_home"] == 1].iloc[0]
    assert (home["team_id"], home["y"], home["y_opp"]) == (1, 4, 1)
    away = df[df["is_home"] == 0].iloc[0]
    assert (away["team_id"], away["y"], away["y_opp"]) == (2, 1, 4)


# ------------------------------------------------- CMP (amendment T-3)

def test_cmp_is_a_distribution_with_the_requested_mean():
    mu = np.array([0.8, 3.3, 6.0])
    for nu in (0.7, 1.0, 1.4):
        pmf = np.exp(tm.cmp_logpmf_table(mu, nu))
        assert pmf.sum(axis=1) == pytest.approx(1.0)
        assert (pmf * np.arange(pmf.shape[1])).sum(axis=1) == pytest.approx(mu, rel=1e-6)


def test_cmp_with_nu_one_is_poisson_and_narrower_above_one():
    mu = np.array([3.3])
    y = np.arange(12)
    pois = np.array([-3.3 + k * np.log(3.3) - sum(np.log(np.arange(1, k + 1))) for k in y])
    assert tm.cmp_logpmf_table(mu, 1.0)[0, :12] == pytest.approx(pois, abs=1e-9)
    ys = np.arange(tm.CMP_YMAX + 1)
    var = lambda nu: float((np.exp(tm.cmp_logpmf_table(mu, nu))[0] * (ys - 3.3) ** 2).sum())  # noqa: E731
    assert var(1.0) == pytest.approx(3.3, rel=1e-6) and var(1.4) < 3.3 < var(0.7)
    # a narrower distribution puts less weight above a line that sits over the mean
    assert tm.cmp_p_over(mu, 4.5, 1.4)[0] < tm.cmp_p_over(mu, 4.5, 1.0)[0]
    assert tm.cmp_p_over(mu, 3.5, 1.0)[0] == pytest.approx(1 - np.exp(pois[:4]).sum())


def test_fit_nu_recovers_under_dispersion():
    rng = np.random.default_rng(4)
    mu = rng.uniform(2.6, 4.2, 6000)
    y = rng.binomial(18, mu / 18)                   # variance = mu * (1 - mu/18) < mu
    nu = tm.fit_nu(y, mu)
    assert 1.1 < nu < 1.5
    assert abs(tm.fit_nu(rng.poisson(mu), mu) - 1.0) < 0.06
    cal = tm.calibration(y, mu, nu, [3.5, 4.5], p_over=tm.cmp_p_over)
    assert (cal["predicted"] - cal["observed"]).abs().max() < 0.03


# ------------------------------------------- calibration (amendment T-4)

def test_logit_fit_recovers_known_parameters():
    rng = np.random.default_rng(8)
    x = rng.normal(1.2, 0.15, 20000)
    p = 1 / (1 + np.exp(-(-3.0 + 2.4 * x)))
    t = rng.random(20000) < p
    a, b = tm.logit_fit(x, t)
    assert a == pytest.approx(-3.0, abs=0.3) and b == pytest.approx(2.4, abs=0.25)
    assert tm.logit_p(np.exp(1.2), (a, b)) == pytest.approx(1 / (1 + np.exp(-(a + b * 1.2))))


def test_calibration_fixes_a_biased_distribution():
    rng = np.random.default_rng(9)
    mu = rng.uniform(2.6, 4.2, 8000)
    y = rng.binomial(18, mu / 18)                           # narrower than Poisson
    cal = tm.fit_calibration(y, mu)
    assert set(cal) == {3.5, 4.5}
    for line in tm.CAL_LINES:
        assert tm.logit_p(mu, cal[line]).mean() == pytest.approx((y > line).mean(), abs=0.01)
    loss, over = tm.cal_losses(y, mu, cal)
    assert loss.shape == over.shape == (16000,)
    assert over.mean() == pytest.approx(((y > 3.5).mean() + (y > 4.5).mean()) / 2)
    # a calibrated model loses less than the Poisson-based P(over) with the same mu
    pois = {line: (0.0, 0.0) for line in tm.CAL_LINES}      # placeholder, compared below
    p_pois = np.concatenate([tm.ns.p_over(mu, line, 5000.0) for line in tm.CAL_LINES])
    loss_pois = -(over * np.log(p_pois) + (1 - over) * np.log(1 - p_pois))
    assert loss.mean() < loss_pois.mean()
    cal_tab = tm.cal_calibration(y, mu, cal)
    assert cal_tab["n"].sum() == 16000 and (cal_tab["predicted"] - cal_tab["observed"]).abs().max() < 0.03


def test_t1_on_bernoulli_losses_uses_the_same_bootstrap():
    rng = np.random.default_rng(10)
    n = 3000
    mu = rng.uniform(2.6, 4.2, n)
    y = rng.poisson(mu)
    days = np.repeat(np.arange(150), 20).astype(str)
    cal = tm.fit_calibration(y, mu)
    flat = np.full(n, mu.mean())
    base = {"z0": tm.fit_calibration(y, flat), "z1": tm.fit_calibration(y, flat)}
    day_idx, counts = tm.boot_counts(np.tile(days, len(tm.CAL_LINES)), n_boot=2000)
    loss, _ = tm.cal_losses(y, mu, cal)
    res = tm.t1_losses(loss, {k: tm.cal_losses(y, flat, base[k])[0] for k in base}, day_idx, counts)
    assert res["pass"] and res["z0"]["gain"] > 0

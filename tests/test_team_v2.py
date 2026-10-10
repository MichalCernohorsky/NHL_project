"""Team models v2 (docs/models_v2_notes.md 1-4): the likelihood fit, the
as-of columns and the rule that nothing of a game or a later game enters
its own prediction."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_model as tm  # noqa: E402
from nhl_tool import team_v2 as t2  # noqa: E402

CONST = json.loads((ROOT / "models" / "naive_team.json").read_text())["families"]


def _frames(seed=3, teams=8, days=120, seasons=("2023-24", "2024-25")):
    """Synthetic league: every day half of the teams play (two games), so
    back-to-backs happen to some teams and not to others."""
    rng = np.random.default_rng(seed)
    shots, pens, att, refs = [], [], [], []
    gid = 0
    for s, season in enumerate(seasons):
        for d in range(days):
            date = (pd.Timestamp(f"{2023 + s}-10-01") + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
            order = rng.permutation(teams)[:teams // 2] + 1
            names = rng.permutation(["Ann", "Bob", "Cid", "Dan", "Eve", "Fay"])
            for g, (h, a) in enumerate(zip(order[::2], order[1::2])):
                gid += 1
                ys, yp = rng.poisson(28, 2), rng.poisson(3.3, 2)
                ya = ys + rng.poisson(27, 2)
                for team, opp, home, i in ((h, a, 1, 0), (a, h, 0, 1)):
                    base = dict(game_id=gid, season=season, game_date=date, team_id=int(team),
                                opp_id=int(opp), is_home=home)
                    shots.append({**base, "y": ys[i], "y_opp": ys[1 - i]})
                    pens.append({**base, "y": yp[i], "y_opp": yp[1 - i]})
                    att.append({"game_id": gid, "team_id": int(team), "att": ya[i]})
                for name in names[2 * g:2 * g + 2]:
                    refs.append({"game_id": gid, "name": name})
    return pd.DataFrame(shots), pd.DataFrame(pens), pd.DataFrame(att), pd.DataFrame(refs)


def _built(**kw):
    shots, pens, att, refs = _frames(**kw)
    b2b = t2.b2b_flags(pd.concat([shots[["game_id", "game_date", "team_id"]]]))
    return t2.build_frames(shots, pens, att, b2b, refs, CONST), (shots, pens, att, refs, b2b)


def test_nb_fit_recovers_known_coefficients():
    rng = np.random.default_rng(5)
    n = 40000
    X = np.column_stack([rng.normal(0, 1, n), rng.integers(0, 2, n)])
    offset = np.log(rng.uniform(20, 35, n))
    mu = np.exp(offset + X @ np.array([0.05, -0.08]))
    k = 60.0
    y = rng.negative_binomial(k, k / (k + mu))
    beta, k_hat = t2.nb_fit(y, offset, X)
    assert beta == pytest.approx([0.05, -0.08], abs=0.006)
    with_level = t2.nb_fit(y, offset, np.column_stack([np.ones(n), X]))[0]
    assert with_level == pytest.approx([0.0, 0.05, -0.08], abs=0.008)
    assert 45 < k_hat < 80
    # no signal -> coefficients near zero
    y0 = rng.negative_binomial(k, k / (k + np.exp(offset)))
    assert np.abs(t2.nb_fit(y0, offset, X)[0]).max() < 0.01


def test_back_to_back_is_the_previous_calendar_day():
    long = pd.DataFrame({"game_id": [1, 2, 3, 4, 5], "team_id": [7, 7, 7, 9, 9],
                         "game_date": ["2025-10-07", "2025-10-08", "2025-10-10", "2025-10-08", "2025-10-09"]})
    got = t2.b2b_flags(long).set_index("game_id")["b2b"].to_dict()
    assert got == {1: 0, 2: 1, 3: 0, 4: 0, 5: 1}


def test_columns_of_block_a():
    frames, _ = _built()
    s, p = frames["shots"], frames["penalties"]
    assert len(s) == len(p) == 2 * 2 * 120 * 2
    first = s[s["n_season"] == 0]
    assert (first["F1"] == 1).all() and (s.loc[s["n_season"] == 10, "F2"] == 1).all()
    assert (s.loc[s["n_season"] >= 20, ["F1", "F2"]].to_numpy() == 0).all()
    assert 0.3 < s["B_team"].mean() < 0.7 and (s["B_team"] != s["B_opp"]).mean() > 0.3
    # E of a row = opponent's own penalty factor x the team's drawing factor
    f = tm.factors(p, CONST["penalties"]["w"], CONST["penalties"]["c"],
                   CONST["penalties"]["league_mean_train"]).set_index(["game_id", "team_id"])
    r = p.iloc[500]
    e = f.at[(r["game_id"], r["opp_id"]), "attack"] * f.at[(r["game_id"], r["team_id"]), "defence"]
    assert r["E"] == pytest.approx(e) and r["D"] == pytest.approx(f.at[(r["game_id"], r["team_id"]), "L"] * (e - 1))
    assert s.merge(p[["game_id", "team_id", "D"]], on=["game_id", "team_id"])[["D_x", "D_y"]].diff(axis=1)["D_y"].abs().max() < 1e-12
    # alpha = 0 is exactly version 1; alpha = 1 uses the attempts form
    assert t2.base_mu(s, CONST["shots"]) == pytest.approx(tm.predict(s, CONST["shots"]))
    assert not np.allclose(t2.base_mu(s, CONST["shots"], 1.0, 55.0), tm.predict(s, CONST["shots"]))
    assert np.isfinite(t2.base_mu(s, CONST["shots"], 0.5, 55.0)).all()


def test_nothing_of_the_game_or_later_enters_its_columns():
    frames, (shots, pens, att, refs, b2b) = _built()
    cut = "2024-11-15"
    cols_s = ["form_for", "form_for_att", "form_against_att", "L_att", "E", "D", "F1", "F2", "B_team", "B_opp"]
    cols_p = ["E", "D", "R", "ref_n", "F1", "F2"]
    key = ["game_id", "team_id"]
    # change every count on and after the cut date: earlier AND same-day rows must not move
    s2, p2, a2 = shots.copy(), pens.copy(), att.copy()
    late = s2["game_date"] >= cut
    s2.loc[late, ["y", "y_opp"]] += 9
    p2.loc[p2["game_date"] >= cut, ["y", "y_opp"]] += 4
    a2.loc[a2["game_id"].isin(s2.loc[late, "game_id"]), "att"] += 30
    again = t2.build_frames(s2, p2, a2, b2b, refs, CONST)
    for fam, cols in (("shots", cols_s), ("penalties", cols_p)):
        a = frames[fam][frames[fam]["game_date"] <= cut].set_index(key)[cols]
        b = again[fam][again[fam]["game_date"] <= cut].set_index(key)[cols]
        pd.testing.assert_frame_equal(a, b.loc[a.index])
    after = frames["penalties"].set_index(key)["R"]
    assert not np.allclose(after, again["penalties"].set_index(key)["R"].loc[after.index])   # later rows do move


def test_referee_deviation_is_shrunk_and_from_the_past():
    frames, (_, pens, _, refs, _) = _built()
    p = frames["penalties"]
    first_day = p[p["game_date"] == p["game_date"].min()]
    assert (first_day["R"] == 0).all() and (first_day["ref_n"] == 0).all()
    # one referee by hand
    home = p[p["is_home"] == 1].set_index("game_id")
    mine = refs[refs["name"] == "Ann"].merge(home[["game_date", "y", "y_opp", "L_t"]], on="game_id") \
        .sort_values(["game_date", "game_id"]).reset_index(drop=True)
    dev = mine["y"] + mine["y_opp"] - 2 * mine["L_t"].fillna(CONST["penalties"]["league_mean_train"])
    d_ann = dev.iloc[:10].sum() / (10 + t2.REF_SHRINK)
    gid = int(mine["game_id"].iloc[10])
    other = refs[(refs["game_id"] == gid) & (refs["name"] != "Ann")]["name"].iloc[0]
    o = refs[refs["name"] == other].merge(home[["game_date", "y", "y_opp", "L_t"]], on="game_id")
    o = o[o["game_date"] < home.at[gid, "game_date"]]
    d_o = (o["y"] + o["y_opp"] - 2 * o["L_t"].fillna(CONST["penalties"]["league_mean_train"])).sum() \
        / (len(o) + t2.REF_SHRINK)
    assert home.at[gid, "R"] == pytest.approx((d_ann + d_o) / 2)


def test_fit_finds_a_planted_effect_and_refuses_other_seasons():
    frames, (shots, pens, att, refs, b2b) = _built(days=170)
    s = frames["shots"]
    # plant: back-to-back teams shoot 10 % less
    rng = np.random.default_rng(9)
    planted = shots.merge(b2b, on=["game_id", "team_id"])
    lam = np.where(planted["b2b"] == 1, 28 * 0.9, 28.0)
    planted["y"] = rng.poisson(lam)
    opp = planted[["game_id", "team_id", "y"]].rename(columns={"team_id": "opp_id", "y": "y_opp"})
    planted = planted.drop(columns=["y_opp", "b2b"]).merge(opp, on=["game_id", "opp_id"])
    again = t2.build_frames(planted, pens, att, b2b, refs, CONST)["shots"]
    block = t2.fit_block_a(again, CONST["shots"], "shots")
    assert block["coef"]["B_team"] == pytest.approx(np.log(0.9), abs=0.03)
    assert block["loglik"] > block["loglik_v1"] and 0 <= block["alpha"] <= 1
    mu = t2.predict_a(again, CONST["shots"], block)
    assert mu[again["B_team"] == 1].mean() < mu[again["B_team"] == 0].mean()
    bad = s.assign(season="2025-26")
    with pytest.raises(AssertionError):
        t2.fit_block_a(bad, CONST["shots"], "shots")
    with pytest.raises(AssertionError):
        t2.fit_rho(frames["penalties"].assign(season="2025-26"), CONST["penalties"],
                   {"coef": dict.fromkeys(t2.COLS_A, 0.0)})


def test_band_draws_are_nested_and_losses_stack_by_line():
    rng = np.random.default_rng(1)
    p = np.column_stack([np.full(5000, 0.45), np.full(5000, 0.2)])
    over = t2.draw_bands(p, rng)
    assert (over[:, 1] <= over[:, 0]).all()
    assert over.mean(axis=0) == pytest.approx([0.45, 0.2], abs=0.02)
    loss = t2.bern_loss(p, over)
    assert loss.shape == (10000,)
    assert loss[:5000].mean() == pytest.approx(-(over[:, 0] * np.log(0.45) + (1 - over[:, 0]) * np.log(0.55)).mean())

"""Player shots model v2 (docs/models_v2_notes.md 5): the manpower split,
features from strictly earlier games only, and the fit."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns  # noqa: E402
from nhl_tool import player_v2 as pv  # noqa: E402
from nhl_tool import team_model as tm  # noqa: E402
from nhl_tool import team_v2 as t2  # noqa: E402

CONST_PEN = json.loads((ROOT / "models" / "naive_team.json").read_text())["families"]["penalties"]
KEY = ["game_id", "player_id"]


def _league(seed=4, teams=6, days=90, seasons=("2023-24", "2024-25"), b2b_effect=1.0):
    """Every day four of six teams play; eight skaters a team. Returns the
    raw skater rows, the penalties frame and the back-to-back flags."""
    rng = np.random.default_rng(seed)
    sched, gid = [], 0
    for s, season in enumerate(seasons):
        for d in range(days):
            date = (pd.Timestamp(f"{2023 + s}-10-01") + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
            order = rng.permutation(teams)[:4] + 1
            for h, a in zip(order[::2], order[1::2]):
                gid += 1
                sched.append((gid, season, date, int(h), int(a)))
    long = pd.DataFrame([(g, d, t) for g, _, d, h, a in sched for t in (h, a)],
                        columns=["game_id", "game_date", "team_id"])
    b2b = t2.b2b_flags(long)
    flag = b2b.set_index(["game_id", "team_id"])["b2b"].to_dict()
    rows, pens = [], []
    for g, season, date, h, a in sched:
        yp = rng.poisson(3.3, 2)
        for i, (team, opp, home) in enumerate(((h, a, 1), (a, h, 0))):
            pens.append(dict(game_id=g, season=season, game_date=date, team_id=team, opp_id=opp,
                             is_home=home, y=int(yp[i]), y_opp=int(yp[1 - i])))
            mult = b2b_effect if flag[(g, team)] else 1.0
            for j in range(8):
                pid = team * 100 + j
                toi = int(rng.integers(800, 1200))
                pp = int(rng.integers(0, 200)) if j != 5 else 0
                s_np = int(rng.poisson((0.0020 + 0.0002 * j) * (toi - pp) * mult))
                s_pp = int(rng.poisson(0.0045 * pp * mult))
                rows.append(dict(game_id=g, game_date=date, season=season, player_id=pid, team_id=team,
                                 opp_id=opp, position="D" if j >= 6 else "C", toi_s=toi, ot_toi_s=0,
                                 pp_toi_s=pp, sog=s_np + s_pp, sog_reg=s_np + s_pp,
                                 att_reg=s_np + s_pp + int(rng.poisson(2)) + int(rng.poisson(0.004 * pp)),
                                 sog_pp_reg=s_pp, att_pp_reg=s_pp + int(rng.poisson(0.004 * pp))))
    df = pd.DataFrame(rows)
    df["att_reg"] = np.maximum(df["att_reg"], df["att_pp_reg"] + df["sog_reg"] - df["sog_pp_reg"])
    return pv.split_columns(df), pd.DataFrame(pens), b2b


def _feats(**kw):
    df, pens, b2b = _league(**kw)
    ctx = pv.context(tm.add_asof(pens), b2b, CONST_PEN)
    const = pv.fit_constants(df, pens)
    return pv.features(df, pens, ctx, const), (df, pens, b2b, ctx, const)


def test_split_columns():
    raw = pd.DataFrame([dict(game_id=1, game_date="2025-10-07", season="2025-26", player_id=5, team_id=1,
                             opp_id=2, position="L", toi_s=1000, ot_toi_s=40, pp_toi_s=120, sog=4, sog_reg=3,
                             att_reg=7, sog_pp_reg=1, att_pp_reg=2),
                        dict(game_id=1, game_date="2025-10-07", season="2025-26", player_id=6, team_id=1,
                             opp_id=2, position="D", toi_s=100, ot_toi_s=0, pp_toi_s=130, sog=0, sog_reg=0,
                             att_reg=0, sog_pp_reg=0, att_pp_reg=0)])
    d = pv.split_columns(raw).set_index("player_id")
    assert (d.at[5, "toi_reg"], d.at[5, "t_pp"], d.at[5, "t_np"]) == (960, 120, 840)
    assert (d.at[5, "s_np"], d.at[5, "s_pp"], d.at[5, "a_np"], d.at[5, "a_pp"]) == (2, 1, 5, 2)
    assert (d.at[6, "t_pp"], d.at[6, "t_np"]) == (100, 0) and d.at[6, "group"] == "D"   # capped at the ice time


def test_constants_and_team_games():
    df, pens, _ = _league()
    c = pv.fit_constants(df, pens)
    assert c["rate"]["S"]["pp"]["F"] > c["rate"]["S"]["np"]["F"] > 0
    assert c["rate"]["A"]["np"]["F"] > c["rate"]["S"]["np"]["F"]
    assert 0.03 < c["pp_share"] < 0.15
    tg = pv.team_games(df, pens)
    g = tg[tg["game_id"] == 7]
    a, b = g.iloc[0], g.iloc[1]
    assert a["np_against"] == b["s_np"] and a["pk_against"] == b["s_pp"]
    assert a["pen"] == pens[(pens["game_id"] == 7) & (pens["team_id"] == a["team_id"])]["y"].iloc[0]
    assert c["league_pk_per_penalty"] == pytest.approx(tg["pk_against"].sum() / tg["pen"].sum())


def test_features_come_from_strictly_earlier_games():
    feats, (df, pens, b2b, ctx, const) = _feats()
    cols = ["rS_np", "rA_np", "rS_pp", "rA_pp", "t_np_l10", "t_pp_l10", "o_np", "o_pk", "E",
            "B_team", "B_opp", "gp_before"]
    cut = "2024-11-20"
    d2, p2 = df.copy(), pens.copy()
    late = d2["game_date"] >= cut
    d2.loc[late, ["sog", "sog_reg", "s_np", "a_np", "att_reg"]] += 5
    d2.loc[late, ["s_pp", "a_pp", "sog_pp_reg", "att_pp_reg"]] += 2
    d2.loc[late, ["toi_s", "toi_reg", "t_np"]] += 300
    p2.loc[p2["game_date"] >= cut, ["y", "y_opp"]] += 3
    again = pv.features(d2, p2, pv.context(tm.add_asof(p2), b2b, CONST_PEN), const)
    a = feats[feats["game_date"] <= cut].set_index(KEY)[cols]
    b = again[again["game_date"] <= cut].set_index(KEY)[cols]
    pd.testing.assert_frame_equal(a, b.loc[a.index])
    later = feats[feats["game_date"] > "2024-12-10"].set_index(KEY)[cols]
    assert not np.allclose(later, again.set_index(KEY)[cols].loc[later.index])
    # first game of a player: no history -> the position prior, neutral opponent
    first = feats.sort_values(["player_id", "game_date"]).groupby("player_id").head(1)
    assert first["rS_np"].to_numpy() == pytest.approx(first["group"].map(const["rate"]["S"]["np"]).to_numpy())
    assert first["t_np_l10"].isna().all() and not feats["entry_phase0"].iloc[0]
    assert np.isfinite(feats.loc[feats["entry_phase0"], cols].to_numpy()).all()


def test_rates_shrink_as_in_the_notes():
    feats, (df, pens, b2b, ctx, const) = _feats()
    r = feats[(feats["season"] == "2024-25") & (feats["gp_before"] == 12) & (feats["group"] == "F")].iloc[0]
    hist = df[(df["player_id"] == r["player_id"])]
    cur = hist[(hist["season"] == "2024-25") & (hist["game_date"] < r["game_date"])]
    prev = hist[hist["season"] == "2023-24"]
    assert len(prev) >= ns.MIN_GP_PRIOR
    w = ns.W_SECONDS * const["pp_share"]
    pos = const["rate"]["S"]["pp"]["F"]
    prior = (prev["s_pp"].sum() + pos * w) / (prev["t_pp"].sum() + w)
    assert r["rS_pp"] == pytest.approx((cur["s_pp"].sum() + prior * w) / (cur["t_pp"].sum() + w))
    q = const["rate"]["S"]["np"]["F"] / const["rate"]["A"]["np"]["F"]
    w_np = ns.W_SECONDS * (1 - const["pp_share"])
    pos_a = const["rate"]["A"]["np"]["F"]
    prior_a = (prev["a_np"].sum() + pos_a * w_np) / (prev["t_np"].sum() + w_np)
    assert r["rA_np"] == pytest.approx(q * (cur["a_np"].sum() + prior_a * w_np) / (cur["t_np"].sum() + w_np))
    # the mean: both parts, the power-play part scaled by E^pi
    one = feats[feats["game_id"] == r["game_id"]]
    mu0, mu1 = pv.base_mu(one, 0.0, 0.0), pv.base_mu(one, 0.0, 1.0)
    i = list(one["player_id"]).index(r["player_id"])
    part_np = r["rS_np"] * r["t_np_l10"] * r["o_np"]
    part_pp = r["rS_pp"] * r["t_pp_l10"] * r["o_pk"]
    assert mu0[i] == pytest.approx(part_np + part_pp) and mu1[i] == pytest.approx(part_np + part_pp * r["E"])


def test_fit_finds_a_planted_rest_effect(monkeypatch):
    monkeypatch.setattr(pv, "ALPHA_GRID", [0.0, 0.5])
    monkeypatch.setattr(pv, "PI_GRID", [0.0, 1.0])
    feats, (_, _, _, _, const) = _feats(days=150, b2b_effect=0.8)
    model = pv.fit(feats)
    assert model["coef"]["B_team"] == pytest.approx(np.log(0.8), abs=0.05)
    assert abs(model["coef"]["B_opp"]) < 0.05 and model["alpha"] in (0.0, 0.5) and model["pi"] in (0.0, 1.0)
    assert 0.0 < model["coef"]["c0"] < 0.25                    # the base averages rested and tired games
    rows = feats[feats["entry_phase0"]]
    flat = {**model, "coef": dict.fromkeys(pv.COLS, 0.0)}
    y = rows["sog_reg"].to_numpy()
    assert tm.nb_logpmf(y, pv.predict(rows, model), model["nb_k"]).sum() > \
        tm.nb_logpmf(y, pv.predict(rows, flat), model["nb_k"]).sum() + 20
    full = pv.with_mu(feats[feats["entry_phase0"]], {**model, "ot_ratio": {"F": 0.02, "D": 0.03}})
    assert full["mu_60"].mean() == pytest.approx(full["sog_reg"].mean(), rel=0.06)
    assert (full["mu_full"] > full["mu_60"]).all()
    with pytest.raises(AssertionError):
        pv.fit(feats.assign(season="2025-26"))

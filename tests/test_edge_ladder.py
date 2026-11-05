"""Edge ladder (docs/edge_ladder_plan.md): bands, the slope test and its
simulations, and the forward-only candidate arm."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import edge_ladder as el  # noqa: E402


def _tips(n=4000, days=40, truth="model", seed=3):
    rng = np.random.default_rng(seed)
    p_mkt = rng.uniform(0.42, 0.62, n)
    p_mod = np.clip(p_mkt + rng.uniform(0.0, 0.16, n), 0.01, 0.95)
    price = 1 / (p_mkt * 1.0874)
    p_true = p_mod if truth == "model" else p_mkt
    win = rng.random(n) < p_true
    day = rng.integers(0, days, n)
    return pd.DataFrame({
        "tip_id": [f"t{i:05d}" for i in range(n)], "game_id": day * 10 + rng.integers(0, 6, n),
        "game_date": [f"2026-10-{1 + d % 28:02d}" if d < 28 else f"2026-11-{d - 27:02d}" for d in day],
        "p_model": p_mod, "p_consensus": p_mkt, "sim_tipsport_price": price,
        "outcome": np.where(win, "win", "loss"), "profit_units": np.where(win, price - 1, -1.0),
        "ev": p_mod * price - 1, "settled": True}).assign(band=lambda d: [el.band_of(e) for e in d["ev"]])


def test_bands_follow_the_plan():
    assert [el.band_of(e) for e in (-0.3, -1e-9, 0.0, 0.0499, 0.05, 0.0999, 0.10, 0.1999, 0.20, 3.0)] == \
        [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert [b[2] for b in el.BANDS] == ["< 0 %", "0–5 %", "5–10 %", "10–20 %", "≥ 20 %"]


def test_ladder_table_counts_settled_tips_only():
    df = _tips(n=600)
    df.loc[:9, "settled"] = False
    t = el.ladder(df)
    assert t["n"].sum() == 590 and list(t["band"]) == [1, 2, 3, 4, 5]
    r = t[t["n"] > 0].iloc[0]
    part = df[(df["band"] == r["band"]) & df["settled"]]
    assert r["roi"] == pytest.approx(part["profit_units"].mean())
    assert r["lo"] < r["roi"] < r["hi"] and r["hit"] == pytest.approx((part["outcome"] == "win").mean())
    pc = pd.Series(df["p_consensus"] + 0.02, index=df.index)
    t2 = el.ladder(df, pc)
    assert t2.loc[t2["n"] > 0, "move_pp"].round(6).eq(2.0).all()


def test_slope_test_sees_a_real_slope_and_not_a_flat_one():
    good = el.slope_test(_tips(truth="model"))
    assert good["b"] > 0.5 and good["pass"] and good["lo"] < good["b"] < good["hi"]
    flat = el.slope_test(_tips(truth="market", seed=8))
    assert abs(flat["b"]) < 0.5 and flat["lo"] < 0 < flat["hi"]


def test_simulations_give_false_alarm_and_power():
    df = _tips(n=2000, truth="market")
    assert el.slope_sims(df, "market", sims=200, n_boot=2000) <= 0.06
    assert el.slope_sims(df, "model", sims=100, n_boot=2000) >= 0.5


def test_arm_is_one_tip_per_game_from_the_start_date_on():
    df = pd.DataFrame({
        "tip_id": ["a", "b", "c", "d", "e", "f"], "game_id": [1, 1, 2, 2, 3, 4],
        "game_date": ["2026-11-05", "2026-11-05", "2026-11-06", "2026-11-06", "2026-11-07", "2026-11-07"],
        "ev": [0.30, 0.12, 0.15, 0.15, 0.09, 0.11], "p_model": [0.6, 0.6, 0.55, 0.60, 0.7, 0.6],
        "outcome": ["win", "loss", "void", "win", "win", None], "settled": [True, True, False, True, True, False],
        "profit_units": [0.8, -1, 0, 0.9, 0.7, None]})
    picks = el.arm(df)
    assert list(picks["tip_id"]) == ["d", "f"]          # game 1 before the start; game 2 tie -> higher p_model; game 3 under 10 %
    assert list(el.arm(df, start=None)["tip_id"]) == ["a", "d", "f"]
    # the choice ignores outcomes: a void best tip stays the game's pick
    df.loc[3, "p_model"] = 0.50
    assert list(el.arm(df)["tip_id"]) == ["c", "f"]
    st = el.arm_status(el.arm(df))
    assert st["n"] == 0 and st["pending"] == 2 and st["look"] == 300

"""Attribute contributions (docs/tips_plan.md section 11): exact, additive,
order-free - and tied to the frozen model's own prediction."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import explain  # noqa: E402
from nhl_tool import naive_sog as ns  # noqa: E402

K = 16.84
CASE = dict(rate_60=9.4, toi_min=19.2, opp_factor=1.06, base_rate_60=7.01,
            base_toi_min=15.5, line=2.5, side="over", k=K)


def test_parts_add_up_to_the_difference_from_the_average_player():
    c = explain.tip_contributions(**CASE)
    assert sum(c["mu_parts"].values()) == pytest.approx(c["mu"] - c["mu_base"], abs=1e-12)
    assert sum(c["p_parts"].values()) == pytest.approx(c["p"] - c["p_base"], abs=1e-12)
    assert c["mu"] == pytest.approx(9.4 / 60 * 19.2 * 1.06)
    assert c["p"] == pytest.approx(float(ns.p_over(c["mu"], 2.5, K)[0]))


def test_signs_follow_the_inputs():
    c = explain.tip_contributions(**CASE)
    assert all(v > 0 for v in c["p_parts"].values())          # everything above average
    low = explain.tip_contributions(**{**CASE, "opp_factor": 0.9, "toi_min": 13.0})
    assert low["p_parts"]["opp"] < 0 and low["p_parts"]["toi"] < 0 < low["p_parts"]["rate"]
    assert low["mu_parts"]["opp"] < 0


def test_under_mirrors_over():
    over = explain.tip_contributions(**CASE)
    under = explain.tip_contributions(**{**CASE, "side": "under"})
    assert under["p"] == pytest.approx(1 - over["p"])
    for key in explain.FACTORS:
        assert under["p_parts"][key] == pytest.approx(-over["p_parts"][key])
        assert under["mu_parts"][key] == pytest.approx(over["mu_parts"][key])


def test_an_average_player_has_no_contributions():
    c = explain.tip_contributions(**{**CASE, "rate_60": 7.01, "toi_min": 15.5, "opp_factor": 1.0})
    assert all(abs(v) < 1e-12 for v in c["p_parts"].values())
    assert c["p"] == pytest.approx(c["p_base"])


def test_shapley_does_not_depend_on_key_order_and_splits_a_product_fairly():
    f = lambda x: x["a"] * x["b"]                                   # noqa: E731
    one = explain.shapley(f, {"a": 1.0, "b": 1.0}, {"a": 2.0, "b": 2.0})
    two = explain.shapley(f, {"b": 1.0, "a": 1.0}, {"b": 2.0, "a": 2.0})
    assert one == pytest.approx({"a": 1.5, "b": 1.5}) and two["a"] == pytest.approx(one["a"])
    g = lambda x: x["a"] + 10 * x["b"]                              # noqa: E731
    assert explain.shapley(g, {"a": 0, "b": 0}, {"a": 3, "b": 1}) == pytest.approx({"a": 3, "b": 10})


def test_frozen_model_supplies_the_baseline_rate():
    from nhl_tool import tips
    model = tips.load_model()
    assert model["prior_rate_per_s"]["F"] * 3600 == pytest.approx(7.010, abs=5e-4)
    assert set(explain.LABELS) == set(explain.FACTORS)

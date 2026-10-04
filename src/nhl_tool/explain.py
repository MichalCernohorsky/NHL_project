"""Where a tip's number comes from: exact Shapley contributions of the naive
model's three inputs (docs/tips_plan.md section 11). Display only - nothing
here decides a tip.

The naive model is  mu_60 = rate_60 / 60 * toi_min * opp_factor  and
p = P(side of the line | mu_60). The reference point is "the average player
of the position": the frozen prior rate of the position, the position's
average ice time, opponent factor 1. Each input's contribution is its
average marginal effect over all 6 orders in which the inputs can be
switched from the reference to the player's real values, so the three
contributions add up exactly to (player's value - reference value) and no
order is privileged. NBA / MLB estimate the same thing with SHAP.
"""
from __future__ import annotations

from itertools import permutations

from . import naive_sog as ns

FACTORS = ("rate", "toi", "opp")
LABELS = {"rate": "Střelba hráče", "toi": "Čas na ledě", "opp": "Soupeř"}


def shapley(f, base: dict, actual: dict) -> dict:
    """Exact Shapley values of f over the keys of `base`.
    f takes a dict with the same keys; sum(result) == f(actual) - f(base)."""
    keys = list(base)
    out = dict.fromkeys(keys, 0.0)
    orders = list(permutations(keys))
    cache: dict[frozenset, float] = {}

    def value(on: frozenset) -> float:
        if on not in cache:
            cache[on] = float(f({k: actual[k] if k in on else base[k] for k in keys}))
        return cache[on]

    for order in orders:
        on: frozenset = frozenset()
        for key in order:
            nxt = on | {key}
            out[key] += value(nxt) - value(on)
            on = nxt
    return {k: v / len(orders) for k, v in out.items()}


def mu_of(x: dict) -> float:
    return x["rate"] / 60.0 * x["toi"] * x["opp"]


def p_side(mu: float, line: float, side: str, k: float) -> float:
    p = float(ns.p_over(mu, line, k)[0])
    return p if side == "over" else 1.0 - p


def tip_contributions(*, rate_60: float, toi_min: float, opp_factor: float,
                      base_rate_60: float, base_toi_min: float,
                      line: float, side: str, k: float) -> dict:
    """-> {"mu_base", "mu", "mu_parts": {factor: shots},
           "p_base", "p", "p_parts": {factor: probability}}"""
    base = {"rate": float(base_rate_60), "toi": float(base_toi_min), "opp": 1.0}
    actual = {"rate": float(rate_60), "toi": float(toi_min), "opp": float(opp_factor)}

    def p_of(x: dict) -> float:
        return p_side(mu_of(x), line, side, k)

    return {"mu_base": mu_of(base), "mu": mu_of(actual),
            "mu_parts": shapley(mu_of, base, actual),
            "p_base": p_of(base), "p": p_of(actual),
            "p_parts": shapley(p_of, base, actual)}

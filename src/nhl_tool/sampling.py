"""The pre-registered historical sample (docs/market_discovery_plan.md 4.2).

Whole game days, taken in golden-ratio order until the target number of
games is reached. Same ordering as NBA scripts/backfill_props.py: ANY prefix
of the order is an even sample of the season, so a purchase that stops early
(budget, dead key, interruption) leaves an evenly thinned season instead of
its first months - and season phase is known to move results (NBA: early
-7.3 %, mid -1.1 %, late -5.8 % ROI).

Deterministic: same season, same days, every run. No seed to choose.
"""
from __future__ import annotations

# Fractional part of the golden ratio: (i * GOLDEN) mod 1 is a
# low-discrepancy sequence.
GOLDEN = 0.6180339887498949


def spread_order(days):
    ordered = sorted(days)
    return [d for _, d in sorted(
        (((i + 1) * GOLDEN) % 1.0, d) for i, d in enumerate(ordered))]


def sample_days(games_per_day: dict[str, int], target_games: int) -> list[str]:
    """Days in spread order until their games reach target_games. Returned
    in that order (the purchase order), not chronologically."""
    picked, total = [], 0
    for day in spread_order(games_per_day):
        if total >= target_games:
            break
        picked.append(day)
        total += games_per_day[day]
    return picked

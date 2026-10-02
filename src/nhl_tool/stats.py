"""Bootstrap intervals the project reports everywhere (seed 17, 10 000
resamples, game days resampled - bets of one day are not independent)."""
from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 17
N_BOOT = 10_000


def roi_ci(df: pd.DataFrame, day_col: str = "game_date", profit_col: str = "profit_units",
           n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """(ROI, low, high) of flat 1-unit bets, 95 % CI by resampling days."""
    if df.empty:
        return float("nan"), float("nan"), float("nan")
    by_day = df.groupby(day_col)[profit_col].agg(["sum", "size"])
    s, n = by_day["sum"].to_numpy(), by_day["size"].to_numpy()
    roi = s.sum() / n.sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(s), size=(n_boot, len(s)))
    boots = s[idx].sum(axis=1) / n[idx].sum(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(roi), float(lo), float(hi)

"""Descriptive statistics with their uncertainty (docs/tips_plan.md section
11): a split such as home / away is shown with a 95% interval of the
difference, so a gap that is only noise is labelled as noise. Description
of history - the model does not use it and no tip is evaluated by it."""
from __future__ import annotations

import math

import pandas as pd

Z = 1.96


def mean_ci(values) -> tuple[float | None, float | None, int]:
    """(mean, half-width of the 95% interval or None for n < 2, n)."""
    v = pd.Series(values, dtype="float64").dropna()
    n = len(v)
    if n == 0:
        return None, None, 0
    half = Z * v.std(ddof=1) / math.sqrt(n) if n >= 2 else None
    return float(v.mean()), (float(half) if half is not None else None), n


def diff_ci(a, b) -> tuple[float | None, float | None]:
    """(mean(a) - mean(b), half-width of its 95% interval); None when either
    side has fewer than 2 values."""
    a = pd.Series(a, dtype="float64").dropna()
    b = pd.Series(b, dtype="float64").dropna()
    if len(a) < 2 or len(b) < 2:
        return None, None
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float(a.mean() - b.mean()), float(Z * se)


def cz(x, d: int = 2) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def split_table(df: pd.DataFrame, col: str, splits: list[tuple[str, str, str]]) -> pd.DataFrame:
    """One row per split: `splits` = [(title, name when flag is 1, name when
    0, ...)] is given as (flag column, name_1, name_0). The verdict compares
    the two halves by the 95% interval of their difference."""
    rows = []
    for flag, name1, name0 in splits:
        if flag not in df or col not in df:
            continue
        a = df.loc[df[flag] == 1, col]
        b = df.loc[df[flag] == 0, col]
        ma, _, na = mean_ci(a)
        mb, _, nb = mean_ci(b)
        d, half = diff_ci(a, b)
        if d is None:
            verdict = "málo zápasů"
        elif abs(d) > half:
            verdict = "rozdíl větší než náhoda"
        else:
            verdict = "v rámci náhody"
        rows.append({
            "srovnání": f"{name1} × {name0}",
            name_col(1): f"{cz(ma)} ({na} z.)", name_col(0): f"{cz(mb)} ({nb} z.)",
            "rozdíl": "–" if d is None else f"{'+' if d >= 0 else '−'}{cz(abs(d))}",
            "95% interval rozdílu": "–" if d is None else
                f"{'+' if d - half >= 0 else '−'}{cz(abs(d - half))} až "
                f"{'+' if d + half >= 0 else '−'}{cz(abs(d + half))}",
            "čtení": verdict})
    return pd.DataFrame(rows)


def name_col(i: int) -> str:
    return "první" if i == 1 else "druhá"


def over_table(series_by_period: list[tuple[str, pd.Series]], lines: list[float]) -> pd.DataFrame:
    """How often the value went over each line, per period."""
    rows = []
    for name, v in series_by_period:
        v = pd.Series(v, dtype="float64").dropna()
        rows.append({"období": name, "zápasů": len(v),
                     **{f"přes {cz(line, 1)}": f"{(v > line).mean() * 100:.0f} %" if len(v) else "–"
                        for line in lines}})
    return pd.DataFrame(rows)

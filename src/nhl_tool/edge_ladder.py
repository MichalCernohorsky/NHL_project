"""Edge ladder: does the ROI of the tips grow with their edge?

Specification: docs/edge_ladder_plan.md (approved and frozen 5. 11. 2026,
before any result was looked at by edge band). Nothing here is tuned.

    edge (EV) = p_model x price - 1     (price = simulated Tipsport price)

Five fixed bands, a per-band table (description), one test (the slope of a
tip's profit on its EV, 95 % interval by resampling game days) with two
simulations, and one candidate arm, followed forward only.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import phase0
from .stats import N_BOOT, SEED, roi_ci
from .team_model import boot_counts

BANDS = [(-math.inf, 0.00, "< 0 %"), (0.00, 0.05, "0–5 %"), (0.05, 0.10, "5–10 %"),
         (0.10, 0.20, "10–20 %"), (0.20, math.inf, "≥ 20 %")]
ARM_MIN_EV = 0.10
ARM_START = "2026-11-06"          # tips written after the plan was frozen
LOOK1_UPTO = "2026-11-04"
ARM_LOOK = 300
SIMS = 1000
SEASON = "2026-27"


def band_of(ev: float) -> int:
    """1..5 by the plan's section 4."""
    for i, (lo, hi, _) in enumerate(BANDS, 1):
        if lo <= ev < hi:
            return i
    raise ValueError(ev)


def load_tips(conn, upto: str | None = None) -> pd.DataFrame:
    """Every playable tip with its EV and band; `settled` marks win / loss."""
    df = pd.read_sql_query(
        """SELECT tip_id, game_id, game_date, player_id, line, side, pos_group, p_model,
                  p_consensus, sim_tipsport_price, outcome, profit_units
           FROM tips WHERE playable = 1 AND model = 'naive_sog_v1'""", conn)
    if upto:
        df = df[df["game_date"] <= upto]
    df = df.copy()
    df["ev"] = df["p_model"] * df["sim_tipsport_price"] - 1.0
    df["band"] = [band_of(e) for e in df["ev"]]
    df["settled"] = df["outcome"].isin(["win", "loss"])
    return df.reset_index(drop=True)


def closing_p(conn, tips: pd.DataFrame, model: dict) -> pd.Series:
    """p_close of the tip's side, 60 minutes, indexed like `tips` (NaN when
    the closing snapshot has no book quoting both sides of the same line)."""
    lines = phase0.load_closing(conn, SEASON)
    lines = lines[lines["player_id"].notna()].copy()
    if lines.empty:
        return pd.Series(np.nan, index=tips.index)
    lines["player_id"] = lines["player_id"].astype(int)
    cons = phase0.consensus(phase0.both_sides(lines))
    m = tips[["game_id", "player_id", "line", "side", "pos_group"]].reset_index().merge(
        cons[["game_id", "player_id", "line", "p_over_full"]], on=["game_id", "player_id", "line"], how="left")
    k = model["nb_k"]
    out = []
    for r in m.itertuples(index=False):
        if pd.isna(r.p_over_full):
            out.append(np.nan)
            continue
        p = phase0.p60(r.p_over_full, r.line, k, model["ot_ratio"][r.pos_group])
        out.append(p if r.side == "over" else 1.0 - p)
    return pd.Series(out, index=m["index"]).reindex(tips.index)


def ladder(df: pd.DataFrame, p_close: pd.Series | None = None) -> pd.DataFrame:
    """Section 5: one row per band over the settled tips of `df`."""
    rows = []
    for i, (_, _, name) in enumerate(BANDS, 1):
        part = df[(df["band"] == i) & df["settled"]]
        row = {"band": i, "name": name, "n": int(len(part))}
        if len(part):
            roi, lo, hi = roi_ci(part)
            row.update(hit=float((part["outcome"] == "win").mean()), p_model=float(part["p_model"].mean()),
                       p_market=float(part["p_consensus"].mean()), ev=float(part["ev"].mean()),
                       roi=roi, lo=lo, hi=hi)
            if p_close is not None:
                pc = p_close.reindex(part.index)
                ok = pc.notna()
                row["n_close"] = int(ok.sum())
                if ok.any():
                    row["move_pp"] = float((pc[ok] - part.loc[ok, "p_consensus"]).mean() * 100)
                    row["roi_close"] = float((pc[ok] * part.loc[ok, "sim_tipsport_price"] - 1).mean())
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------ the test

def _day_stats(x: np.ndarray, y: np.ndarray, day_idx: np.ndarray, d: int):
    return [np.bincount(day_idx, weights=w, minlength=d) for w in (np.ones_like(x), x, y, x * x, x * y)]


def _slopes(stats, counts: np.ndarray) -> np.ndarray:
    n, sx, sy, sxx, sxy = (counts @ s for s in stats)
    return (n * sxy - sx * sy) / (n * sxx - sx * sx)


def slope(x, y) -> float:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def slope_test(df: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Section 6 on the settled tips of df: slope b, its 95 % interval by
    resampling game days, and whether the whole interval is above zero."""
    s = df[df["settled"]]
    x, y = s["ev"].to_numpy(float), s["profit_units"].to_numpy(float)
    day_idx, counts = boot_counts(s["game_date"].to_numpy(), n_boot=n_boot, seed=seed)
    boots = _slopes(_day_stats(x, y, day_idx, counts.shape[1]), counts)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n": int(len(s)), "days": int(counts.shape[1]), "b": slope(x, y), "lo": float(lo), "hi": float(hi),
            "pass": bool(lo > 0), "ev": float(x.mean()), "roi": float(y.mean())}


def slope_sims(df: pd.DataFrame, truth: str, sims: int = SIMS, n_boot: int = N_BOOT,
               seed: int = SEED) -> float:
    """Share of simulated seasons in which the test passes when outcomes are
    drawn from the market ('market', true slope 0) or the model ('model',
    true slope 1); same tips, prices and bootstrap draws."""
    s = df[df["settled"]]
    x = s["ev"].to_numpy(float)
    price = s["sim_tipsport_price"].to_numpy(float)
    p = s["p_consensus" if truth == "market" else "p_model"].to_numpy(float)
    day_idx, counts = boot_counts(s["game_date"].to_numpy(), n_boot=n_boot, seed=seed)
    d = counts.shape[1]
    base = _day_stats(x, np.zeros_like(x), day_idx, d)
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(sims):
        y = np.where(rng.random(len(p)) < p, price - 1.0, -1.0)
        stats = [base[0], base[1], np.bincount(day_idx, weights=y, minlength=d), base[3],
                 np.bincount(day_idx, weights=x * y, minlength=d)]
        hits += np.percentile(_slopes(stats, counts), 2.5) > 0
    return hits / sims


# ------------------------------------------------------------ the arm

def arm(df: pd.DataFrame, start: str | None = ARM_START) -> pd.DataFrame:
    """Section 7: per game the playable tip with the highest EV (ties: higher
    p_model, then lower tip_id), kept when its EV >= 10 %. Chosen among all
    playable tips of the game, whatever their outcome turned out to be."""
    d = df if start is None else df[df["game_date"] >= start]
    if d.empty:
        return d
    best = (d.sort_values(["game_id", "ev", "p_model", "tip_id"], ascending=[True, False, False, True])
             .groupby("game_id", as_index=False).head(1))
    return best[best["ev"] >= ARM_MIN_EV].sort_values(["game_date", "game_id"]).reset_index(drop=True)


def arm_status(picks: pd.DataFrame) -> dict:
    s = picks[picks["settled"]] if not picks.empty else picks
    out = {"n": int(len(s)), "pending": int(len(picks) - len(s)), "look": ARM_LOOK}
    if len(s):
        roi, lo, hi = roi_ci(s)
        out.update(roi=roi, lo=lo, hi=hi, hit=float((s["outcome"] == "win").mean()), ev=float(s["ev"].mean()),
                   days=int(s["game_date"].nunique()))
    return out

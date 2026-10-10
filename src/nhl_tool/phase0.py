"""Phase 0 evaluation of one market on the purchased closing lines
(docs/market_discovery_plan.md sections 3 and 6, amendments D1-D3, D8).

K4a  Brier of the naive model against the market, on the main line, full
     game (the US market counts overtime).
K4b  ROI of the single filter: edge = p_model_60 - p_book_60 >= 3 p.b., one
     bet per (game, player); paid at the SIMULATED Tipsport price of D1,
     1 / (p_consensus_60 * (1 + m)), settled on 60 minutes (D3).
K5   bets per game day, scaled to the players Tipsport lists (D2).
6.5  null simulation: the market is the truth.

Nothing here is tuned; every number is fixed by the plan.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import naive_sog as ns
from .stats import N_BOOT, SEED, roi_ci
from .team_model import boot_counts, mean_ci

MARKET = "player_shots_on_goal"
EDGE_MIN = 0.03
K4A_MAX_GAP = 0.010
K3_MIN_GAMES = 300
K5_MIN_BETS = 3.0
NULL_SIMS = 2000


def load_closing(conn, season: str) -> pd.DataFrame:
    """Every closing quote of the market for the season's games (the
    purchased sample), from the last closing snapshot before puck drop."""
    return pd.read_sql_query(
        """SELECT o.game_id, o.player_id, o.player_name_raw, o.bookmaker, o.line,
                  o.side, o.price, o.snapshot_time, g.start_time_utc, g.game_date
           FROM odds o JOIN games g USING (game_id)
           WHERE g.season = ? AND g.season_type = 'regular'
             AND o.market = ? AND o.snapshot_kind = 'closing'
             AND o.snapshot_time < g.start_time_utc
             AND o.snapshot_time = (SELECT MAX(x.snapshot_time) FROM odds x
                                    WHERE x.game_id = o.game_id AND x.market = o.market
                                      AND x.snapshot_kind = 'closing'
                                      AND x.snapshot_time < g.start_time_utc)""",
        conn, params=(season, MARKET))


def both_sides(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, player, book, line) quoted on both sides, with the
    book's proportional de-vig P(over). Half-point lines only (no push)."""
    wide = (lines.pivot_table(index=["game_id", "game_date", "player_id", "bookmaker", "line"],
                              columns="side", values="price", aggfunc="max")
                 .dropna(subset=["over", "under"]).reset_index())
    wide = wide[(wide["line"] * 2) % 2 == 1].copy()
    io, iu = 1.0 / wide["over"], 1.0 / wide["under"]
    wide["p_over_full"] = io / (io + iu)
    return wide


def consensus(wide: pd.DataFrame) -> pd.DataFrame:
    """Per (game, player, line): median de-vig P(over) and number of books."""
    return (wide.groupby(["game_id", "game_date", "player_id", "line"], as_index=False)
                .agg(p_over_full=("p_over_full", "median"), books=("bookmaker", "nunique"),
                     best_over=("over", "max"), best_under=("under", "max")))


def main_lines(cons: pd.DataFrame) -> pd.DataFrame:
    """Plan 6.3: the line most books quote; on a tie the lower one."""
    order = cons.sort_values(["game_id", "player_id", "books", "line"],
                             ascending=[True, True, False, True])
    return order.groupby(["game_id", "player_id"], as_index=False).first()


@lru_cache(maxsize=None)
def _p60(p_full: float, line: float, k: float, ot_ratio: float) -> float:
    return ns.market_p_60(p_full, line, k, ot_ratio)


def p60(p_full: float, line: float, k: float, ot_ratio: float) -> float:
    """D3.3: a full-game P(over) of the market converted to 60 minutes."""
    return _p60(round(float(p_full), 6), float(line), float(k), float(ot_ratio))


# ------------------------------------------------------------------ K4a

def brier_rows(cons: pd.DataFrame, feats: pd.DataFrame, k: float) -> pd.DataFrame:
    """Main-line rows of players who played and pass the phase 0 entry:
    model and market P(over) for the FULL game and the full-game outcome."""
    rows = main_lines(cons).merge(
        feats[["game_id", "player_id", "mu_full", "sog", "toi_s", "entry_phase0"]],
        on=["game_id", "player_id"])
    rows = rows[(rows["toi_s"] > 0) & rows["entry_phase0"]].copy()
    rows["p_model"] = [float(ns.p_over(mu, line, k)[0]) for mu, line in zip(rows["mu_full"], rows["line"])]
    rows["p_market"] = rows["p_over_full"]
    rows["over"] = (rows["sog"] > rows["line"]).astype(float)
    return rows


def k4a(rows: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    bm = (rows["p_model"] - rows["over"]) ** 2
    bk = (rows["p_market"] - rows["over"]) ** 2
    day_idx, counts = boot_counts(rows["game_date"].to_numpy(), n_boot=n_boot)
    gap, lo, hi = mean_ci((bm - bk).to_numpy(), day_idx, counts)
    return {"n": int(len(rows)), "days": int(counts.shape[1]), "brier_model": float(bm.mean()),
            "brier_market": float(bk.mean()), "gap": gap, "lo": lo, "hi": hi,
            "pass": bool(gap <= K4A_MAX_GAP)}


def calibration(rows: pd.DataFrame, col: str, bands: int = 10) -> pd.DataFrame:
    order = np.argsort(rows[col].to_numpy(), kind="stable")
    out = []
    for part in np.array_split(order, bands):
        sub = rows.iloc[part]
        out.append({"n": len(sub), "predicted": float(sub[col].mean()),
                    "observed": float(sub["over"].mean())})
    return pd.DataFrame(out)


# ------------------------------------------------------------- K4b, K5

def select_bets(wide: pd.DataFrame, cons: pd.DataFrame, feats: pd.DataFrame,
                model: dict, margin: float) -> pd.DataFrame:
    """Plan 6.4 + D1 + D3: per (game, player) the candidate (line, side,
    book) with the largest 60-minute edge; a bet when edge >= 3 p.b. and the
    player has >= 10 games in the season. Paid at the simulated Tipsport
    price from the CONSENSUS of that line and side (D1 -> section 6.3),
    not from the selected book."""
    k = model["nb_k"]
    f = feats[["game_id", "player_id", "group", "mu_60", "sog", "sog_reg", "toi_s", "entry_phase0"]]
    c = wide.merge(f, on=["game_id", "player_id"])
    c = c[(c["toi_s"] > 0) & c["entry_phase0"]].copy()        # no ice time = void; entry rule
    if c.empty:
        return c
    ot = c["group"].map(model["ot_ratio"])
    c["p_model_over"] = [float(ns.p_over(mu, line, k)[0]) for mu, line in zip(c["mu_60"], c["line"])]
    c["p_book_over"] = [p60(p, line, k, r) for p, line, r in zip(c["p_over_full"], c["line"], ot)]
    edge_over = c["p_model_over"] - c["p_book_over"]
    c["side"] = np.where(edge_over >= 0, "over", "under")
    c["edge"] = edge_over.abs()
    best = (c.sort_values(["edge", "line", "bookmaker"], ascending=[False, True, True])
             .groupby(["game_id", "player_id"], as_index=False).first())
    bets = best[best["edge"] >= EDGE_MIN].copy()
    bets = bets.merge(cons[["game_id", "player_id", "line", "p_over_full", "books",
                            "best_over", "best_under"]].rename(columns={"p_over_full": "p_cons_full"}),
                      on=["game_id", "player_id", "line"])
    ot = bets["group"].map(model["ot_ratio"])
    p_cons_over = np.array([p60(p, line, k, r) for p, line, r in zip(bets["p_cons_full"], bets["line"], ot)])
    over = (bets["side"] == "over").to_numpy()
    bets["p_model"] = np.where(over, bets["p_model_over"], 1 - bets["p_model_over"])
    bets["p_market"] = np.where(over, p_cons_over, 1 - p_cons_over)          # consensus, 60 minutes
    bets["price_tipsport"] = 1.0 / (bets["p_market"] * (1 + margin))
    bets["price_us"] = np.where(over, bets["best_over"], bets["best_under"])
    won60 = (bets["sog_reg"] > bets["line"]) == over                          # D3: 60 minutes
    won_full = (bets["sog"] > bets["line"]) == over                           # the books' rule
    bets["won"] = won60.astype(int)
    bets["profit_units"] = np.where(won60, bets["price_tipsport"] - 1.0, -1.0)
    bets["profit_us"] = np.where(won_full, bets["price_us"] - 1.0, -1.0)
    return bets


def k4b(bets: pd.DataFrame, sample_days: int, n_boot: int = N_BOOT) -> dict:
    if bets.empty:
        return {"n": 0, "pass": False, "roi": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "per_day": 0.0}
    roi, lo, hi = roi_ci(bets, n_boot=n_boot)
    us, us_lo, us_hi = roi_ci(bets, profit_col="profit_us", n_boot=n_boot)
    avg = float(bets["price_tipsport"].mean())
    return {"n": int(len(bets)), "days": int(bets["game_date"].nunique()), "roi": roi, "lo": lo, "hi": hi,
            "hit": float(bets["won"].mean()), "avg_price": avg, "break_even": 1.0 / avg,
            "per_day": len(bets) / sample_days, "p_model": float(bets["p_model"].mean()),
            "p_market": float(bets["p_market"].mean()), "edge": float(bets["edge"].mean()),
            "over_share": float((bets["side"] == "over").mean()),
            "roi_us": us, "us_lo": us_lo, "us_hi": us_hi,
            "pass": bool(roi > 0 and hi > 0)}


def k5(bets_per_day: float, players_per_game: float, tipsport_players: float) -> dict:
    scaled = bets_per_day * tipsport_players / players_per_game
    return {"per_day_all": bets_per_day, "players_per_game": players_per_game,
            "per_day_tipsport": scaled, "pass": bool(scaled >= K5_MIN_BETS)}


def null_sim(bets: pd.DataFrame, sims: int = NULL_SIMS, seed: int = SEED) -> dict:
    """Plan 6.5: outcomes drawn from the market's own probability of each
    bet's side; selection and prices stay. Share of simulations with ROI > 0."""
    if bets.empty:
        return {"pass_rate": 0.0, "roi_mean": float("nan")}
    rng = np.random.default_rng(seed)
    p = bets["p_market"].to_numpy()
    gain = bets["price_tipsport"].to_numpy() - 1.0
    wins = rng.random((sims, len(p))) < p
    roi = np.where(wins, gain, -1.0).mean(axis=1)
    return {"pass_rate": float((roi > 0).mean()), "roi_mean": float(roi.mean()),
            "roi_p95": float(np.percentile(roi, 95))}

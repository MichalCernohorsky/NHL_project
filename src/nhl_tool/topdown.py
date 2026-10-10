"""The market as the model (docs/topdown_plan.md): bet where a book pays
more than the fair price implied by the consensus of the other books.

Stage 1 (plan section 3, amendment TD-1) checks the principle on the
purchased US closing lines, leave-one-book-out: for every book B and every
(game, player, line), p = median de-vig probability of the OTHER books
(at least 3); a bet at B when price * p - 1 >= 3 %, at most one per
(game, player, book); settled by the US books' rule (full game).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import naive_sog as ns
from .stats import N_BOOT, SEED, roi_ci

EV_MIN = 0.03
MIN_OTHERS = 3
SIMS = 2000


def loo_candidates(wide: pd.DataFrame, min_others: int = MIN_OTHERS) -> pd.DataFrame:
    """One row per (game, player, line, book) that has at least `min_others`
    other books on the line: the others' median P(over) and the expected
    value of each side at this book's prices."""
    rows = []
    for (gid, day, pid, line), grp in wide.groupby(["game_id", "game_date", "player_id", "line"],
                                                   sort=False):
        if len(grp) < min_others + 1:
            continue
        p = grp["p_over_full"].to_numpy()
        over, under = grp["over"].to_numpy(), grp["under"].to_numpy()
        books = grp["bookmaker"].to_numpy()
        p_all = float(np.median(p))
        for i in range(len(grp)):
            p_others = float(np.median(np.delete(p, i)))
            rows.append((gid, day, pid, line, books[i], over[i], under[i], p[i], p_others, p_all,
                         over[i] * p_others - 1.0, under[i] * (1.0 - p_others) - 1.0))
    return pd.DataFrame(rows, columns=["game_id", "game_date", "player_id", "line", "bookmaker",
                                       "over", "under", "p_book", "p_others", "p_all",
                                       "ev_over", "ev_under"])


def select_bets(cand: pd.DataFrame, results: pd.DataFrame, ev_min: float = EV_MIN) -> pd.DataFrame:
    """Per (game, player, book) the line and side with the largest expected
    value; a bet when it is >= ev_min and the player had ice time. Settled on
    the full game (the US books' rule)."""
    if cand.empty:
        return cand
    c = cand.copy()
    over = c["ev_over"] >= c["ev_under"]
    c["side"] = np.where(over, "over", "under")
    c["ev"] = np.where(over, c["ev_over"], c["ev_under"])
    c["price"] = np.where(over, c["over"], c["under"])
    c["p_fair"] = np.where(over, c["p_others"], 1 - c["p_others"])          # the rule's probability
    best = (c.sort_values(["ev", "line"], ascending=[False, True])
             .groupby(["game_id", "player_id", "bookmaker"], as_index=False).first())
    bets = best[best["ev"] >= ev_min].merge(
        results[["game_id", "player_id", "sog", "toi_s"]], on=["game_id", "player_id"])
    bets = bets[bets["toi_s"] > 0].copy()                                   # no ice time = void
    won = (bets["sog"] > bets["line"]) == (bets["side"] == "over")
    bets["won"] = won.astype(int)
    bets["profit_units"] = np.where(won, bets["price"] - 1.0, -1.0)
    return bets.reset_index(drop=True)


def summary(bets: pd.DataFrame, n_boot: int = N_BOOT) -> dict:
    if bets.empty:
        return {"n": 0, "pass": False}
    roi, lo, hi = roi_ci(bets, n_boot=n_boot)
    return {"n": int(len(bets)), "days": int(bets["game_date"].nunique()),
            "players": int(bets.groupby(["game_id", "player_id"]).ngroups),
            "roi": roi, "lo": lo, "hi": hi, "hit": float(bets["won"].mean()),
            "p_fair": float(bets["p_fair"].mean()), "ev_rule": float(bets["ev"].mean()),
            "avg_price": float(bets["price"].mean()),
            "over_share": float((bets["side"] == "over").mean()),
            "pass": bool(roi > 0), "supported": bool(lo > 0)}


def simulate(bets: pd.DataFrame, wide: pd.DataFrame, k: float, sims: int = SIMS,
             seed: int = SEED) -> dict:
    """Amendment TD-1. 'holds': the consensus of all books is the truth - one
    shot count per (game, player) from a negative binomial fitted to the
    main-line consensus. 'null': the book that is bet is right - each bet
    wins with the book's own de-vig probability, with one shared draw per
    (game, player) so that bets on the same player move together."""
    if bets.empty:
        return {}
    rng = np.random.default_rng(seed)
    cons = (wide.groupby(["game_id", "player_id", "line"], as_index=False)
                .agg(p=("p_over_full", "median"), books=("bookmaker", "nunique"))
                .sort_values(["game_id", "player_id", "books", "line"],
                             ascending=[True, True, False, True])
                .groupby(["game_id", "player_id"], as_index=False).first())
    cons["mu"] = [ns.mu_from_p_over(p, line, k) for p, line in zip(cons["p"], cons["line"])]
    key = bets[["game_id", "player_id"]].drop_duplicates().merge(cons, on=["game_id", "player_id"])
    idx = {(g, p): i for i, (g, p) in enumerate(zip(key["game_id"], key["player_id"]))}
    who = np.array([idx[(g, p)] for g, p in zip(bets["game_id"], bets["player_id"])])
    line = bets["line"].to_numpy()
    over = (bets["side"] == "over").to_numpy()
    gain = bets["price"].to_numpy() - 1.0
    mu = key["mu"].to_numpy()

    shots = rng.negative_binomial(k, k / (k + mu), size=(sims, len(mu)))
    win = (shots[:, who] > line) == over
    holds = np.where(win, gain, -1.0).mean(axis=1)

    u = rng.random((sims, len(mu)))[:, who]
    p_book_over = bets["p_book"].to_numpy()
    win0 = np.where(over, u > 1 - p_book_over, u <= 1 - p_book_over)
    null = np.where(win0, gain, -1.0).mean(axis=1)
    q = lambda a, x: float(np.percentile(a, x))  # noqa: E731
    return {"holds_mean": float(holds.mean()), "holds_p05": q(holds, 5), "holds_p95": q(holds, 95),
            "holds_positive": float((holds > 0).mean()),
            "null_mean": float(null.mean()), "null_p95": q(null, 95),
            "null_positive": float((null > 0).mean())}

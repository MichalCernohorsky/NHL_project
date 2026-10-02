"""Naive model of a skater's shots on goal in 60 minutes (regulation).

Specification: docs/market_discovery_plan.md section 6.2 + amendments D3
(60-minute target, OT ratio, market conversion) and D6 (live entry rule).
Interpretation of the points the plan leaves open is in docs/naive_model.md
and is fixed there before the model was fitted.

    mu_60 = r * TOI_L10 * o            (negative binomial, one dispersion k)

r       regulation shots per second of regulation ice time in the season
        before the game, shrunk to a prior with a weight of 3 hours of ice:
        r = (S + r_prior * W) / (T + W). Prior = the player's previous
        season if he played >= 20 games in it, else the position (F/D)
        rate of the training seasons.
TOI_L10 mean regulation time on ice (toi - ot_toi) in the last 10 games
        played, before the game (across seasons; D6).
o       shots the OPPONENT allowed in regulation per game over its last <= 20
        games of the same season before this one, divided by the training
        league average, shrunk to 1 with a weight of 10 games.

Every feature of a game uses only games strictly before it. Constants
(league average, position priors, OT ratios, k) come from the training
seasons only and are frozen in models/naive_sog.json.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

W_SECONDS = 3 * 3600          # prior weight: 3 hours of ice
OPP_WINDOW = 20
OPP_SHRINK_GAMES = 10
TOI_WINDOW = 10
MIN_GP_SEASON = 10            # phase 0 entry (plan 6.2)
MIN_GP_PREV_LIVE = 20         # live-tip alternative entry (D6)
MIN_GP_PRIOR = 20             # previous season counts as prior from 20 games
FORWARD = ("C", "L", "R")


def pos_group(position: str | None) -> str:
    return "D" if position == "D" else "F"


def prev_season(label: str) -> str:
    y = int(label[:4])
    return f"{y - 1}-{str(y)[2:]}"


# ------------------------------------------------------------------ data

def load_skater_games(conn, seasons: list[str]) -> pd.DataFrame:
    """One row per skater and regular-season game, ordered in time."""
    qs = ",".join("?" * len(seasons))
    df = pd.read_sql_query(
        f"""SELECT p.game_id, g.game_date, g.season, p.player_id, p.team_id,
                   CASE WHEN p.team_id = g.home_team_id THEN g.away_team_id
                        ELSE g.home_team_id END AS opp_id,
                   p.position, p.toi_s, COALESCE(p.ot_toi_s, 0) AS ot_toi_s,
                   p.sog, p.sog_reg
            FROM player_game_logs p JOIN games g USING (game_id)
            WHERE g.season_type = 'regular' AND g.season IN ({qs})
              AND p.toi_s > 0 AND p.sog_reg IS NOT NULL""",
        conn, params=list(seasons))
    df["toi_reg"] = (df["toi_s"] - df["ot_toi_s"]).clip(lower=0)
    df["group"] = df["position"].map(pos_group)
    return df.sort_values(["game_date", "game_id", "player_id"]).reset_index(drop=True)


def team_games(df: pd.DataFrame) -> pd.DataFrame:
    """Regulation shots for / against per team and game."""
    tf = (df.groupby(["game_id", "game_date", "season", "team_id", "opp_id"], as_index=False)
            ["sog_reg"].sum().rename(columns={"sog_reg": "shots_for"}))
    against = tf[["game_id", "team_id", "shots_for"]].rename(
        columns={"team_id": "opp_id", "shots_for": "shots_against"})
    return tf.merge(against, on=["game_id", "opp_id"], how="left")


# ------------------------------------------------------------- constants

def fit_constants(train: pd.DataFrame) -> dict:
    """Everything the plan says is estimated on the training seasons,
    except the dispersion k (fit_dispersion, which needs mu first)."""
    tg = team_games(train)
    rate = {g: float(part["sog_reg"].sum() / part["toi_reg"].sum())
            for g, part in train.groupby("group")}
    ot = {g: float((part["sog"] - part["sog_reg"]).sum() / part["sog_reg"].sum())
          for g, part in train.groupby("group")}
    return {"league_team_shots": float(tg["shots_for"].mean()),
            "prior_rate_per_s": rate, "ot_ratio": ot}


# -------------------------------------------------------------- features

def features(df: pd.DataFrame, const: dict) -> pd.DataFrame:
    """mu_60 and entry flags for every row of df, from strictly earlier
    games only. df may span several seasons; nothing of a game or of a
    later game enters its own features."""
    d = df.sort_values(["player_id", "game_date", "game_id"]).copy()

    # season-to-date, before this game
    by_ps = d.groupby(["player_id", "season"], sort=False)
    d["gp_before"] = by_ps.cumcount()
    d["S_before"] = by_ps["sog_reg"].cumsum() - d["sog_reg"]
    d["T_before"] = by_ps["toi_reg"].cumsum() - d["toi_reg"]

    # last 10 games played, across seasons (D6)
    d["toi_l10"] = (d.groupby("player_id", sort=False)["toi_reg"]
                     .transform(lambda s: s.shift(1).rolling(TOI_WINDOW, min_periods=1).mean()))

    # previous season totals -> prior
    tot = (d.groupby(["player_id", "season"], as_index=False)
             .agg(gp=("game_id", "size"), S=("sog_reg", "sum"), T=("toi_reg", "sum")))
    tot["season"] = tot["season"].map(lambda s: f"{int(s[:4]) + 1}-{str(int(s[:4]) + 2)[2:]}")
    tot = tot.rename(columns={"gp": "prev_gp", "S": "prev_S", "T": "prev_T"})
    d = d.merge(tot, on=["player_id", "season"], how="left")
    d["prev_gp"] = d["prev_gp"].fillna(0).astype(int)
    pos_rate = d["group"].map(const["prior_rate_per_s"])
    prev_rate = d["prev_S"] / d["prev_T"]
    d["r_prior"] = np.where((d["prev_gp"] >= MIN_GP_PRIOR) & (d["prev_T"] > 0), prev_rate, pos_rate)
    d["r"] = (d["S_before"] + d["r_prior"] * W_SECONDS) / (d["T_before"] + W_SECONDS)

    # opponent: shots it allowed in its last <= 20 games of this season
    tg = team_games(df).sort_values(["team_id", "game_date", "game_id"])
    by_ts = tg.groupby(["team_id", "season"], sort=False)["shots_against"]
    tg["opp_mean"] = by_ts.transform(
        lambda s: s.shift(1).rolling(OPP_WINDOW, min_periods=1).mean())
    tg["opp_n"] = by_ts.transform(
        lambda s: s.shift(1).rolling(OPP_WINDOW, min_periods=1).count()).fillna(0)
    opp = tg[["game_id", "team_id", "opp_mean", "opp_n"]].rename(columns={"team_id": "opp_id"})
    d = d.merge(opp, on=["game_id", "opp_id"], how="left")
    raw = (d["opp_mean"] / const["league_team_shots"]).fillna(1.0)
    n = d["opp_n"].fillna(0)
    d["o"] = (n * raw + OPP_SHRINK_GAMES) / (n + OPP_SHRINK_GAMES)

    d["mu_60"] = d["r"] * d["toi_l10"] * d["o"]
    d["mu_full"] = d["mu_60"] * (1 + d["group"].map(const["ot_ratio"]))
    d["entry_phase0"] = d["gp_before"] >= MIN_GP_SEASON
    d["entry_live"] = d["entry_phase0"] | (d["prev_gp"] >= MIN_GP_PREV_LIVE)
    return d.sort_values(["game_date", "game_id", "player_id"]).reset_index(drop=True)


# ---------------------------------------------------- negative binomial

def nb_pmf_upto(mu, k: float, ymax: int) -> np.ndarray:
    """pmf[0..ymax] for each mu (rows), mean mu, size k (var = mu + mu^2/k),
    by the stable recursion p(y+1) = p(y) * (y + k)/(y + 1) * mu/(k + mu)."""
    mu = np.atleast_1d(np.asarray(mu, dtype=float))
    out = np.empty((mu.size, ymax + 1))
    q = mu / (k + mu)
    out[:, 0] = np.exp(k * np.log(k / (k + mu)))
    for y in range(ymax):
        out[:, y + 1] = out[:, y] * (y + k) / (y + 1) * q
    return out


def p_over(mu, line: float, k: float) -> np.ndarray:
    """P(Y > line) for a half-integer (or integer) line."""
    floor = int(math.floor(line))
    return 1.0 - nb_pmf_upto(mu, k, floor).sum(axis=1)


def loglik(y: np.ndarray, mu: np.ndarray, k: float) -> float:
    y = np.asarray(y, dtype=int)
    lg = np.vectorize(math.lgamma)
    return float(np.sum(lg(y + k) - lg(k) - lg(y + 1)
                        + k * np.log(k / (k + mu)) + y * np.log(mu / (k + mu))))


def loglik_poisson(y: np.ndarray, mu: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    lg = np.vectorize(math.lgamma)
    return float(np.sum(y * np.log(mu) - mu - lg(y + 1)))


def fit_dispersion(y, mu, lo: float = 0.5, hi: float = 1000.0) -> float:
    """MLE of k by golden-section search on log k within [lo, hi]."""
    y, mu = np.asarray(y), np.asarray(mu)
    f = lambda lk: -loglik(y, mu, math.exp(lk))  # noqa: E731
    a, b = math.log(lo), math.log(hi)
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(60):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return math.exp((a + b) / 2)


def mu_from_p_over(p: float, line: float, k: float, lo: float = 1e-4, hi: float = 40.0) -> float:
    """The mean at which P(Y > line) = p (D3.3: a market price -> its mean)."""
    for _ in range(80):
        mid = (lo + hi) / 2
        if p_over(mid, line, k)[0] < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def market_p_60(p_over_full: float, line: float, k: float, ot_ratio: float) -> float:
    """D3.3: de-vig P(over) of a book that counts overtime -> the same
    market's P(over) for 60 minutes (conservative: no free edge)."""
    mu = mu_from_p_over(p_over_full, line, k)
    return float(p_over(mu / (1 + ot_ratio), line, k)[0])

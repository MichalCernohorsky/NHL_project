"""Naive team models: team shots and two-minute penalties in 60 minutes.

Specification: docs/team_markets_plan.md (sections 4-5, amendment T-1);
exact formulas and every fixed choice: docs/team_models.md, committed
before the first fit. Nothing here reads odds.

    mu = L_t * attack_T * defence_S * h^(+-1)

Everything a prediction uses comes from games with an EARLIER date.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import naive_sog as ns
from .stats import N_BOOT, SEED

TRAIN = ["2023-24", "2024-25"]
VALID = "2025-26"
WINDOW = 20                 # games of the current season behind a team's form
LEAGUE_ROWS = 400           # team rows behind the rolling league average
LEAGUE_MIN_ROWS = 100
W_GRID = [1, 2, 3, 5, 8, 12, 16, 20, 30, 40, 60, 80, 120]
C_GRID = [round(0.1 * i, 1) for i in range(11)]
FAMILIES = ("shots", "penalties")
# Lines for the calibration table (plan section 5): (team market, game market)
LINES = {"shots": ([x + 0.5 for x in range(22, 31)], [x + 0.5 for x in range(48, 60)]),
         "penalties": ([3.5, 4.5], [5.5, 6.5, 7.5, 8.5])}
MARKETS = {"shots": ("S-T", "S-Z"), "penalties": ("T-T", "T-Z")}


# ------------------------------------------------------------------ data

def _marks(seasons) -> str:
    return ",".join("?" * len(seasons))


def load_team_games(conn, seasons: list[str], family: str) -> pd.DataFrame:
    """Two rows per finished regular-season game: the team's 60-minute count
    (y) and the opponent's (y_opp). Games without complete counts are left out."""
    if family == "shots":
        sql = f"""
            WITH tg AS (SELECT p.game_id, p.team_id, SUM(p.sog_reg) AS y,
                               SUM(p.sog_reg IS NULL) AS missing
                        FROM player_game_logs p JOIN games g USING (game_id)
                        WHERE g.season IN ({_marks(seasons)}) AND g.season_type = 'regular'
                        GROUP BY p.game_id, p.team_id)
            SELECT g.game_id, g.season, g.game_date, me.team_id, op.team_id AS opp_id,
                   me.team_id = g.home_team_id AS is_home, me.y AS y, op.y AS y_opp
            FROM tg me JOIN tg op ON op.game_id = me.game_id AND op.team_id != me.team_id
            JOIN games g ON g.game_id = me.game_id
            WHERE me.missing = 0 AND op.missing = 0"""
    elif family == "penalties":
        # amendment T-1: regulation only; minor or bench; a double minor is two
        sql = f"""
            WITH side AS (
                SELECT game_id, season, game_date, home_team_id AS team_id,
                       away_team_id AS opp_id, 1 AS is_home FROM games
                 WHERE season IN ({_marks(seasons)}) AND season_type = 'regular'
                UNION ALL
                SELECT game_id, season, game_date, away_team_id, home_team_id, 0 FROM games
                 WHERE season IN ({_marks(seasons)}) AND season_type = 'regular'),
            cnt AS (SELECT game_id, team_id, SUM(duration / 2) AS y FROM penalties
                     WHERE period_type = 'REG' AND type_code IN ('MIN', 'BEN')
                     GROUP BY game_id, team_id)
            SELECT s.game_id, s.season, s.game_date, s.team_id, s.opp_id, s.is_home,
                   COALESCE(me.y, 0) AS y, COALESCE(op.y, 0) AS y_opp
            FROM side s
            JOIN backfill_state b ON b.task = 'penalties'
                 AND b.key = CAST(s.game_id AS TEXT) AND b.status = 'done'
            LEFT JOIN cnt me ON me.game_id = s.game_id AND me.team_id = s.team_id
            LEFT JOIN cnt op ON op.game_id = s.game_id AND op.team_id = s.opp_id"""
        seasons = [*seasons, *seasons]
    else:
        raise ValueError(family)
    df = pd.read_sql_query(sql, conn, params=list(seasons))
    df["is_home"] = df["is_home"].astype(int)
    return df.sort_values(["game_date", "game_id", "is_home"]).reset_index(drop=True)


# ------------------------------------------------------------- as-of view

def add_asof(df: pd.DataFrame) -> pd.DataFrame:
    """What was known before each game's date: the rolling league average,
    the team's form in the current season, last season's level, and the
    season-to-date means the baselines use."""
    df = df.sort_values(["game_date", "game_id", "is_home"]).reset_index(drop=True)
    # rolling league average over the last LEAGUE_ROWS rows with an earlier date
    y = df["y"].to_numpy(dtype=float)
    csum = np.concatenate([[0.0], np.cumsum(y)])
    first = df.groupby("game_date").head(1).index.to_numpy()      # first row of each date
    start_of = dict(zip(df.loc[first, "game_date"], first))
    i0 = df["game_date"].map(start_of).to_numpy()
    lo = np.maximum(0, i0 - LEAGUE_ROWS)
    n_hist = i0 - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        league = (csum[i0] - csum[lo]) / n_hist
    df["L_t"] = np.where(n_hist >= LEAGUE_MIN_ROWS, league, np.nan)

    g = df.groupby(["season", "team_id"], sort=False)
    df["n_season"] = g.cumcount()
    df["n"] = df["n_season"].clip(upper=WINDOW)
    prev_y = g["y"].shift(1)
    prev_opp = g["y_opp"].shift(1)
    grp = [df["season"], df["team_id"]]
    df["form_for"] = prev_y.groupby(grp).transform(
        lambda s: s.rolling(WINDOW, min_periods=1).mean())
    df["form_against"] = prev_opp.groupby(grp).transform(
        lambda s: s.rolling(WINDOW, min_periods=1).mean())
    df["season_for"] = prev_y.groupby(grp).transform(lambda s: s.expanding().mean())
    df["season_total"] = (prev_y + prev_opp).groupby(grp).transform(
        lambda s: s.expanding().mean())

    # last season: team mean / league mean, for and against; 1 when not in the data
    per_team = df.groupby(["season", "team_id"]).agg(f=("y", "mean"), a=("y_opp", "mean"))
    per_league = df.groupby("season")["y"].mean()
    prev_for, prev_against = [], []
    for season, team in zip(df["season"], df["team_id"]):
        key = (ns.prev_season(season), team)
        if key in per_team.index:
            base = per_league[key[0]]
            prev_for.append(per_team.at[key, "f"] / base)
            prev_against.append(per_team.at[key, "a"] / base)
        else:
            prev_for.append(1.0)
            prev_against.append(1.0)
    df["prev_for"], df["prev_against"] = prev_for, prev_against
    return df


def factors(df: pd.DataFrame, w: float, c: float, league_mean: float) -> pd.DataFrame:
    """attack / defence factors of the row's own team and L (league level)."""
    L = df["L_t"].fillna(league_mean).to_numpy()
    n = df["n"].to_numpy(dtype=float)
    out = pd.DataFrame({"game_id": df["game_id"], "team_id": df["team_id"], "L": L})
    for name, form, prev in (("attack", "form_for", "prev_for"),
                             ("defence", "form_against", "prev_against")):
        r = np.nan_to_num(df[form].to_numpy(dtype=float) / L, nan=0.0)   # n = 0 -> unused
        prior = 1.0 + c * (df[prev].to_numpy(dtype=float) - 1.0)
        out[name] = (n * r + w * prior) / (n + w)
    return out


def predict(df: pd.DataFrame, const: dict, defence_override=None) -> np.ndarray:
    """mu for every row of an as-of frame (both rows of every game present)."""
    f = factors(df, const["w"], const["c"], const["league_mean_train"])
    opp_def = f.set_index(["game_id", "team_id"])["defence"].reindex(
        pd.MultiIndex.from_arrays([df["game_id"], df["opp_id"]])).to_numpy()
    if defence_override is not None:
        opp_def = defence_override
    side = np.where(df["is_home"].to_numpy() == 1, const["h"], 1.0 / const["h"])
    return f["L"].to_numpy() * f["attack"].to_numpy() * opp_def * side


def opponent_defence(df: pd.DataFrame, const: dict) -> np.ndarray:
    f = factors(df, const["w"], const["c"], const["league_mean_train"])
    return f.set_index(["game_id", "team_id"])["defence"].reindex(
        pd.MultiIndex.from_arrays([df["game_id"], df["opp_id"]])).to_numpy()


def baselines(df: pd.DataFrame, league_mean: float) -> dict[str, np.ndarray]:
    """Team-level means of the two baselines (docs/team_models.md)."""
    L = df["L_t"].fillna(league_mean).to_numpy()
    z1 = np.where(df["n_season"].to_numpy() > 0, df["season_for"].to_numpy(dtype=float), L)
    return {"z0": L, "z1": z1}


def game_frame(df: pd.DataFrame, mu: np.ndarray, base: dict[str, np.ndarray],
               league_mean: float) -> pd.DataFrame:
    """One row per game: total count, the model's and the baselines' means."""
    L = df["L_t"].fillna(league_mean).to_numpy()
    tot1 = np.where(df["n_season"].to_numpy() > 0,
                    df["season_total"].to_numpy(dtype=float), 2 * L)
    t = pd.DataFrame({"game_id": df["game_id"], "game_date": df["game_date"],
                      "season": df["season"], "y": df["y"], "mu": mu,
                      "z0": base["z0"], "z1": tot1})
    return t.groupby("game_id", sort=False).agg(
        game_date=("game_date", "first"), season=("season", "first"), y=("y", "sum"),
        mu=("mu", "sum"), z0=("z0", "sum"), z1=("z1", "mean")).reset_index()


# ------------------------------------------------------------ likelihood

def nb_logpmf(y, mu, k: float) -> np.ndarray:
    """log P(Y = y) for a negative binomial with mean mu and size k."""
    y = np.asarray(y, dtype=int)
    mu = np.asarray(mu, dtype=float)
    ymax = int(y.max()) if y.size else 0
    rising = np.concatenate([[0.0], np.cumsum(np.log(k + np.arange(ymax)))])   # lgamma(y+k)-lgamma(k)
    lfact = np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, ymax + 1)))])
    return (rising[y] - lfact[y] + k * np.log(k / (k + mu)) + y * np.log(mu / (k + mu)))


def fit_k(y, mu, lo: float = 0.5, hi: float = 5000.0) -> float:
    """MLE of the size k by golden-section search on log k."""
    f = lambda lk: -nb_logpmf(y, mu, math.exp(lk)).sum()  # noqa: E731
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


def fit(train: pd.DataFrame) -> dict:
    """Constants of one family from an as-of frame of the TRAINING seasons."""
    assert set(train["season"]) <= set(TRAIN), "training frame holds other seasons"
    y = train["y"].to_numpy()
    home = train["is_home"].to_numpy() == 1
    const = {"league_mean_train": float(y.mean()),
             "h": float(math.sqrt(y[home].mean() / y[~home].mean()))}
    best = None
    for w in W_GRID:
        for c in C_GRID:
            mu = predict(train, {**const, "w": w, "c": c})
            k = fit_k(y, mu)
            ll = float(nb_logpmf(y, mu, k).sum())
            if best is None or ll > best[0]:
                best = (ll, w, c, k)
    ll, w, c, k = best
    const.update({"w": w, "c": c, "k_team": k, "loglik_team": ll, "rows": int(len(train))})
    mu = predict(train, const)
    base = baselines(train, const["league_mean_train"])
    games = game_frame(train, mu, base, const["league_mean_train"])
    const["k_game"] = fit_k(games["y"].to_numpy(), games["mu"].to_numpy())
    const["baselines"] = {
        name: {"k_team": fit_k(y, base[name]),
               "k_game": fit_k(games["y"].to_numpy(), games[name].to_numpy())}
        for name in ("z0", "z1")}
    return const


# ------------------------------------------------------------ evaluation

def boot_counts(days: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED):
    """(day index of every row, matrix of how often each day is drawn in each
    resample). Same draws as stats.roi_ci: integers(0, D, (n_boot, D))."""
    uniq, day_idx = np.unique(days, return_inverse=True)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n_boot, len(uniq)))
    counts = np.zeros((n_boot, len(uniq)), dtype=np.float64)
    np.add.at(counts, (np.arange(n_boot)[:, None], idx), 1.0)
    return day_idx, counts


def mean_ci(values: np.ndarray, day_idx: np.ndarray, counts: np.ndarray) -> tuple[float, float, float]:
    """(mean, low, high): 95 % interval of the row mean, game days resampled."""
    d = counts.shape[1]
    s = np.bincount(day_idx, weights=values, minlength=d)
    n = np.bincount(day_idx, minlength=d).astype(float)
    boots = (counts @ s) / (counts @ n)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(values.mean()), float(lo), float(hi)


def t1(y, mu, k, base_mu: dict, base_k: dict, day_idx, counts) -> dict:
    """Criterion T1: the model's log loss against both baselines."""
    loss = -nb_logpmf(y, mu, k)
    out = {"loss_model": float(loss.mean())}
    ok = True
    for name in ("z0", "z1"):
        lb = -nb_logpmf(y, base_mu[name], base_k[name])
        gain, lo, hi = mean_ci(lb - loss, day_idx, counts)
        out[name] = {"loss": float(lb.mean()), "gain": gain, "lo": lo, "hi": hi}
        ok = ok and lo > 0
    out["pass"] = bool(ok)
    return out


def calibration(y, mu, k: float, lines: list[float], bands: int = 5) -> pd.DataFrame:
    """P(over line) for every row and line, pooled, in equal-sized bands."""
    p = np.concatenate([ns.p_over(mu, line, k) for line in lines])
    hit = np.concatenate([(np.asarray(y) > line).astype(float) for line in lines])
    order = np.argsort(p, kind="stable")
    rows = []
    for part in np.array_split(order, bands):
        rows.append({"n": int(len(part)), "predicted": float(p[part].mean()),
                     "observed": float(hit[part].mean())})
    return pd.DataFrame(rows)

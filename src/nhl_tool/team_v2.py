"""Team models v2: new attributes on top of the frozen naive team models.

Specification: docs/models_v2_plan.md section 3; exact formulas and every
fixed choice: docs/models_v2_notes.md sections 1-4, committed before the
first fit. Nothing of version 1 is refitted and nothing here reads odds.

    mu_A = mu_base(alpha) * exp(c0 + gamma D + phi1 F1 + phi2 F2 + b1 B_team + b2 B_opp)
    mu_R = mu_A * exp(rho R)                                   (penalties only)

Everything a prediction uses comes from games with an EARLIER date.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import team_model as tm

ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]
PHASE = (10, 20)            # team games 1-10 and 11-20 of the season
REF_SHRINK = 30             # games a referee's deviation is shrunk with
COLS_A = ["c0", "D", "F1", "F2", "B_team", "B_opp"]   # c0 = 1: the level (notes, N-1)
KEY = ["game_id", "team_id"]


# ------------------------------------------------------------ likelihood

def nb_beta(y, offset, X, k: float, beta=None, iters: int = 60) -> np.ndarray:
    """ML of beta in ln mu = offset + X beta for a negative binomial with a
    fixed size k (a level, if wanted, is a column of ones in X). Fisher
    scoring with step halving."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    beta = np.zeros(X.shape[1]) if beta is None else np.array(beta, dtype=float)

    def loglik(b):
        mu = np.exp(offset + X @ b)
        return float((y * np.log(mu / (k + mu)) + k * np.log(k / (k + mu))).sum())

    ll = loglik(beta)
    for _ in range(iters):
        mu = np.exp(offset + X @ beta)
        grad = X.T @ ((y - mu) * k / (k + mu))
        info = X.T @ (X * (mu * k / (k + mu))[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(info, grad)
        t = 1.0
        while t > 1e-6 and loglik(beta + t * step) < ll:
            t /= 2
        beta = beta + t * step
        new = loglik(beta)
        if new - ll < 1e-10:
            break
        ll = new
    return beta


def nb_fit(y, offset, X, k0: float = 50.0, rounds: int = 8) -> tuple[np.ndarray, float]:
    """(beta, k) by alternating the two maximisations until k settles."""
    beta, k = None, k0
    for _ in range(rounds):
        beta = nb_beta(y, offset, X, k, beta)
        new = tm.fit_k(y, np.exp(offset + np.asarray(X, dtype=float) @ beta))
        done = abs(math.log(new / k)) < 1e-5
        k = new
        if done:
            break
    return beta, k


# ------------------------------------------------------------------ data

def load_team_attempts(conn, seasons: list[str]) -> pd.DataFrame:
    """Shot attempts (on goal + missed + blocked) per team and game, 60 minutes."""
    marks = ",".join("?" * len(seasons))
    return pd.read_sql_query(
        f"""SELECT s.game_id, s.team_id, SUM(s.att_reg) AS att
            FROM player_shot_splits s JOIN games g USING (game_id)
            WHERE g.season IN ({marks}) AND g.season_type = 'regular'
            GROUP BY s.game_id, s.team_id""", conn, params=list(seasons))


def load_b2b(conn) -> pd.DataFrame:
    """b2b = 1 when the team played a regular-season game the calendar day before."""
    g = pd.read_sql_query(
        """SELECT game_id, game_date, home_team_id, away_team_id FROM games
           WHERE season_type = 'regular' AND COALESCE(schedule_state, 'OK') = 'OK'""", conn)
    long = pd.concat([g[["game_id", "game_date"]].assign(team_id=g[side])
                      for side in ("home_team_id", "away_team_id")], ignore_index=True)
    return b2b_flags(long)


def b2b_flags(long: pd.DataFrame) -> pd.DataFrame:
    long = long.sort_values(["team_id", "game_date", "game_id"]).reset_index(drop=True)
    day = pd.to_datetime(long["game_date"])
    gap = (day - day.groupby(long["team_id"]).shift(1)).dt.days
    long["b2b"] = (gap == 1).astype(int)
    return long[["game_id", "team_id", "b2b"]]


def load_referees(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT game_id, name FROM game_officials WHERE role = 'referee'", conn)


def with_attempts(shots: pd.DataFrame, att: pd.DataFrame) -> pd.DataFrame:
    """Shots rows with the team's and the opponent's attempts. Rows of
    games still to be played (y unknown) are kept with unknown attempts."""
    out = shots.merge(att, on=KEY, how="left").merge(
        att.rename(columns={"team_id": "opp_id", "att": "att_opp"}), on=["game_id", "opp_id"], how="left")
    played = out["y"].notna()
    return out[~played | (out["att"].notna() & out["att_opp"].notna())].reset_index(drop=True)


# --------------------------------------------------------------- as-of

def asof_shots(shots: pd.DataFrame) -> pd.DataFrame:
    """tm.add_asof plus the same form and league average from attempts."""
    s = tm.add_asof(shots)
    a = tm.add_asof(shots.assign(y=shots["att"], y_opp=shots["att_opp"]))
    assert (s["game_id"].to_numpy() == a["game_id"].to_numpy()).all() \
        and (s["team_id"].to_numpy() == a["team_id"].to_numpy()).all()
    s["form_for_att"], s["form_against_att"] = a["form_for"], a["form_against"]
    s["L_att"] = a["L_t"]
    return s


def pp_expectation(pens: pd.DataFrame, const_pen: dict) -> pd.DataFrame:
    """Per team row of an as-of PENALTIES frame: E = how often the opponent
    takes minors x how often the team draws them (both against the league,
    frozen v1 factors), and D = L_t * (E - 1), the expected power plays above
    the league in counts (notes, section 1)."""
    f = tm.factors(pens, const_pen["w"], const_pen["c"], const_pen["league_mean_train"])
    opp_attack = f.set_index(KEY)["attack"].reindex(
        pd.MultiIndex.from_arrays([pens["game_id"], pens["opp_id"]])).to_numpy()
    e = opp_attack * f["defence"].to_numpy()
    return pd.DataFrame({"game_id": pens["game_id"].to_numpy(), "team_id": pens["team_id"].to_numpy(),
                         "E": e, "D": f["L"].to_numpy() * (e - 1.0)})


def referee_deviation(pens: pd.DataFrame, refs: pd.DataFrame, league_mean: float) -> pd.DataFrame:
    """Per game: R = mean over its referees of their shrunk deviation from
    the league in two-minute penalties per game, from EARLIER games only
    (notes, section 3). Games still to be played get R from the past too."""
    home = pens[pens["is_home"] == 1]
    games = pd.DataFrame({"game_id": home["game_id"].to_numpy(), "game_date": home["game_date"].to_numpy(),
                          "dev": (home["y"] + home["y_opp"]).to_numpy(dtype=float)
                          - 2.0 * home["L_t"].fillna(league_mean).to_numpy()})
    r = refs.merge(games, on="game_id")
    played = r["dev"].notna()
    # per referee and DATE, so that nothing of the same day counts as the past
    day = (r.assign(n=played.astype(int), s=r["dev"].fillna(0.0))
            .groupby(["name", "game_date"], as_index=False)[["n", "s"]].sum()
            .sort_values(["name", "game_date"]))
    by = day.groupby("name", sort=False)
    day["n_before"] = by["n"].cumsum() - day["n"]
    day["sum_before"] = by["s"].cumsum() - day["s"]
    r = r.merge(day[["name", "game_date", "n_before", "sum_before"]], on=["name", "game_date"])
    r["d"] = r["sum_before"] / (r["n_before"] + REF_SHRINK)
    out = r.groupby("game_id", as_index=False).agg(R=("d", "mean"), ref_n=("n_before", "mean"))
    return games[["game_id"]].merge(out, on="game_id", how="left").fillna({"R": 0.0, "ref_n": 0.0})


def add_extras(df: pd.DataFrame, pp: pd.DataFrame, b2b: pd.DataFrame,
               ref: pd.DataFrame | None = None) -> pd.DataFrame:
    """The block A columns (and R when referees are given) on an as-of frame."""
    out = df.merge(pp, on=KEY, how="left", validate="one_to_one")
    out = out.merge(b2b.rename(columns={"b2b": "B_team"}), on=KEY, how="left")
    out = out.merge(b2b.rename(columns={"team_id": "opp_id", "b2b": "B_opp"}),
                    on=["game_id", "opp_id"], how="left")
    for col in ("B_team", "B_opp"):
        out[col] = out[col].fillna(0).astype(int)
    out[["E", "D"]] = out[["E", "D"]].fillna({"E": 1.0, "D": 0.0})
    out["c0"] = 1.0
    number = out["n_season"] + 1
    out["F1"] = (number <= PHASE[0]).astype(int)
    out["F2"] = ((number > PHASE[0]) & (number <= PHASE[1])).astype(int)
    if ref is not None:
        out = out.merge(ref, on="game_id", how="left").fillna({"R": 0.0, "ref_n": 0.0})
    assert len(out) == len(df)
    return out


def build_frames(shots: pd.DataFrame, pens: pd.DataFrame, att: pd.DataFrame, b2b: pd.DataFrame,
                 refs: pd.DataFrame, const: dict) -> dict[str, pd.DataFrame]:
    """As-of frames of both families with the v2 columns. `const` is the
    'families' dict of models/naive_team.json."""
    p = tm.add_asof(pens)
    pp = pp_expectation(p, const["penalties"])
    ref = referee_deviation(p, refs, const["penalties"]["league_mean_train"])
    s = asof_shots(with_attempts(shots, att))
    return {"shots": add_extras(s, pp, b2b), "penalties": add_extras(p, pp, b2b, ref)}


def load_frames(conn, seasons: list[str], const: dict) -> dict[str, pd.DataFrame]:
    return build_frames(tm.load_team_games(conn, seasons, "shots"),
                        tm.load_team_games(conn, seasons, "penalties"),
                        load_team_attempts(conn, seasons), load_b2b(conn), load_referees(conn), const)


# --------------------------------------------------------------- model

def base_mu(df: pd.DataFrame, const: dict, alpha: float = 0.0,
            league_att: float | None = None) -> np.ndarray:
    """Version 1's formula; with alpha > 0 the form blends shots with
    attempts rescaled by the league's shots per attempt (shots only)."""
    if not alpha:
        return tm.predict(df, const)
    q = df["L_t"].fillna(const["league_mean_train"]) / df["L_att"].fillna(league_att)
    d = df.copy()
    for form in ("form_for", "form_against"):
        d[form] = (1 - alpha) * df[form] + alpha * df[f"{form}_att"] * q
    return tm.predict(d, const)


def predict_a(df: pd.DataFrame, const: dict, block: dict) -> np.ndarray:
    beta = np.array([block["coef"][c] for c in COLS_A])
    base = base_mu(df, const, block.get("alpha", 0.0), block.get("league_att_train"))
    return base * np.exp(df[COLS_A].to_numpy(dtype=float) @ beta)


def predict_r(df: pd.DataFrame, const: dict, block: dict, rho: float) -> np.ndarray:
    return predict_a(df, const, block) * np.exp(rho * df["R"].to_numpy(dtype=float))


def fit_block_a(train: pd.DataFrame, const: dict, family: str) -> dict:
    """Block A coefficients of one family from the TRAINING seasons."""
    assert set(train["season"]) <= set(tm.TRAIN), "training frame holds other seasons"
    y = train["y"].to_numpy(dtype=float)
    X = train[COLS_A].to_numpy(dtype=float)
    league_att = float(train["att"].mean()) if family == "shots" else None
    best = None
    for alpha in (ALPHA_GRID if family == "shots" else [0.0]):
        offset = np.log(base_mu(train, const, alpha, league_att))
        beta, k = nb_fit(y, offset, X)
        ll = float(tm.nb_logpmf(y, np.exp(offset + X @ beta), k).sum())
        if best is None or ll > best[0]:
            best = (ll, alpha, beta, k)
    ll, alpha, beta, k = best
    out = {"coef": {c: float(b) for c, b in zip(COLS_A, beta)}, "k": float(k),
           "loglik": ll, "loglik_v1": float(tm.nb_logpmf(y, tm.predict(train, const),
                                                         const["k_team"]).sum()),
           "rows": int(len(train))}
    if family == "shots":
        out.update(alpha=float(alpha), league_att_train=league_att)
    return out


def fit_rho(train: pd.DataFrame, const: dict, block: dict) -> dict:
    """Block R: rho on top of the fixed block A (penalties)."""
    assert set(train["season"]) <= set(tm.TRAIN), "training frame holds other seasons"
    y = train["y"].to_numpy(dtype=float)
    offset = np.log(predict_a(train, const, block))
    X = train[["R"]].to_numpy(dtype=float)
    beta, k = nb_fit(y, offset, X)
    return {"rho": float(beta[0]), "k": float(k), "shrink": REF_SHRINK,
            "loglik": float(tm.nb_logpmf(y, np.exp(offset + X @ beta), k).sum())}


# ------------------------------------------- block B (notes, amendment N-2)

COLS_B = ["S0", "S1", "S2"]     # has lines; (p_win - 0.5); (expected goals - training mean)


def team_script(conn, script: pd.DataFrame, goals_mean: float) -> pd.DataFrame:
    """Per (game, team): the block B columns from the game's main lines.
    `script` = main_lines.game_script(); a game without both numbers gets
    zeros, so block B equals block A for it."""
    g = pd.read_sql_query("SELECT game_id, home_team_id, away_team_id FROM games", conn)
    g = g.merge(script[["game_id", "p_home", "goals"]], on="game_id", how="inner")
    ok = g["p_home"].notna() & g["goals"].notna()
    rows = []
    for side, sign in (("home_team_id", 1.0), ("away_team_id", -1.0)):
        rows.append(pd.DataFrame({
            "game_id": g["game_id"], "team_id": g[side], "S0": ok.astype(float),
            "S1": np.where(ok, sign * (g["p_home"] - 0.5), 0.0),
            "S2": np.where(ok, g["goals"] - goals_mean, 0.0)}))
    return pd.concat(rows, ignore_index=True)


def add_script(df: pd.DataFrame, ts: pd.DataFrame) -> pd.DataFrame:
    out = df.drop(columns=[c for c in COLS_B if c in df]).merge(ts, on=KEY, how="left")
    out[COLS_B] = out[COLS_B].fillna(0.0)
    assert len(out) == len(df)
    return out


def fit_block_b(y, mu_a, X) -> dict:
    """delta on top of a FIXED block A, from the rows that have lines; the
    size k then from all rows (rows without lines keep mu_A)."""
    y, mu_a, X = np.asarray(y, dtype=float), np.asarray(mu_a, dtype=float), np.asarray(X, dtype=float)
    rows = X[:, 0] == 1
    beta, _ = nb_fit(y[rows], np.log(mu_a[rows]), X[rows])
    mu_b = mu_a * np.exp(X @ beta)
    k = tm.fit_k(y, mu_b)
    return {"coef": {c: float(b) for c, b in zip(COLS_B, beta)}, "k": float(k),
            "rows_with_lines": int(rows.sum()), "rows": int(len(y)),
            "loglik": float(tm.nb_logpmf(y, mu_b, k).sum())}


def predict_b(df: pd.DataFrame, mu_a, block: dict) -> np.ndarray:
    beta = np.array([block["coef"][c] for c in COLS_B])
    return np.asarray(mu_a, dtype=float) * np.exp(df[COLS_B].to_numpy(dtype=float) @ beta)


def cal_json(cal: dict) -> dict:
    return {str(line): {"a": a, "b": b} for line, (a, b) in cal.items()}


def as_cal(d: dict) -> dict:
    return {float(line): (v["a"], v["b"]) for line, v in d.items()}


# ---------------------------------------------------------- evaluation

def tt_probs(mu, cal: dict) -> np.ndarray:
    """P(over) per line (columns in the order of cal), rows = team rows."""
    return np.column_stack([np.clip(tm.logit_p(mu, ab), 1e-9, 1 - 1e-9) for ab in cal.values()])


def bern_loss(p: np.ndarray, over: np.ndarray) -> np.ndarray:
    """Log loss per (row, line), lines stacked one under another."""
    loss = -(over * np.log(p) + (1 - over) * np.log(1 - p))
    return loss.T.reshape(-1)


def draw_bands(p: np.ndarray, rng) -> np.ndarray:
    """One draw of the over outcomes of every line from one uniform per row,
    so that 'over 4.5' implies 'over 3.5' (notes, section 4)."""
    u = rng.random(p.shape[0])
    return (u[:, None] < p).astype(float)

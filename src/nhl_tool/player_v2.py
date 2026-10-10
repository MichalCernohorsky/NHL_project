"""Player shots model v2: shooting and ice time split by manpower, shot
attempts, expected power plays, the opponent's two defences and rest.

Specification: docs/models_v2_plan.md section 4; exact formulas and every
fixed choice: docs/models_v2_notes.md sections 5-6, committed before the
first fit. Nothing here reads odds.

    mu_60 = (r_np * t_np * o_np + r_pp * t_pp * E^pi * o_pk)
            * exp(c0 + b1 B_team + b2 B_opp)

'np' = outside the power play, 'pp' = on it. Every feature of a game uses
only games strictly before it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import naive_sog as ns
from . import team_model as tm
from . import team_v2 as t2

ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]
PI_GRID = [0.25 * i for i in range(9)]
SITS = ("np", "pp")
COLS = ["c0", "B_team", "B_opp"]          # c0 = 1: the level (notes, N-1)


# ------------------------------------------------------------------ data

def load_skater_games(conn, seasons: list[str]) -> pd.DataFrame:
    """One row per skater and regular-season game with the manpower split."""
    qs = ",".join("?" * len(seasons))
    df = pd.read_sql_query(
        f"""SELECT p.game_id, g.game_date, g.season, p.player_id, p.team_id,
                   CASE WHEN p.team_id = g.home_team_id THEN g.away_team_id
                        ELSE g.home_team_id END AS opp_id,
                   p.position, p.toi_s, COALESCE(p.ot_toi_s, 0) AS ot_toi_s,
                   COALESCE(p.pp_toi_s, 0) AS pp_toi_s, p.sog, p.sog_reg,
                   s.att_reg, s.sog_pp_reg, s.att_pp_reg
            FROM player_game_logs p JOIN games g USING (game_id)
            JOIN player_shot_splits s ON s.game_id = p.game_id AND s.player_id = p.player_id
            WHERE g.season_type = 'regular' AND g.season IN ({qs})
              AND p.toi_s > 0 AND p.sog_reg IS NOT NULL""",
        conn, params=list(seasons))
    return split_columns(df)


def split_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["toi_reg"] = (df["toi_s"] - df["ot_toi_s"]).clip(lower=0)
    df["t_pp"] = np.minimum(df["pp_toi_s"], df["toi_reg"])
    df["t_np"] = df["toi_reg"] - df["t_pp"]
    df["s_pp"], df["a_pp"] = df["sog_pp_reg"], df["att_pp_reg"]
    df["s_np"] = df["sog_reg"] - df["sog_pp_reg"]
    df["a_np"] = df["att_reg"] - df["att_pp_reg"]
    df["group"] = df["position"].map(ns.pos_group)
    return df.sort_values(["game_date", "game_id", "player_id"]).reset_index(drop=True)


def team_games(df: pd.DataFrame, pens: pd.DataFrame) -> pd.DataFrame:
    """Per team and game: shots it allowed outside its own penalty kills,
    shots it allowed shorthanded, and its own two-minute penalties (T-1)."""
    tf = df.groupby(["game_id", "game_date", "season", "team_id", "opp_id"], as_index=False)[
        ["s_np", "s_pp"]].sum()
    against = tf[["game_id", "team_id", "s_np", "s_pp"]].rename(
        columns={"team_id": "opp_id", "s_np": "np_against", "s_pp": "pk_against"})
    tg = tf.merge(against, on=["game_id", "opp_id"], how="left")
    own = pens[["game_id", "team_id", "y"]].rename(columns={"y": "pen"})
    return tg.merge(own, on=["game_id", "team_id"], how="left").fillna({"pen": 0})


def context(pens_asof: pd.DataFrame, b2b: pd.DataFrame, const_pen: dict) -> pd.DataFrame:
    """Per (game, team): E (expected power plays against the league) and rest."""
    pp = t2.pp_expectation(pens_asof, const_pen)
    out = pens_asof[["game_id", "team_id", "opp_id"]].merge(pp[["game_id", "team_id", "E"]],
                                                           on=["game_id", "team_id"])
    out = out.merge(b2b.rename(columns={"b2b": "B_team"}), on=["game_id", "team_id"], how="left")
    out = out.merge(b2b.rename(columns={"team_id": "opp_id", "b2b": "B_opp"}),
                    on=["game_id", "opp_id"], how="left")
    return out.drop(columns="opp_id").fillna({"B_team": 0, "B_opp": 0})


# ------------------------------------------------------------- constants

def fit_constants(train: pd.DataFrame, pens: pd.DataFrame) -> dict:
    """Position rates per second by situation (shots and attempts), the
    power play's share of ice time and the league's two defensive levels."""
    rate = {kind: {x: {g: float(part[f"{col}_{x}"].sum() / part[f"t_{x}"].sum())
                       for g, part in train.groupby("group")} for x in SITS}
            for kind, col in (("S", "s"), ("A", "a"))}
    tg = team_games(train, pens)
    return {"rate": rate,
            "pp_share": float(train["t_pp"].sum() / train["toi_reg"].sum()),
            "league_np_against": float(tg["np_against"].mean()),
            "league_pk_per_penalty": float(tg["pk_against"].sum() / tg["pen"].sum())}


# -------------------------------------------------------------- features

def features(df: pd.DataFrame, pens: pd.DataFrame, ctx: pd.DataFrame, const: dict) -> pd.DataFrame:
    """The components of mu_60 for every row of df, from strictly earlier
    games only (df may span several seasons)."""
    d = df.sort_values(["player_id", "game_date", "game_id"]).copy()
    by_ps = d.groupby(["player_id", "season"], sort=False)
    d["gp_before"] = by_ps.cumcount()
    counts = [f"{c}_{x}" for x in SITS for c in ("s", "a", "t")]
    for col in counts:
        d[f"{col}_before"] = by_ps[col].cumsum() - d[col]
    by_p = d.groupby("player_id", sort=False)
    for x in SITS:
        d[f"t_{x}_l10"] = by_p[f"t_{x}"].transform(
            lambda s: s.shift(1).rolling(ns.TOI_WINDOW, min_periods=1).mean())

    tot = d.groupby(["player_id", "season"], as_index=False).agg(
        prev_gp=("game_id", "size"), **{f"prev_{c}": (c, "sum") for c in counts})
    tot["season"] = tot["season"].map(lambda s: f"{int(s[:4]) + 1}-{str(int(s[:4]) + 2)[2:]}")
    d = d.merge(tot, on=["player_id", "season"], how="left")
    d["prev_gp"] = d["prev_gp"].fillna(0).astype(int)
    has_prev = (d["prev_gp"] >= ns.MIN_GP_PRIOR).to_numpy()
    for x in SITS:
        w = ns.W_SECONDS * (const["pp_share"] if x == "pp" else 1 - const["pp_share"])
        t_prev = d[f"prev_t_{x}"].fillna(0)
        for kind, c in (("S", "s"), ("A", "a")):
            pos = d["group"].map(const["rate"][kind][x])
            shrunk = (d[f"prev_{c}_{x}"].fillna(0) + pos * w) / (t_prev + w)
            prior = np.where(has_prev, shrunk, pos)
            d[f"r{kind}_{x}"] = (d[f"{c}_{x}_before"] + prior * w) / (d[f"t_{x}_before"] + w)
        # attempts -> shots by the position's shots per attempt in this situation
        d[f"rA_{x}"] *= d["group"].map(const["rate"]["S"][x]) / d["group"].map(const["rate"]["A"][x])

    # opponent: last <= 20 games of its season before this one
    tg = team_games(df, pens).sort_values(["team_id", "game_date", "game_id"])
    by_ts = tg.groupby(["team_id", "season"], sort=False)
    roll = lambda s: s.shift(1).rolling(ns.OPP_WINDOW, min_periods=1)  # noqa: E731
    tg["opp_n"] = by_ts["np_against"].transform(lambda s: roll(s).count()).fillna(0)
    tg["np_mean"] = by_ts["np_against"].transform(lambda s: roll(s).mean())
    tg["pk_sum"] = by_ts["pk_against"].transform(lambda s: roll(s).sum())
    tg["pen_sum"] = by_ts["pen"].transform(lambda s: roll(s).sum())
    opp = tg[["game_id", "team_id", "opp_n", "np_mean", "pk_sum", "pen_sum"]].rename(
        columns={"team_id": "opp_id"})
    d = d.merge(opp, on=["game_id", "opp_id"], how="left")
    n = d["opp_n"].fillna(0)
    raw_np = (d["np_mean"] / const["league_np_against"]).fillna(1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        raw_pk = np.where(d["pen_sum"].fillna(0) > 0,
                          d["pk_sum"] / d["pen_sum"] / const["league_pk_per_penalty"], 1.0)
    d["o_np"] = (n * raw_np + ns.OPP_SHRINK_GAMES) / (n + ns.OPP_SHRINK_GAMES)
    d["o_pk"] = (n * raw_pk + ns.OPP_SHRINK_GAMES) / (n + ns.OPP_SHRINK_GAMES)

    d = d.merge(ctx, on=["game_id", "team_id"], how="left").fillna({"E": 1.0, "B_team": 0, "B_opp": 0})
    d["c0"] = 1.0
    d["entry_phase0"] = d["gp_before"] >= ns.MIN_GP_SEASON
    return d.sort_values(["game_date", "game_id", "player_id"]).reset_index(drop=True)


# ----------------------------------------------------------------- model

def base_mu(d: pd.DataFrame, alpha: float, pi: float) -> np.ndarray:
    r_np = (1 - alpha) * d["rS_np"] + alpha * d["rA_np"]
    r_pp = (1 - alpha) * d["rS_pp"] + alpha * d["rA_pp"]
    return (r_np * d["t_np_l10"] * d["o_np"]
            + r_pp * d["t_pp_l10"] * d["E"] ** pi * d["o_pk"]).to_numpy(dtype=float)


def predict(d: pd.DataFrame, model: dict) -> np.ndarray:
    beta = np.array([model["coef"][c] for c in COLS])
    return base_mu(d, model["alpha"], model["pi"]) * np.exp(d[COLS].to_numpy(dtype=float) @ beta)


def with_mu(d: pd.DataFrame, model: dict) -> pd.DataFrame:
    """The columns phase0.py reads: mu_60 and the full-game mean."""
    out = d.copy()
    out["mu_60"] = predict(d, model)
    out["mu_full"] = out["mu_60"] * (1 + out["group"].map(model["ot_ratio"]))
    return out


def fit(train_feats: pd.DataFrame) -> dict:
    """alpha, pi from the grids, rest coefficients and k by maximum
    likelihood, on TRAINING rows that pass the phase 0 entry."""
    assert set(train_feats["season"]) <= set(tm.TRAIN), "training frame holds other seasons"
    rows = train_feats[train_feats["entry_phase0"]]
    y = rows["sog_reg"].to_numpy(dtype=float)
    X = rows[COLS].to_numpy(dtype=float)
    best, k0 = None, 16.0
    for alpha in ALPHA_GRID:
        for pi in PI_GRID:
            offset = np.log(base_mu(rows, alpha, pi))
            beta, k = t2.nb_fit(y, offset, X, k0=k0)
            ll = float(tm.nb_logpmf(y, np.exp(offset + X @ beta), k).sum())
            k0 = k
            if best is None or ll > best[0]:
                best = (ll, alpha, pi, beta, k)
    ll, alpha, pi, beta, k = best
    return {"alpha": float(alpha), "pi": float(pi), "coef": {c: float(b) for c, b in zip(COLS, beta)},
            "nb_k": float(k), "loglik": ll, "fit_rows": int(len(rows))}

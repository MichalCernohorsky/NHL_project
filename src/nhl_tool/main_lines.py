"""Main lines of a game (moneyline and total goals) from The Odds API:
the snapshot purchase of models v2, block B (docs/models_v2_plan.md 2).

One historical call returns every listed game at one moment:
    GET /historical/sports/{sport}/odds?date=...&markets=h2h,totals&regions=us
and costs 10 x markets x regions = 20 credits, whatever the number of
games. The anchor is 15:00 UTC of the game day; a game that had started by
the snapshot's own timestamp gets no rows.
"""
from __future__ import annotations

import math

import pandas as pd

from .odds_import import find_event, normalize_name

MARKETS = ("h2h", "totals")
ANCHOR_UTC = "15:00:00"
CREDITS_PER_CALL = 10 * len(MARKETS)          # one region
TASK = "main_lines:day"
MIN_BOOKS = 3                                 # notes N-2: fewer books = no game script


def anchor(game_date: str) -> str:
    return f"{game_date}T{ANCHOR_UTC}Z"


def estimate(days: int) -> int:
    return days * CREDITS_PER_CALL


def parse_event(event: dict) -> list[dict]:
    """One event of a featured-odds payload -> rows {bookmaker, market, side,
    line, price}. Moneyline sides are 'home' / 'away' by the event's teams."""
    home, away = normalize_name(event.get("home_team")), normalize_name(event.get("away_team"))
    rows = []
    for bm in event.get("bookmakers") or []:
        for market in bm.get("markets") or []:
            key = market.get("key")
            if key not in MARKETS:
                continue
            for o in market.get("outcomes") or []:
                if o.get("price") is None:
                    continue
                name = normalize_name(o.get("name"))
                if key == "h2h":
                    side = "home" if name == home else "away" if name == away else None
                    line = None
                else:
                    side = name if name in ("over", "under") else None
                    line = o.get("point")
                    if line is None:
                        continue
                if side is None:
                    continue
                rows.append({"bookmaker": bm["key"], "market": key, "side": side,
                             "line": None if line is None else float(line),
                             "price": float(o["price"])})
    return rows


def store_snapshot(conn, payload: dict, games: list, kind: str = "day") -> dict:
    """Store the rows of `games` (dicts with game_id, home, away,
    start_time_utc) found in one snapshot payload. Games that had started by
    the snapshot's timestamp are skipped. -> {matched, started, rows}."""
    events = payload.get("data") or []
    by_id = {e["id"]: e for e in events}
    stamp = payload.get("timestamp")
    out = {"matched": 0, "started": 0, "rows": 0}
    for g in games:
        if not stamp or g["start_time_utc"] <= stamp:
            out["started"] += 1
            continue
        eid = find_event(events, g["home"], g["away"], g["start_time_utc"])
        if eid is None:
            continue
        rows = parse_event(by_id[eid])
        out["matched"] += bool(rows)
        for r in rows:
            out["rows"] += conn.execute(
                """INSERT OR IGNORE INTO main_odds (game_id, event_id, bookmaker, market, side,
                       line, price, snapshot_time, snapshot_kind)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g["game_id"], eid, r["bookmaker"], r["market"], r["side"], r["line"],
                 r["price"], stamp, kind)).rowcount
    return out


def days_to_buy(conn, seasons: list[str]) -> dict[str, list]:
    """Game day -> its finished regular-season games (with team names)."""
    marks = ",".join("?" * len(seasons))
    out: dict[str, list] = {}
    for g in conn.execute(
            f"""SELECT g.game_id, g.game_date, g.start_time_utc,
                       ht.full_name AS home, at.full_name AS away
                FROM games g
                JOIN teams ht ON ht.team_id = g.home_team_id
                JOIN teams at ON at.team_id = g.away_team_id
                WHERE g.season IN ({marks}) AND g.season_type = 'regular'
                  AND g.game_state IN ('OFF', 'FINAL') AND g.start_time_utc IS NOT NULL
                ORDER BY g.game_date, g.start_time_utc""", list(seasons)):
        out.setdefault(g["game_date"], []).append(dict(g))
    return out


# ------------------------------------------- game script (notes, amendment N-2)

def poisson_over(lam: float, line: float) -> float:
    """P(X > line) for a Poisson total; on a whole line the push is left out
    (the de-vigged price of a two-way market with a push excludes it)."""
    k = int(math.floor(line))
    pmf = [math.exp(-lam)]
    for i in range(1, k + 1):
        pmf.append(pmf[-1] * lam / i)
    if line == k:                                  # whole line: over = X > k, push = X = k
        under = sum(pmf[:k])
        return (1.0 - under - pmf[k]) / (1.0 - pmf[k])
    return 1.0 - sum(pmf)


def goals_from_total(p_over: float, line: float) -> float:
    """The Poisson mean at which P(over line) equals the de-vigged p_over."""
    lo, hi = 0.5, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if poisson_over(mid, line) < p_over:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def game_script(conn, kind: str = "day") -> pd.DataFrame:
    """Per game: p_home (median de-vigged moneyline, overtime included) and
    goals (median of the books' implied expected total), each from at least
    MIN_BOOKS books quoting both sides; NaN otherwise."""
    df = pd.read_sql_query(
        "SELECT game_id, bookmaker, market, side, line, price FROM main_odds WHERE snapshot_kind = ?",
        conn, params=(kind,))
    out = pd.DataFrame({"game_id": sorted(df["game_id"].unique())})
    wide = df.pivot_table(index=["game_id", "bookmaker", "market"], columns="side", values="price",
                          aggfunc="first").reset_index()
    for col in ("home", "away", "over", "under"):
        if col not in wide:
            wide[col] = float("nan")
    h2h = wide[(wide["market"] == "h2h")].dropna(subset=["home", "away"]).copy()
    h2h["p"] = (1 / h2h["home"]) / (1 / h2h["home"] + 1 / h2h["away"])
    tot = wide[(wide["market"] == "totals")].dropna(subset=["over", "under"]).copy()
    lines = df[(df["market"] == "totals") & (df["side"] == "over")].set_index(
        ["game_id", "bookmaker"])["line"]
    tot["line"] = [lines.get((g, b)) for g, b in zip(tot["game_id"], tot["bookmaker"])]
    tot["p"] = (1 / tot["over"]) / (1 / tot["over"] + 1 / tot["under"])
    tot["goals"] = [goals_from_total(p, line) for p, line in zip(tot["p"], tot["line"])]
    for name, part, col in (("p_home", h2h, "p"), ("goals", tot, "goals")):
        agg = part.groupby("game_id")[col].agg(["median", "count"])
        agg.loc[agg["count"] < MIN_BOOKS, "median"] = float("nan")
        out[name] = out["game_id"].map(agg["median"])
        out[f"books_{name}"] = out["game_id"].map(agg["count"]).fillna(0).astype(int)
    return out

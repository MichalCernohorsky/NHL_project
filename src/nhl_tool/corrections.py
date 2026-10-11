"""NHL corrections after a game (docs/models_v2_notes.md, amendment N-3).

The NHL keeps correcting a game's statistics after the final horn (10. 10.
2026: 2 of the 4 games of the night before changed 10-19 hours after it,
one shot each), while every download step here reads a finished game once.
So each live game is read again once a day for WINDOW_DAYS days, and any
game a step left in error whatever its age, and compared with everything
stored from its box score and play-by-play.

On a difference, when the fresh feed passes the usual checks against
itself (pbp, penalties, attempts), the game's steps and its TOI day are
marked 'stale' and its cache files removed: the rest of the same daily run
downloads it again through the normal steps, with all their checks. No
tolerance anywhere. Every check goes to stat_checks and every changed value
to stat_corrections - the log that will measure how long the NHL corrects.

Settled tips and tickets keep the number known at settlement (user's
decision, 11. 10. 2026); the oldest logged sog_reg is that number.
"""
from __future__ import annotations

from pathlib import Path

from . import attempts, boxscore, pbp, penalties
from .db import set_state

WINDOW_DAYS = 10                  # amendment N-3: chosen without a measurement
GAME_TASKS = ("boxscore", "pbp", "penalties", "attempts")
ERROR_TASKS = ("pbp", "penalties", "attempts")
REG_SKATER = (("sog_reg", "sog_reg"), ("blocked_shots_reg", "blk_reg"))    # column, pbp count
REG_GOALIE = (("shots_against_reg", "sa_reg"), ("saves_reg", "sv_reg"))
SPLIT_COLS = ("team_id", "att_reg", "sog_pp_reg", "att_pp_reg", "sog_sh_reg", "att_sh_reg")
PEN_COLS = ("team_id", "period", "period_type", "time_in_period", "type_code", "desc_key",
            "duration", "committed_by", "served_by", "drawn_by")
GAME_COLS = ("home_score", "away_score", "last_period_type")


def candidates(conn, seasons: list[str], today: str, window: int = WINDOW_DAYS) -> list:
    """Regular games of these seasons with a box score, not checked yet on
    this UTC day and not downloaded on it: 1..window days old, or left in
    error by a step."""
    qs = ",".join("?" * len(seasons))
    errs = ",".join("?" * len(ERROR_TASKS))
    return conn.execute(
        f"""SELECT g.game_id, g.game_date,
                   CAST(julianday(?) - julianday(g.game_date) AS INTEGER) AS age_days
            FROM games g
            JOIN backfill_state b ON b.task = 'boxscore'
                 AND b.key = CAST(g.game_id AS TEXT) AND b.status = 'done'
            WHERE g.season IN ({qs}) AND g.season_type = 'regular'
              AND IFNULL(date(b.updated_at), '') < ?
              AND NOT EXISTS (SELECT 1 FROM stat_checks c WHERE c.game_id = g.game_id
                              AND c.action != 'error' AND substr(c.checked_at, 1, 10) = ?)
              AND (julianday(?) - julianday(g.game_date) BETWEEN 1 AND ?
                   OR EXISTS (SELECT 1 FROM backfill_state e
                              WHERE e.key = CAST(g.game_id AS TEXT)
                                AND e.task IN ({errs}) AND e.status = 'error'))
            ORDER BY g.game_date, g.game_id""",
        (today, *seasons, today, today, today, window, *ERROR_TASKS)).fetchall()


# ------------------------------------------------------------------ compare

def _diff(out: list, stored: dict, fresh: dict, cols, name, ids=None) -> None:
    """Append one difference per column, and per row present on one side
    only, of two keyed row sets. name(key, col) is the logged field (col
    None = the row itself); ids(key, row) gives player_id and team_id."""
    ids = ids or _player
    for key in sorted(set(stored) | set(fresh)):
        s, f = stored.get(key), fresh.get(key)
        if s is None or f is None:
            out.append({**ids(key, s or f), "field": name(key, None),
                        "old": int(s is not None), "new": int(f is not None)})
            continue
        for c in cols:
            if s[c] != f[c]:
                out.append({**ids(key, f), "field": name(key, c), "old": s[c], "new": f[c]})


def _player(key, row):
    return {"player_id": key, "team_id": row["team_id"]}


def _named(prefix: str, row: str = "row"):
    return lambda key, col: f"{prefix}{col or row}"


def _rows(conn, sql: str, game_id: int, key: str) -> dict:
    return {r[key]: dict(r) for r in conn.execute(sql, (game_id,))}


def _done(conn, task: str, game_id: int) -> bool:
    return conn.execute("SELECT 1 FROM backfill_state WHERE task = ? AND key = ? AND status = 'done'",
                        (task, str(game_id))).fetchone() is not None


def differences(conn, game_id: int, box: dict, counts: dict, pens: list[dict],
                events: list[dict]) -> list[dict]:
    """Every stored value of the game that the fresh feed has differently.
    60-minute counts are compared where stored (a step in error has none),
    attempts and penalties when their step is done."""
    out: list[dict] = []
    skaters = {s["player_id"]: s for s in box["skaters"]}
    cols = [c for c in box["skaters"][0] if c not in ("game_id", "player_id")] if skaters else []
    stored = _rows(conn, "SELECT * FROM player_game_logs WHERE game_id = ?", game_id, "player_id")
    _diff(out, stored, skaters, cols, _named(""))
    for pid in set(stored) & set(skaters):
        for c, k in REG_SKATER:
            if stored[pid][c] is not None and stored[pid][c] != counts[k][pid]:
                out.append({**_player(pid, stored[pid]), "field": c,
                            "old": stored[pid][c], "new": counts[k][pid]})

    goalies = {g["player_id"]: g for g in box["goalies"]}
    cols = [c for c in box["goalies"][0] if c not in ("game_id", "player_id")] if goalies else []
    stored = _rows(conn, "SELECT * FROM goalie_game_logs WHERE game_id = ?", game_id, "player_id")
    _diff(out, stored, goalies, cols, _named("goalie."))
    for pid in set(stored) & set(goalies):
        for c, k in REG_GOALIE:
            if stored[pid][c] is not None and stored[pid][c] != counts[k][pid]:
                out.append({**_player(pid, stored[pid]), "field": f"goalie.{c}",
                            "old": stored[pid][c], "new": counts[k][pid]})

    teams = {t["team_id"]: t for t in box["teams"]}
    stored = _rows(conn, "SELECT * FROM team_game_logs WHERE game_id = ?", game_id, "team_id")
    _diff(out, stored, teams, ("is_home", "goals", "sog"), _named("team."),
          lambda k, r: {"player_id": None, "team_id": k})

    g = conn.execute(f"SELECT {', '.join(GAME_COLS)} FROM games WHERE game_id = ?",
                     (game_id,)).fetchone()
    for c in GAME_COLS:
        new = box["game"][c]
        if new is not None and g[c] != new:
            out.append({"player_id": None, "team_id": None, "field": f"game.{c}", "old": g[c], "new": new})

    if _done(conn, "attempts", game_id):
        home = next(t["team_id"] for t in box["teams"] if t["is_home"])
        fresh = attempts.splits(events, {p: s["team_id"] for p, s in skaters.items()}, home)
        stored = _rows(conn, "SELECT * FROM player_shot_splits WHERE game_id = ?", game_id, "player_id")
        _diff(out, stored, fresh, SPLIT_COLS, _named("", "splits.row"))
    if _done(conn, "penalties", game_id):
        stored = _rows(conn, "SELECT * FROM penalties WHERE game_id = ?", game_id, "event_id")
        _diff(out, stored, {p["event_id"]: p for p in pens}, PEN_COLS,
              lambda key, col: f"penalty {key}.{col or 'row'}",
              lambda key, r: {"player_id": r["committed_by"], "team_id": r["team_id"]})
    return out


def feed_problems(box: dict, counts: dict, pens: list[dict], events: list[dict]) -> list[str]:
    """The usual checks of the steps, run on the fresh feed against itself:
    a feed that fails them is a correction still in progress."""
    sk = box["skaters"]
    return (pbp.compare(sk, counts) + penalties.incomplete(pens) + penalties.compare(sk, pens)
            + attempts.compare([{"player_id": s["player_id"], "sog_reg": counts["sog_reg"][s["player_id"]]}
                                for s in sk], events))


def check(conn, game_id: int, box_payload: dict, pbp_payload: dict) -> tuple[list[dict], list[str]]:
    """(differences from what is stored, problems of the fresh feed)."""
    box = boxscore.parse_boxscore(box_payload)
    counts = pbp.parse_pbp(pbp_payload)
    pens = penalties.parse_penalties(pbp_payload)
    events = attempts.parse_attempts(pbp_payload)
    return (differences(conn, game_id, box, counts, pens, events),
            feed_problems(box, counts, pens, events))


# ------------------------------------------------------------------ act

def invalidate(conn, game_id: int, game_date: str, cache_dir: Path | None, detail: str) -> None:
    """Mark the game for a fresh download by the normal steps of this run:
    its four per-game steps and its TOI day go 'stale' (not done, so they
    run again), and the cached box score, right rail and TOI day go."""
    for task in GAME_TASKS:
        set_state(conn, task, str(game_id), "stale", detail)
    set_state(conn, "toi", game_date, "stale", detail)
    if cache_dir is not None:
        for key in (f"boxscore/{game_id}", f"right_rail/{game_id}", f"toi/{game_date}"):
            (Path(cache_dir) / f"{key}.json").unlink(missing_ok=True)


def summary(diffs: list[dict], limit: int = 200) -> str:
    return "; ".join(f"{d['player_id'] or d['team_id'] or ''} {d['field']} {d['old']}->{d['new']}".strip()
                     for d in diffs)[:limit]


def record(conn, game_id: int, checked_at: str, age_days: int, action: str,
           diffs: list[dict], detail: str | None = None) -> None:
    """One stat_checks row; the changed values only when the game was refreshed."""
    conn.execute("""INSERT INTO stat_checks (game_id, checked_at, age_days, action, n_diff, detail)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                 (game_id, checked_at, age_days, action, len(diffs), detail))
    if action == "refreshed":
        conn.executemany(
            """INSERT INTO stat_corrections (game_id, checked_at, age_days, player_id, team_id,
                   field, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(game_id, checked_at, age_days, d["player_id"], d["team_id"], d["field"],
              d["old"], d["new"]) for d in diffs])

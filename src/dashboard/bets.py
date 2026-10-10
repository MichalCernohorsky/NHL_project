"""The user's decisions (✅ / ❌) and tickets - append-only records
(docs/tips_plan.md section 9).

Two JSONL files, each line one record with a unique id:
    decisions.jsonl  {"id", "ts", "tip_id", "game_id", "decision": bet|no|pending}
    bets.jsonl       {"id", "ts", "type": "bet", tip/game/player, line, side,
                      book, price, stake}  and  {"id", "ts", "type": "delete", "bet_id"}

Nothing is rewritten: a changed decision is a new record (latest wins), a
removed typo is a 'delete' record. A local copy lives outside the repository
(~/.nhl_project, NHL_BETS_DIR overrides); every write is pushed to the
PRIVATE data repository (GitHub Contents API) and on start the remote copy
is merged in (union by id). On Streamlit Cloud the disk is wiped on every
restart, so the GitHub copy is the source of truth there.

Lock (NBA decisions.py): from puck drop on, deciding, saving or deleting a
ticket is refused here in code, not only by a disabled button.
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

FILES = {"decisions": "decisions.jsonl", "bets": "bets.jsonl"}
REMOTE_DIR = "bets"
API = "https://api.github.com"


class Locked(Exception):
    """The game has started: the record would be written after the fact."""


def bets_dir() -> Path:
    d = Path(os.environ.get("NHL_BETS_DIR") or Path.home() / ".nhl_project")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(kind: str) -> Path:
    return bets_dir() / FILES[kind]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def started(start_utc: str | None, now: datetime | None = None) -> bool:
    if not start_utc:
        return False
    start = datetime.fromisoformat(str(start_utc).replace("Z", "+00:00"))
    return (now or now_utc()) >= start


# ------------------------------------------------------------- records

def read(kind: str) -> list[dict]:
    p = _path(kind)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _append(kind: str, rec: dict) -> dict:
    rec = {"id": uuid.uuid4().hex, "ts": now_utc().isoformat(timespec="seconds"), **rec}
    with open(_path(kind), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sync_push(kind)
    return rec


def decide(tip: dict, decision: str, now: datetime | None = None) -> dict:
    if decision not in ("bet", "no", "pending"):
        raise ValueError(decision)
    if started(tip.get("start_time_utc"), now):
        raise Locked("zápas už začal - rozhodnutí je zamčené")
    return _append("decisions", {"tip_id": tip["tip_id"], "game_id": int(tip["game_id"]),
                                 "decision": decision})


def current_decisions() -> dict[str, dict]:
    """tip_id -> latest decision record."""
    out: dict[str, dict] = {}
    for r in sorted(read("decisions"), key=lambda r: r["ts"]):
        out[r["tip_id"]] = r
    return out


def save_bet(tip: dict, line: float, price: float, stake: float, book: str,
             side: str | None = None, now: datetime | None = None) -> dict:
    if started(tip.get("start_time_utc"), now):
        raise Locked("zápas už začal - tiket se zpětně nezapisuje")
    if price <= 1.0 or stake <= 0:
        raise ValueError("kurz musí být > 1 a vklad > 0")
    return _append("bets", {
        "type": "bet", "tip_id": tip.get("tip_id"), "game_id": int(tip["game_id"]),
        "game_date": tip.get("game_date"), "start_time_utc": tip.get("start_time_utc"),
        "player_id": int(tip["player_id"]), "player_name": tip.get("player_name"),
        "side": side or tip["side"], "line": float(line), "price": float(price),
        "stake": float(stake), "book": book})


def delete_bet(bet: dict, now: datetime | None = None) -> dict:
    if started(bet.get("start_time_utc"), now):
        raise Locked("zápas už začal - tiket nejde smazat")
    return _append("bets", {"type": "delete", "bet_id": bet["id"]})


def active_bets() -> list[dict]:
    recs = read("bets")
    deleted = {r["bet_id"] for r in recs if r.get("type") == "delete"}
    return [r for r in recs if r.get("type") == "bet" and r["id"] not in deleted]


TEAM_MARKETS = ("S-T", "T-T")
# Team penalties before 1 November are paused (docs/team_markets_plan.md,
# amendment T-6): penalties run higher at the start of a season than the
# model's rolling league level, so its October "under" is overstated by
# 8.4 p.b. on the training seasons. From November it is within ~1 p.b.
PAUSE_TT_UNTIL_MONTH = 11
PAUSE_TT_REASON = ("Tresty týmu se do 31. 10. netipují: na začátku sezóny se píská víc, než model "
                   "čeká (dodatek T-6 plánu). Tikety na tresty od 1. 11.")


def paused(market: str, game_date: str | None) -> str | None:
    """Why no ticket may be written on this market for a game of this date."""
    if market != "T-T" or not game_date:
        return None
    month = int(str(game_date)[5:7])
    return PAUSE_TT_REASON if 8 <= month < PAUSE_TT_UNTIL_MONTH else None


def player_bets() -> list[dict]:
    """Tickets on player shots (the Tipy dne / Moje sázky flow)."""
    return [b for b in active_bets() if b.get("market") not in TEAM_MARKETS]


def team_bets() -> list[dict]:
    """Tickets on the team markets (docs/team_markets_plan.md, stage 2)."""
    return [b for b in active_bets() if b.get("market") in TEAM_MARKETS]


def save_team_bet(pred: dict, line: float, price: float, stake: float, book: str,
                  side: str, paper: bool, now: datetime | None = None) -> dict:
    """A ticket on a team market; paper = no money (plan section 6)."""
    if pred.get("market") not in TEAM_MARKETS or side not in ("over", "under"):
        raise ValueError("neznamy trh nebo strana")
    why = paused(pred["market"], pred.get("game_date"))
    if why:
        raise ValueError(why)
    if started(pred.get("start_time_utc"), now):
        raise Locked("zápas už začal - tiket se zpětně nezapisuje")
    if price <= 1.0 or stake <= 0:
        raise ValueError("kurz musí být > 1 a vklad > 0")
    return _append("bets", {
        "type": "bet", "market": pred["market"], "game_id": int(pred["game_id"]),
        "game_date": pred.get("game_date"), "start_time_utc": pred.get("start_time_utc"),
        "team_id": int(pred["team_id"]), "team": pred.get("tym"), "opp": pred.get("souper"),
        "mu": float(pred["mu"]) if pred.get("mu") is not None else None,
        "side": side, "line": float(line), "price": float(price), "stake": float(stake),
        "book": book, "paper": bool(paper)})


def settle(bet: dict, actual_60: int | None, played: bool) -> tuple[str, float]:
    """(outcome, profit in the stake's currency). Not played = void (stake
    back); a whole-number line can push."""
    if not played or actual_60 is None:
        return "void", 0.0
    if actual_60 == bet["line"]:
        return "push", 0.0
    won = (actual_60 > bet["line"]) == (bet["side"] == "over")
    return ("win", bet["stake"] * (bet["price"] - 1)) if won else ("loss", -bet["stake"])


# ------------------------------------------------------------- GitHub backup

def _setting(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:  # noqa: BLE001 - no secrets file outside Streamlit Cloud
        return None
    return None


def _remote():
    token, repo = _setting("NHL_DATA_TOKEN"), _setting("NHL_DB_RELEASE_REPO")
    if not token or not repo or repo.lower().endswith("/nhl_project"):
        return None
    return token, repo


def _marker() -> Path:
    return bets_dir() / ".unsynced"


def unsynced() -> bool:
    return _marker().exists()


def _get_remote(kind: str, token: str, repo: str):
    import requests
    r = requests.get(f"{API}/repos/{repo}/contents/{REMOTE_DIR}/{FILES[kind]}",
                     headers={"Authorization": f"Bearer {token}",
                              "Accept": "application/vnd.github+json"}, timeout=30)
    if r.status_code == 404:
        return None, ""
    r.raise_for_status()
    body = r.json()
    return body["sha"], base64.b64decode(body["content"]).decode()


def sync_push(kind: str) -> bool:
    """Push the local file (merged with the remote one first) to the data
    repo. Failure leaves a marker the pages show until a push succeeds."""
    remote = _remote()
    if remote is None:
        return False
    token, repo = remote
    try:
        import requests
        sha, text = _get_remote(kind, token, repo)
        merged = _merge_text(text, _path(kind).read_text() if _path(kind).exists() else "")
        _path(kind).write_text(merged)
        payload = {"message": f"Update {FILES[kind]}",
                   "content": base64.b64encode(merged.encode()).decode()}
        if sha:
            payload["sha"] = sha
        r = requests.put(f"{API}/repos/{repo}/contents/{REMOTE_DIR}/{FILES[kind]}",
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"},
                         json=payload, timeout=30)
        r.raise_for_status()
        _marker().unlink(missing_ok=True)
        return True
    except Exception:  # noqa: BLE001 - offline is not an error, the marker says so
        _marker().write_text("1")
        return False


def sync_pull() -> int:
    """Merge the remote copies into the local files; -> records added."""
    remote = _remote()
    if remote is None:
        return 0
    token, repo = remote
    added = 0
    for kind in FILES:
        try:
            _, text = _get_remote(kind, token, repo)
        except Exception:  # noqa: BLE001
            _marker().write_text("1")
            continue
        local = _path(kind).read_text() if _path(kind).exists() else ""
        merged = _merge_text(text, local)
        added += merged.count("\n") - local.count("\n")
        _path(kind).write_text(merged)
    return added


def _merge_text(a: str, b: str) -> str:
    """Union of two JSONL texts by record id, ordered by timestamp."""
    recs: dict[str, dict] = {}
    for text in (a, b):
        for line in text.splitlines():
            if line.strip():
                r = json.loads(line)
                recs[r["id"]] = r
    ordered = sorted(recs.values(), key=lambda r: (r["ts"], r["id"]))
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ordered)

#!/usr/bin/env python3
"""Buy the live season's morning and closing snapshots the day after, from
The Odds API historical archive (plan amendment D4).

Why not live: the snapshots must be taken at fixed moments (10:00 ET and
puck drop minus 10 min). GitHub Actions runs a 10-minute schedule only
every 3-6 hours (measured 29. 9.-2. 10.), and the Mac misses them while it
sleeps. The archive keeps every line at 5-minute resolution, so buying the
day after gives the same pre-registered moments exactly, at 10x the live
price, with nothing to keep awake.

Covers finished games of the last `--days` ET days (default 7, so a missed
run catches up), each snapshot kind once: a game that already has rows of a
kind (e.g. collected live by the Mac before 3. 10.) is not bought again.
Only games with a box score (names are matched against appearances). A
market no book quotes (blocked shots so far) costs nothing.

Off until the user's "jed": config odds.hist_daily_enabled. --dry-run shows
what a run would buy and cost, needs no key and spends nothing.

Usage:
    python scripts/buy_snapshots.py --dry-run
    python scripts/buy_snapshots.py                 # the cloud daily job
"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.hist_odds import CREDITS_PER_MARKET_REGION, KINDS, HistoricalBuyer
from nhl_tool.parsing import ET


def task(kind: str) -> str:
    return f"hist_live:{kind}"


def window(until: str, days: int) -> tuple[str, str]:
    end = date.fromisoformat(until)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def todo(conn, season: str, start: str, end: str) -> list[tuple]:
    """(game row, kind) pairs still to buy, oldest first."""
    games = conn.execute(
        """SELECT g.game_id, g.game_date, g.start_time_utc,
                  ht.full_name AS home, at.full_name AS away
           FROM games g
           JOIN teams ht ON ht.team_id = g.home_team_id
           JOIN teams at ON at.team_id = g.away_team_id
           WHERE g.season = ? AND g.season_type = 'regular'
             AND g.game_date BETWEEN ? AND ?
             AND g.game_state IN ('OFF', 'FINAL') AND g.start_time_utc IS NOT NULL
             AND EXISTS (SELECT 1 FROM team_game_logs t WHERE t.game_id = g.game_id)
           ORDER BY g.game_date, g.start_time_utc""", (season, start, end)).fetchall()
    out = []
    for kind in KINDS:
        done = state_keys(conn, task(kind), statuses=("done", "missing"))
        have = {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE snapshot_kind = ?", (kind,))}
        out += [(g, kind) for g in games if str(g["game_id"]) not in done
                and g["game_id"] not in have]
    return sorted(out, key=lambda x: (x[0]["game_date"], x[0]["start_time_utc"], x[1]))


def markets_per_snapshot(conn, season: str) -> dict:
    """Observed average number of markets the books actually quote per game,
    per kind - what a purchase really costs (unquoted markets are free)."""
    rows = conn.execute(
        """SELECT o.snapshot_kind, o.game_id, COUNT(DISTINCT o.market)
           FROM odds o JOIN games g USING (game_id)
           WHERE g.season = ? AND o.snapshot_kind IN ('morning', 'closing')
           GROUP BY o.snapshot_kind, o.game_id""", (season,)).fetchall()
    acc = defaultdict(list)
    for kind, _, n in rows:
        acc[kind].append(n)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--until", help="last ET game date (default: yesterday ET)")
    ap.add_argument("--days", type=int, help="look-back window (default: config)")
    ap.add_argument("--budget", type=float, help="max credits this run (default: config)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    oc = cfg["odds"]
    season = cfg["live"]["season"]
    until = args.until or (datetime.now(ET).date() - timedelta(days=1)).isoformat()
    start, end = window(until, args.days or oc["hist_daily_days"])
    budget = args.budget or oc["hist_daily_budget"]
    conn = connect(resolve_db_path(cfg))
    items = todo(conn, season, start, end)

    per_kind = Counter(k for _, k in items)
    days = sorted({g["game_date"] for g, _ in items})
    avg = markets_per_snapshot(conn, season)
    expected = sum(per_kind[k] * avg.get(k, len(oc["markets"])) * CREDITS_PER_MARKET_REGION
                   for k in KINDS) + len(days)
    ceiling = len(items) * len(oc["markets"]) * CREDITS_PER_MARKET_REGION + 2 * len(days)
    print(f"okno {start} .. {end} | trhy {', '.join(oc['markets'])}")
    for d in days:
        c = Counter(k for g, k in items if g["game_date"] == d)
        print(f"  {d}: ranni {c['morning']}, closing {c['closing']}")
    print(f"k nakupu: ranni {per_kind['morning']}, closing {per_kind['closing']}"
          f" | odhad {expected:.0f} kreditu (strop {ceiling})"
          f" | vypsanych trhu na snimek dosud: "
          + ", ".join(f"{k} {v:.2f}" for k, v in sorted(avg.items())))

    if args.dry_run:
        print("--dry-run: nic se nekoupilo, zadny kredit se neutratil.")
        return
    if not oc.get("hist_daily_enabled"):
        print("VYPNUTO: odds.hist_daily_enabled = false (ceka na 'jed'). Nic se nekupuje.")
        return
    if not items:
        print("nic k nakupu.")
        return

    from nhl_tool.odds_client import OddsApiError, OddsClient, cache_response
    client = OddsClient()
    client.get("/sports")                    # free: learn the balance
    start_used = client.last_used or 0
    print(f"zustatek uctu: {client.last_remaining:.0f} kreditu")
    buyer = HistoricalBuyer(conn, client, oc, oc["markets"], cache_fn=cache_response)
    rows, unmatched, n = defaultdict(int), set(), 0
    for g, kind in items:
        spent = (client.last_used or 0) - start_used
        if spent >= budget or (client.last_remaining or 1e9) <= oc["reserve_backfill"]:
            print(f"STOP ROZPOCTU: utraceno {spent:.0f}, zustatek {client.last_remaining:.0f}."
                  " Zbytek koupi pristi beh (okno se posouva).")
            break
        try:
            res = buyer.price(g, kind)
            set_state(conn, task(kind), str(g["game_id"]), res["status"], res["detail"])
            for m, k in res["rows"].items():
                rows[f"{kind}:{m}"] += k
            unmatched |= res["unmatched"]
            n += 1
        except OddsApiError as exc:
            set_state(conn, task(kind), str(g["game_id"]), "error", str(exc)[:200])
            print(f"  CHYBA {g['game_id']} {kind}: {exc}")
        conn.commit()
    print(f"koupeno snimku: {n} | radku: "
          + (", ".join(f"{k}={v}" for k, v in sorted(rows.items())) or "nic")
          + f" | nesparovanych jmen {len(unmatched)}")
    print(f"utraceno {(client.last_used or 0) - start_used:.0f},"
          f" zustatek {(client.last_remaining or 0):.0f} kreditu")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Historical player-prop odds for the phase 0 sample (plan section 4).

Buys ONE snapshot per game of the pre-registered sample: 'closing' = puck
drop minus 10 min (stage A), or 'morning' = 10:00 ET on the game day
(stage B, finalists only). Region us. Resumable (backfill_state), budget-
and reserve-guarded, raw JSON cached, days worked in golden-ratio order so
a run that stops early leaves an even sample (src/nhl_tool/sampling.py).

CREDITS (The Odds API v4 docs): historical event odds = 10 x markets
RETURNED x regions; historical events list = 1 per call. One events call per
sampled game day is reused for every game of that day.

NOTHING is bought without --dry-run first and the user's "jed"
(docs/market_discovery_plan.md). --dry-run needs no API key.

Usage:
    python scripts/backfill_props.py --dry-run
    python scripts/backfill_props.py --dry-run --write-sample docs/market_discovery_sample.md
    python scripts/backfill_props.py --markets player_shots_on_goal,player_total_saves
    python scripts/backfill_props.py --snapshot morning --markets player_shots_on_goal
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys
from nhl_tool.hist_odds import CREDITS_PER_MARKET_REGION, HistoricalBuyer
from nhl_tool.hist_odds import snapshot_for as _snapshot_for
from nhl_tool.sampling import sample_days


def task_name(markets, snapshot: str) -> str:
    return f"props_backfill:{snapshot}:" + ",".join(sorted(markets))


def snapshot_for(snapshot: str, start_utc: str, game_date: str, cfg_odds: dict) -> str:
    return _snapshot_for(snapshot, start_utc, game_date, cfg_odds)


def estimate_credits(n_games: int, n_markets: int, n_days: int) -> int:
    return n_games * n_markets * CREDITS_PER_MARKET_REGION + n_days


def load_sample(conn, season: str, target: int):
    games = conn.execute(
        """SELECT g.game_id, g.game_date, g.start_time_utc,
                  ht.full_name AS home, at.full_name AS away
           FROM games g
           JOIN teams ht ON ht.team_id = g.home_team_id
           JOIN teams at ON at.team_id = g.away_team_id
           WHERE g.season = ? AND g.season_type = 'regular'
             AND g.start_time_utc IS NOT NULL
           ORDER BY g.game_date, g.start_time_utc""", (season,)).fetchall()
    per_day = Counter(g["game_date"] for g in games)
    days = sample_days(per_day, target)
    rank = {d: i for i, d in enumerate(days)}
    sample = sorted((g for g in games if g["game_date"] in rank),
                    key=lambda g: (rank[g["game_date"]], g["start_time_utc"]))
    return games, days, sample


def quarter_spread(all_days, days) -> list[int]:
    ordered = sorted(all_days)
    q = [0, 0, 0, 0]
    pos = {d: i for i, d in enumerate(ordered)}
    for d in days:
        q[min(3, pos[d] * 4 // len(ordered))] += 1
    return q


def write_sample(path: Path, season: str, target: int, days, sample, all_days):
    by_day = Counter(g["game_date"] for g in sample)
    lines = [f"# Vzorek fáze 0 — {season}", "",
             "Vygenerováno `scripts/backfill_props.py --dry-run --write-sample` "
             "PŘED nákupem kurzů. Pravidlo: celé herní dny v pořadí zlatého řezu, "
             f"dokud součet zápasů nedosáhne {target} "
             "(`docs/market_discovery_plan.md`, sekce 4.2).", "",
             f"- herních dnů: {len(days)} z {len(all_days)}",
             f"- zápasů: {len(sample)}",
             f"- dny po čtvrtinách sezóny: {quarter_spread(all_days, days)}", "",
             "| pořadí nákupu | den | zápasů |", "|---|---|---|"]
    lines += [f"| {i} | {d} | {by_day[d]} |" for i, d in enumerate(days, 1)]
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--markets", help="comma-separated; default: config odds.markets")
    ap.add_argument("--snapshot", choices=("closing", "morning"), default="closing")
    ap.add_argument("--budget", type=float, default=10000,
                    help="max credits this run may spend")
    ap.add_argument("--dry-run", action="store_true",
                    help="print sample and cost, spend nothing (no key needed)")
    ap.add_argument("--write-sample", metavar="PATH",
                    help="with --dry-run: write the sample day list as markdown")
    args = ap.parse_args()

    cfg = load_config()
    oc = cfg["odds"]
    markets = [m.strip() for m in (args.markets or ",".join(oc["markets"])).split(",")
               if m.strip()]
    season, target = oc["backfill_season"], oc["backfill_target_games"]
    conn = connect(resolve_db_path(cfg))
    all_games, days, sample = load_sample(conn, season, target)
    if not all_games:
        print(f"V DB neni rozpis {season} - nejdriv python scripts/backfill_schedule.py")
        return
    task = task_name(markets, args.snapshot)
    done = state_keys(conn, task, statuses=("done", "missing"))
    todo = [g for g in sample if str(g["game_id"]) not in done]
    all_days = sorted({g["game_date"] for g in all_games})
    todo_days = {g["game_date"] for g in todo}

    print(f"trhy: {', '.join(markets)} | sezona {season} | snimek: {args.snapshot}")
    print(f"vzorek: {len(days)} hernich dnu z {len(all_days)}, {len(sample)} zapasu"
          f" | dny po ctvrtinach sezony {quarter_spread(all_days, days)}")
    print(f"hotovo {len(sample) - len(todo)}, zbyva {len(todo)} zapasu")
    cost = estimate_credits(len(todo), len(markets), len(todo_days))
    print(f"odhad ceny (strop): {cost} kreditu = {len(todo)} zapasu x {len(markets)}"
          f" trhy x {CREDITS_PER_MARKET_REGION} + {len(todo_days)} volani eventu")
    print(f"rozpocet behu: {args.budget:.0f} | rezerva uctu: {oc['reserve_backfill']}")
    if args.dry_run:
        if args.write_sample:
            write_sample(ROOT / args.write_sample, season, target, days, sample, all_days)
            print(f"seznam dnu zapsan: {args.write_sample}")
        print("\n--dry-run: nic se nestahovalo, zadny kredit se neutratil.")
        return

    boxed = conn.execute(
        """SELECT COUNT(*) FROM games g WHERE g.season = ? AND g.season_type = 'regular'
             AND EXISTS (SELECT 1 FROM team_game_logs t WHERE t.game_id = g.game_id)""",
        (season,)).fetchone()[0]
    if boxed < 0.95 * len(all_games):
        # Player names are matched against box-score appearances; buying
        # before they are loaded would store every line unmatched.
        print(f"STOP: box score ma jen {boxed}/{len(all_games)} zapasu {season}."
              " Nejdriv make data (backfill_boxscores + backfill_toi + backfill_players).")
        return

    from nhl_tool.odds_client import OddsApiError, OddsClient, cache_response
    client = OddsClient()
    client.get("/sports")  # free: learn the balance
    start_used = client.last_used or 0
    print(f"zustatek uctu: {client.last_remaining:.0f} kreditu")
    if (client.last_remaining or 0) <= oc["reserve_backfill"]:
        print("STOP: zustatek je pod rezervou, nic se nestahuje.")
        return

    buyer = HistoricalBuyer(conn, client, oc, markets, cache_fn=cache_response)
    per_market, all_unmatched, n_done = defaultdict(int), set(), 0
    for i, g in enumerate(todo, 1):
        spent = (client.last_used or 0) - start_used
        if spent >= args.budget or (client.last_remaining or 1e9) <= oc["reserve_backfill"]:
            print(f"\nSTOP ROZPOCTU po {n_done} zapasech: utraceno {spent:.0f},"
                  f" zustatek {client.last_remaining:.0f}. Spust znovu (resumable).")
            break
        gid = g["game_id"]
        try:
            res = buyer.price(g, args.snapshot)
            for market, n in res["rows"].items():
                per_market[market] += n
            all_unmatched |= res["unmatched"]
            set_state(conn, task, str(gid), res["status"], res["detail"])
            n_done += res["status"] == "done"
        except KeyboardInterrupt:
            conn.commit()
            print("\npreruseno - postup ulozen, spust znovu pro pokracovani")
            raise
        except OddsApiError as exc:
            set_state(conn, task, str(gid), "error", str(exc)[:200])
            print(f"  CHYBA {gid}: {exc}")
        conn.commit()
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} zapasu | zustatek {client.last_remaining:.0f}")

    print(f"\nshrnuti: {n_done} zapasu, radku: "
          + (", ".join(f"{m}={n}" for m, n in per_market.items()) or "nic")
          + f" | nesparovanych jmen {len(all_unmatched)}")
    print(f"utraceno {(client.last_used or 0) - start_used:.0f},"
          f" zustatek {(client.last_remaining or 0):.0f} kreditu")
    sample_ids = {g["game_id"] for g in sample}
    print("\n=== pokryti vzorku (zapasy s aspon jednou lajnou) ===")
    for market in markets:
        covered = {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM odds WHERE market = ? AND snapshot_kind = ?",
            (market, args.snapshot))}
        hit = len(sample_ids & covered)
        print(f"  {market}: {hit}/{len(sample_ids)} (K3 vyzaduje >= 300)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Main lines (moneyline + total goals) for models v2, block B: one archive
snapshot per game day at 15:00 UTC for the three complete seasons
(docs/models_v2_plan.md section 2).

CREDITS: 20 per game day (10 x 2 markets x 1 region), whatever the number
of games. Dry by default: prints the days and the cost and spends nothing
(no key needed). It buys only with --buy AND only when the whole remaining
cost fits the budget - a purchase above the user's cap does not start at
all (plan, 'Schvaleni a dodatky'). Resumable; stops at the account reserve.

Usage:
    python scripts/buy_main_lines.py                       # dry run
    python scripts/buy_main_lines.py --buy --budget 10500
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import main_lines as ml
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect, set_state, state_keys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--buy", action="store_true", help="really buy (after the user's go-ahead)")
    ap.add_argument("--budget", type=float, default=10500, help="max credits for the whole purchase")
    args = ap.parse_args()

    cfg = load_config()
    oc = cfg["odds"]
    conn = connect(resolve_db_path(cfg))
    days = ml.days_to_buy(conn, cfg["seasons"])
    done = state_keys(conn, ml.TASK, statuses=("done", "missing"))
    todo = [d for d in sorted(days) if d not in done]
    spent_before = ml.estimate(len(days) - len(todo))
    cost = ml.estimate(len(todo))
    print(f"sezony {', '.join(cfg['seasons'])} | hernich dnu {len(days)} | zapasu "
          f"{sum(len(v) for v in days.values())}")
    print(f"hotovo {len(days) - len(todo)} dnu ({spent_before} kreditu) | zbyva {len(todo)} dnu")
    print(f"cena zbytku: {cost} kreditu = {len(todo)} dnu x {ml.CREDITS_PER_CALL} | cely nakup "
          f"{ml.estimate(len(days))} | strop {args.budget:.0f} | rezerva uctu {oc['reserve_backfill']}")
    over = ml.estimate(len(days)) > args.budget
    if over:
        print(f"NAD STROPEM o {ml.estimate(len(days)) - args.budget:.0f} kreditu: nakup se nespusti.")
    if not args.buy:
        print("\nsuchy beh: nic se nestahovalo, zadny kredit se neutratil.")
        return
    if over or not todo:
        return

    from nhl_tool.odds_client import OddsApiError, OddsClient
    client = OddsClient()
    client.get("/sports")  # free: learn the balance
    start_used = client.last_used or 0
    print(f"zustatek uctu: {client.last_remaining:.0f} kreditu")
    if (client.last_remaining or 0) - cost < oc["reserve_backfill"]:
        print("STOP: po nakupu by zustatek klesl pod rezervu, nic se nestahuje.")
        return
    total = {"matched": 0, "started": 0, "rows": 0}
    seen = 0
    for i, day in enumerate(todo, 1):
        why = ml.coverage_stop(i - 1, total["matched"], seen - total["started"])
        if why:
            print(f"\nSTOP po {i - 1} dnech: {why}. Nic dalsiho se nekupuje.")
            break
        spent = (client.last_used or 0) - start_used
        if spent + ml.CREDITS_PER_CALL > args.budget - spent_before:      # never above the cap
            print(f"\nSTOP ROZPOCTU po {i - 1} dnech: utraceno {spent:.0f}. Nic dalsiho se nekupuje.")
            break
        try:
            payload, _ = client.get(f"/historical/sports/{oc['sport']}/odds", date=ml.anchor(day),
                                    regions=oc["regions"], markets=",".join(ml.MARKETS),
                                    oddsFormat="decimal")
            res = ml.store_snapshot(conn, payload, days[day])
            seen += len(days[day])
            for k in total:
                total[k] += res[k]
            set_state(conn, ml.TASK, day, "done" if res["rows"] else "missing",
                      f"games={len(days[day])} matched={res['matched']} started={res['started']}")
        except KeyboardInterrupt:
            conn.commit()
            print("\npreruseno - postup ulozen, spust znovu pro pokracovani")
            raise
        except OddsApiError as exc:
            set_state(conn, ml.TASK, day, "error", str(exc)[:200])
            print(f"  CHYBA {day}: {exc}")
        conn.commit()
        if i % 50 == 0:
            print(f"  {i}/{len(todo)} dnu | zustatek {client.last_remaining:.0f}", flush=True)
    print(f"\nshrnuti: zapasu s kurzy {total['matched']} z {seen} | zacalo pred snimkem "
          f"{total['started']} | radku {total['rows']}")
    print(f"utraceno {(client.last_used or 0) - start_used:.0f}, zustatek "
          f"{(client.last_remaining or 0):.0f} kreditu")


if __name__ == "__main__":
    main()

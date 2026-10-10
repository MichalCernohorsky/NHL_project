#!/usr/bin/env python3
"""Today's tips from the frozen naive model + the latest live snapshot, and
settlement of finished days (docs/tips_plan.md). Part of the cloud daily job,
after the live snapshot (collect_odds.py live). Idempotent: tips are written
once per snapshot (INSERT OR IGNORE), settlement only fills empty outcomes.

Usage:
    python scripts/build_tips.py                       # today (ET)
    python scripts/build_tips.py --date 2026-10-02 --kind morning   # test on another snapshot
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import tips
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.parsing import ET


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="ET game date (default: today ET)")
    ap.add_argument("--kind", default="live", choices=("live", "morning", "closing"))
    args = ap.parse_args()
    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    today = datetime.now(ET).date()
    day = args.date or today.isoformat()
    fixed = tips.fix_sim_prices(conn, tips.load_model(), cfg["odds"]["tipsport_margin"])
    if fixed:
        print(f"oprava vyplaty (konsensus misto vybrane knihy, migrace 0010): {fixed} tipu")
    settled = tips.settle(conn, (today - timedelta(days=1)).isoformat())
    res = tips.build(conn, day, kind=args.kind, margin=cfg["odds"]["tipsport_margin"])
    for (d,) in conn.execute("SELECT DISTINCT game_date FROM tips WHERE f_rate_60 IS NULL").fetchall():
        tips.store_factors(conn, d)        # tips built before the factor columns existed
    print(f"{day} ({args.kind}): zapasu s lajnami {res['games']}, kandidatu {res['candidates']},"
          f" novych {res['inserted']}, TIPU {res['playable']}, TOP {res['top']}"
          f" | vyhodnoceno {settled}")


if __name__ == "__main__":
    main()

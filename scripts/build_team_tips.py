#!/usr/bin/env python3
"""Team markets, stage 2 (docs/team_markets_plan.md 6, T-5): write the
frozen naive team models' expectations for today's games (once, before
puck drop) and settle finished days. Part of the cloud daily job, after
build_tips.py. Idempotent.

Usage:
    python scripts/build_team_tips.py                 # today (ET)
    python scripts/build_team_tips.py --date 2026-10-09
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_tips
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.parsing import ET


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="ET game date (default: today ET)")
    args = ap.parse_args()
    day = args.date or datetime.now(ET).date().isoformat()
    conn = connect(resolve_db_path(load_config()))
    stats = team_tips.build(conn, day)
    yesterday = (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()
    settled = team_tips.settle(conn, yesterday)
    print(f"{day}: zapasu {stats['games']} | novych predikci {stats['inserted']} | "
          f"uz zacate (bez predikce) {stats['started']} | vyhodnoceno {settled}")


if __name__ == "__main__":
    main()

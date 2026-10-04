#!/usr/bin/env python3
"""Fit the naive team models (team shots, two-minute penalties) on the
TRAINING seasons only and write models/naive_team.json
(docs/team_markets_plan.md 4 + amendment T-1; docs/team_models.md).

Reads 2023-24 and 2024-25 and nothing else: 2025-26 is the validation
season and must not touch any constant. Prints in-sample sanity checks
(training data only) and the SHA-256 of the written file - the freeze
fingerprint that goes into the plan before the validation is run.

Usage:
    python scripts/fit_naive_team.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_model as tm
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

OUT = ROOT / "models" / "naive_team.json"


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    conn = connect(resolve_db_path(load_config()))
    families = {}
    for family in tm.FAMILIES:
        train = tm.add_asof(tm.load_team_games(conn, tm.TRAIN, family))
        assert set(train["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
        const = tm.fit(train)
        mu = tm.predict(train, const)
        print(f"{family}: radku {const['rows']} | liga {const['league_mean_train']:.3f} | "
              f"h {const['h']:.4f} | w {const['w']} | c {const['c']} | k tym {const['k_team']:.2f} | "
              f"k zapas {const['k_game']:.2f} | prumer y {train['y'].mean():.3f} vs mu {mu.mean():.3f}")
        families[family] = const
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {
        "model": "naive_team_v1",
        "spec": "docs/team_markets_plan.md 4 + T-1; docs/team_models.md",
        "target": "team shots on goal and two-minute penalties in 60 minutes",
        "trained_on": tm.TRAIN,
        "window": tm.WINDOW, "league_rows": tm.LEAGUE_ROWS,
        "families": families,
        "git_commit": head,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

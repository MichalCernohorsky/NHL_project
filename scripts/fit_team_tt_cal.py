#!/usr/bin/env python3
"""Amendment T-4 of the team markets plan: calibration of P(over) for team
two-minute penalties (market T-T) at the lines 3.5 and 4.5, fitted on the
TRAINING seasons only. The mean stays the frozen naive team model's
(models/naive_team.json); the two baselines get their own calibration.

Writes models/naive_team_tt_cal.json and prints its SHA-256 (the freeze
fingerprint, written into the plan before the validation is run).

Usage:
    python scripts/fit_team_tt_cal.py
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

V1 = ROOT / "models" / "naive_team.json"
OUT = ROOT / "models" / "naive_team_tt_cal.json"


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    const = json.loads(V1.read_text())["families"]["penalties"]
    conn = connect(resolve_db_path(load_config()))
    train = tm.add_asof(tm.load_team_games(conn, tm.TRAIN, "penalties"))
    assert set(train["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
    y = train["y"].to_numpy()
    mu = tm.predict(train, const)
    base = tm.baselines(train, const["league_mean_train"])
    cal = tm.fit_calibration(y, mu)
    base_cal = {name: tm.fit_calibration(y, base[name]) for name in ("z0", "z1")}
    print(f"T-T radku {len(y)}")
    for line in tm.CAL_LINES:
        print(f"  lajna {line}: a {cal[line][0]:.3f} b {cal[line][1]:.3f} | TRENINK predpoved "
              f"{tm.logit_p(mu, cal[line]).mean() * 100:.1f} % | skutecnost {(y > line).mean() * 100:.1f} %")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {
        "model": "naive_team_tt_cal",
        "spec": "docs/team_markets_plan.md amendment T-4",
        "market": "T-T (team two-minute penalties in 60 minutes)",
        "form": "P(y > line) = sigmoid(a + b * ln mu), mu from naive_team_v1 (penalties family)",
        "base_model_sha256": hashlib.sha256(V1.read_bytes()).hexdigest(),
        "trained_on": tm.TRAIN,
        "rows": int(len(y)),
        "lines": {str(line): {"a": ab[0], "b": ab[1]} for line, ab in cal.items()},
        "baselines": {name: {str(line): {"a": ab[0], "b": ab[1]} for line, ab in c.items()}
                      for name, c in base_cal.items()},
        "git_commit": head,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

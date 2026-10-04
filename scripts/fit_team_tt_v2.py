#!/usr/bin/env python3
"""Amendment T-3 of the team markets plan: the shape nu of the CMP
distribution for team two-minute penalties (market T-T), fitted on the
TRAINING seasons only. The mean stays the frozen naive team model's
(models/naive_team.json); only the distribution around it changes. The two
baselines get their own nu, so the model cannot win by shape alone.

Writes models/naive_team_tt_v2.json and prints its SHA-256 (the freeze
fingerprint, written into the plan before the validation is run).

Usage:
    python scripts/fit_team_tt_v2.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_model as tm
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
OUT = ROOT / "models" / "naive_team_tt_v2.json"


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
    assert min(mu.min(), base["z0"].min(), base["z1"].min()) > 0, "a zero mean has no CMP"
    nu = tm.fit_nu(y, mu)
    base_nu = {name: tm.fit_nu(y, base[name]) for name in ("z0", "z1")}
    print(f"T-T radku {len(y)} | nu model {nu:.4f} | nu Z0 {base_nu['z0']:.4f} | nu Z1 {base_nu['z1']:.4f}")
    for line in tm.LINES["penalties"][0]:
        was = tm.ns.p_over(mu, line, const["k_team"]).mean() * 100
        now = tm.cmp_p_over(mu, line, nu).mean() * 100
        print(f"  TRENINK lajna {line}: v1 {was:.1f} % | v2 {now:.1f} % | skutecnost "
              f"{(y > line).mean() * 100:.1f} %")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {
        "model": "naive_team_tt_v2",
        "spec": "docs/team_markets_plan.md amendment T-3",
        "market": "T-T (team two-minute penalties in 60 minutes)",
        "distribution": "CMP with the mean of naive_team_v1 (penalties family)",
        "base_model_sha256": hashlib.sha256(V1.read_bytes()).hexdigest(),
        "trained_on": tm.TRAIN,
        "rows": int(len(y)),
        "nu": nu,
        "baselines_nu": base_nu,
        "git_commit": head,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

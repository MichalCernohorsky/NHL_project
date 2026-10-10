#!/usr/bin/env python3
"""Fit the team models v2 (blocks A and R) on the TRAINING seasons only and
write models/team_v2.json (docs/models_v2_plan.md 3; docs/models_v2_notes.md
1-4).

Reads 2023-24 and 2024-25 and nothing else: 2025-26 is the validation
season and must not touch any coefficient. Version 1's constants are read
from the frozen models/naive_team.json and are not refitted. Prints
in-sample checks (training data only) and the SHA-256 of the written file -
the freeze fingerprint that goes into the plan before the report is run.

Usage:
    python scripts/fit_team_v2.py
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
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
OUT = ROOT / "models" / "team_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common_rows(frames: dict) -> dict:
    """Both families on the same games (complete shots, attempts and penalties)."""
    games = set(frames["shots"]["game_id"]) & set(frames["penalties"]["game_id"])
    return {f: df[df["game_id"].isin(games)].reset_index(drop=True) for f, df in frames.items()}


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    const = json.loads(V1.read_text())["families"]
    conn = connect(resolve_db_path(load_config()))
    raw = t2.load_frames(conn, tm.TRAIN, const)
    frames = common_rows(raw)
    for family, df in frames.items():
        assert set(df["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
        print(f"{family}: radku {len(df)} (pred sjednocenim {len(raw[family])})")

    shots, pens = frames["shots"], frames["penalties"]
    a_s = t2.fit_block_a(shots, const["shots"], "shots")
    a_p = t2.fit_block_a(pens, const["penalties"], "penalties")
    y_p = pens["y"].to_numpy()
    mu_a = t2.predict_a(pens, const["penalties"], a_p)
    a_p["cal"] = t2.cal_json(tm.fit_calibration(y_p, mu_a))
    ref = t2.fit_rho(pens, const["penalties"], a_p)
    mu_r = t2.predict_r(pens, const["penalties"], a_p, ref["rho"])
    ref["cal"] = t2.cal_json(tm.fit_calibration(y_p, mu_r))

    for name, block in (("strely", a_s), ("tresty", a_p)):
        coef = " | ".join(f"{c} {v:+.4f}" for c, v in block["coef"].items())
        print(f"{name}: {coef} | k {block['k']:.2f} | loglik {block['loglik']:.1f} "
              f"(v1 {block['loglik_v1']:.1f}, zisk {block['loglik'] - block['loglik_v1']:+.1f})"
              + (f" | alfa {block['alpha']}" if "alpha" in block else ""))
    print(f"rozhodci: rho {ref['rho']:+.4f} | loglik {ref['loglik']:.1f} "
          f"(blok A {a_p['loglik']:.1f}, zisk {ref['loglik'] - a_p['loglik']:+.1f})")
    print("--- kontrola v treninku (in-sample, jen spravnost kodu) ---")
    mu_s = t2.predict_a(shots, const["shots"], a_s)
    print(f"strely: prumer y {shots['y'].mean():.3f} | v1 {tm.predict(shots, const['shots']).mean():.3f} "
          f"| v2 {mu_s.mean():.3f}")
    print(f"tresty: prumer y {y_p.mean():.3f} | v1 {tm.predict(pens, const['penalties']).mean():.3f} "
          f"| v2 {mu_a.mean():.3f} | R {mu_r.mean():.3f}")
    for line, ab in t2.as_cal(a_p["cal"]).items():
        print(f"tresty P(> {line}): v2 {tm.logit_p(mu_a, ab).mean():.4f} vs skutecnost "
              f"{(y_p > line).mean():.4f}")
    print(f"b2b tym {shots['B_team'].mean():.3f} | faze 1 {shots['F1'].mean():.3f} | "
          f"D smer. odch. {pens['D'].std():.3f} | R smer. odch. {pens['R'].std():.3f}")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {
        "model": "team_v2",
        "spec": "docs/models_v2_plan.md 3; docs/models_v2_notes.md 1-4",
        "target": "team shots on goal and two-minute penalties in 60 minutes",
        "trained_on": tm.TRAIN,
        "builds_on": {"naive_team.json": sha(V1)},
        "columns": t2.COLS_A, "phase": list(t2.PHASE),
        "shots": a_s, "penalties": a_p, "referees": ref,
        "git_commit": head,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {sha(OUT)}")


if __name__ == "__main__":
    main()

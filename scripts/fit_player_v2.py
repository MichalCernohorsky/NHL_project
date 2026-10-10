#!/usr/bin/env python3
"""Fit the player shots model v2 (block A) on the TRAINING seasons only and
write models/player_v2.json (docs/models_v2_plan.md 4; docs/models_v2_notes.md
5).

Reads 2023-24 and 2024-25 and nothing else. Version 1's constants (the
3-hour prior weight, the windows, the overtime ratio) and the frozen team
penalty factors are read from their frozen files and are not refitted.
Prints in-sample checks and the SHA-256 of the written file - the freeze
fingerprint that goes into the plan before the report is run.

Usage:
    python scripts/fit_player_v2.py
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

from nhl_tool import naive_sog as ns
from nhl_tool import player_v2 as pv
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_sog.json"
TEAM = ROOT / "models" / "naive_team.json"
OUT = ROOT / "models" / "player_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    v1 = json.loads(V1.read_text())
    const_pen = json.loads(TEAM.read_text())["families"]["penalties"]
    conn = connect(resolve_db_path(load_config()))
    train = pv.load_skater_games(conn, tm.TRAIN)
    assert set(train["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
    pens = tm.load_team_games(conn, tm.TRAIN, "penalties")
    ctx = pv.context(tm.add_asof(pens), t2.load_b2b(conn), const_pen)
    const = pv.fit_constants(train, pens)
    feats = pv.features(train, pens, ctx, const)
    model = {**const, **pv.fit(feats), "ot_ratio": v1["ot_ratio"]}
    rows = feats[feats["entry_phase0"]]
    y, mu = rows["sog_reg"].to_numpy(), pv.predict(rows, model)

    # version 1 on the same rows, for the in-sample comparison only
    old = ns.load_skater_games(conn, tm.TRAIN)
    f1 = ns.features(old, {"league_team_shots": v1["league_team_shots"],
                           "prior_rate_per_s": v1["prior_rate_per_s"], "ot_ratio": v1["ot_ratio"]})
    both = rows[["game_id", "player_id", "sog_reg"]].assign(mu2=mu).merge(
        f1[["game_id", "player_id", "mu_60"]], on=["game_id", "player_id"])
    ll1 = float(tm.nb_logpmf(both["sog_reg"].to_numpy(), both["mu_60"].to_numpy(), v1["nb_k"]).sum())
    ll2 = float(tm.nb_logpmf(both["sog_reg"].to_numpy(), both["mu2"].to_numpy(), model["nb_k"]).sum())
    model["loglik_v1_same_rows"], model["loglik_same_rows"] = ll1, ll2

    print(f"trenovaci radky: {model['fit_rows']} (spolecne s v1: {len(both)})")
    print(f"alfa {model['alpha']} | pi {model['pi']} | " +
          " | ".join(f"{c} {v:+.4f}" for c, v in model["coef"].items()) + f" | k {model['nb_k']:.2f}")
    print(f"loglik v2 {ll2:.1f} vs v1 {ll1:.1f} (zisk {ll2 - ll1:+.1f}) na spolecnych radcich")
    print(f"podil presilovky na case {const['pp_share']:.4f} | liga strel mimo oslabeni "
          f"{const['league_np_against']:.2f} | strel v oslabeni na trest {const['league_pk_per_penalty']:.3f}")
    for kind in ("S", "A"):
        print(f"rychlost {kind} za 60 min: " + ", ".join(
            f"{x} {g} {v * 3600:.2f}" for x in pv.SITS for g, v in const["rate"][kind][x].items()))
    print("--- kontrola v treninku (in-sample, jen spravnost kodu) ---")
    print(f"prumer predikce {mu.mean():.3f} vs skutecnost {y.mean():.3f}")
    for line in (0.5, 1.5, 2.5, 3.5):
        print(f"P(> {line}): model {ns.p_over(mu, line, model['nb_k']).mean():.4f} vs skutecnost "
              f"{(y > line).mean():.4f}")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {"model": "player_v2", "spec": "docs/models_v2_plan.md 4; docs/models_v2_notes.md 5",
             "target": "player shots on goal in 60 minutes (sog_reg)", "trained_on": tm.TRAIN,
             "builds_on": {"naive_sog.json": sha(V1), "naive_team.json": sha(TEAM)},
             **model, "git_commit": head,
             "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {sha(OUT)}")


if __name__ == "__main__":
    main()

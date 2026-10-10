#!/usr/bin/env python3
"""Fit block B of the player shots model v2 (game script from the main
lines) on the TRAINING seasons only and write models/player_v2b.json
(docs/models_v2_plan.md 4; docs/models_v2_notes.md, amendment N-2).

delta is estimated on top of the FROZEN block A (models/player_v2.json),
from training rows that pass the phase 0 entry and whose game has main
lines of at least three books.

Usage:
    python scripts/fit_player_v2b.py
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fit_team_v2 import sha
from nhl_tool import main_lines as ml
from nhl_tool import player_v2 as pv
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

VA = ROOT / "models" / "player_v2.json"
TEAM = ROOT / "models" / "naive_team.json"
OUT = ROOT / "models" / "player_v2b.json"


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    va = json.loads(VA.read_text())
    const_pen = json.loads(TEAM.read_text())["families"]["penalties"]
    conn = connect(resolve_db_path(load_config()))
    train = pv.load_skater_games(conn, tm.TRAIN)
    assert set(train["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
    pens = tm.load_team_games(conn, tm.TRAIN, "penalties")
    ctx = pv.context(tm.add_asof(pens), t2.load_b2b(conn), const_pen)
    feats = pv.features(train, pens, ctx, va)
    rows = feats[feats["entry_phase0"]].reset_index(drop=True)

    script = ml.game_script(conn)
    in_train = script[script["game_id"].isin(set(train["game_id"]))]
    both = in_train["p_home"].notna() & in_train["goals"].notna()
    goals_mean = float(in_train.loc[both, "goals"].mean())
    rows = t2.add_script(rows, t2.team_script(conn, script, goals_mean))
    y = rows["sog_reg"].to_numpy()
    mu_a = pv.predict(rows, va)
    block = t2.fit_block_b(y, mu_a, rows[t2.COLS_B])
    ll_a = float(tm.nb_logpmf(y, mu_a, va["nb_k"]).sum())
    mu_b = t2.predict_b(rows, mu_a, block)
    print(f"trenovaci radky {block['rows']} | s kurzy {block['rows_with_lines']} | prumer cekanych "
          f"golu {goals_mean:.3f}")
    print(" | ".join(f"{c} {v:+.4f}" for c, v in block["coef"].items()) + f" | k {block['k']:.2f}")
    print(f"loglik B {block['loglik']:.1f} vs A {ll_a:.1f} (zisk {block['loglik'] - ll_a:+.1f}) | "
          f"prumer predikce {mu_b.mean():.3f} vs skutecnost {y.mean():.3f}")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {"model": "player_v2b", "spec": "docs/models_v2_plan.md 4; docs/models_v2_notes.md N-2",
             "trained_on": tm.TRAIN,
             "builds_on": {"player_v2.json": sha(VA), "naive_team.json": sha(TEAM)},
             "columns": t2.COLS_B, "min_books": ml.MIN_BOOKS, "goals_mean_train": goals_mean,
             "coef": block["coef"], "nb_k": block["k"], "fit_rows": block["rows"],
             "rows_with_lines": block["rows_with_lines"], "loglik": block["loglik"], "loglik_a": ll_a,
             "ot_ratio": va["ot_ratio"], "git_commit": head,
             "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    OUT.write_text(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {sha(OUT)}")


if __name__ == "__main__":
    main()

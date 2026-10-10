#!/usr/bin/env python3
"""Fit block B of the team models v2 (game script from the main lines) on
the TRAINING seasons only and write models/team_v2b.json
(docs/models_v2_plan.md 3; docs/models_v2_notes.md, amendment N-2).

delta is estimated on top of the FROZEN block A (models/team_v2.json), from
training rows whose game has main lines of at least three books. Reads
2023-24 and 2024-25 and nothing else. Prints in-sample checks and the
SHA-256 of the written file.

Usage:
    python scripts/fit_team_v2b.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fit_team_v2 import common_rows, sha
from nhl_tool import main_lines as ml
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
V2 = ROOT / "models" / "team_v2.json"
OUT = ROOT / "models" / "team_v2b.json"


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    const = json.loads(V1.read_text())["families"]
    v2 = json.loads(V2.read_text())
    conn = connect(resolve_db_path(load_config()))
    frames = common_rows(t2.load_frames(conn, tm.TRAIN, const))
    script = ml.game_script(conn)
    train_games = set(frames["shots"]["game_id"])
    in_train = script[script["game_id"].isin(train_games)]
    both = in_train["p_home"].notna() & in_train["goals"].notna()
    goals_mean = float(in_train.loc[both, "goals"].mean())
    ts = t2.team_script(conn, script, goals_mean)
    print(f"trenovaci zapasy {len(train_games)} | s kurzy aspon 3 knih {int(both.sum())} | "
          f"prumer cekanych golu {goals_mean:.3f} | prumer p domacich "
          f"{in_train.loc[both, 'p_home'].mean():.3f}")

    blocks = {}
    for family in ("shots", "penalties"):
        df = t2.add_script(frames[family], ts)
        assert set(df["season"]) == set(tm.TRAIN), "training frame must hold training seasons only"
        y = df["y"].to_numpy()
        mu_a = t2.predict_a(df, const[family], v2[family])
        block = t2.fit_block_b(y, mu_a, df[t2.COLS_B])
        block["loglik_a"] = float(tm.nb_logpmf(y, mu_a, v2[family]["k"]).sum())
        mu_b = t2.predict_b(df, mu_a, block)
        if family == "penalties":
            block["cal"] = t2.cal_json(tm.fit_calibration(y, mu_b))
            ref = t2.fit_rho(df, const[family], v2[family], mu=mu_b)
            ref["cal"] = t2.cal_json(tm.fit_calibration(y, mu_b * __import__("numpy").exp(
                ref["rho"] * df["R"].to_numpy(dtype=float))))
            blocks["referees"] = ref
        blocks[family] = block
        coef = " | ".join(f"{c} {v:+.4f}" for c, v in block["coef"].items())
        print(f"{family}: {coef} | k {block['k']:.2f} | radku s kurzy {block['rows_with_lines']}/"
              f"{block['rows']} | loglik {block['loglik']:.1f} (blok A {block['loglik_a']:.1f}, zisk "
              f"{block['loglik'] - block['loglik_a']:+.1f}) | prumer y {y.mean():.3f} vs mu_B {mu_b.mean():.3f}")
    print(f"rozhodci nad B: rho {blocks['referees']['rho']:+.4f}")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {"model": "team_v2b", "spec": "docs/models_v2_plan.md 3; docs/models_v2_notes.md N-2",
             "trained_on": tm.TRAIN,
             "builds_on": {"naive_team.json": sha(V1), "team_v2.json": sha(V2)},
             "columns": t2.COLS_B, "min_books": ml.MIN_BOOKS, "goals_mean_train": goals_mean,
             **blocks, "git_commit": head,
             "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | SHA-256 {sha(OUT)}")


if __name__ == "__main__":
    main()

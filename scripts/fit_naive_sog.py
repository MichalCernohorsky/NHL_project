#!/usr/bin/env python3
"""Fit the naive shots model's constants on the TRAINING seasons only and
write models/naive_sog.json (plan 6.2 + D3; interpretation docs/naive_model.md).

Reads 2023-24 and 2024-25 and nothing else: 2025-26 is the validation
season and must not touch any constant. Prints in-sample sanity checks
(training data only) and the SHA-256 of the written file - the freeze
fingerprint that goes into the plan before any 2025-26 odds are bought.

Usage:
    python scripts/fit_naive_sog.py
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
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

TRAIN = ["2023-24", "2024-25"]
OUT = ROOT / "models" / "naive_sog.json"


def main():
    if OUT.exists() and "--force" not in sys.argv:
        # Frozen 2. 10. 2026 (plan, "Zamrazení naivního modelu"). Re-fitting
        # would change the fingerprint the phase 0 test is pinned to.
        print(f"{OUT.relative_to(ROOT)} je zamrazeny - neprepisuji (--force jen s novou erou).")
        sys.exit(1)
    conn = connect(resolve_db_path(load_config()))
    train = ns.load_skater_games(conn, TRAIN)
    assert set(train["season"]) == set(TRAIN), "training frame must hold training seasons only"
    const = ns.fit_constants(train)
    feats = ns.features(train, const)
    fit_rows = feats[feats["entry_phase0"]]
    y, mu = fit_rows["sog_reg"].to_numpy(), fit_rows["mu_60"].to_numpy()
    k = ns.fit_dispersion(y, mu)
    ll_nb, ll_po = ns.loglik(y, mu, k), ns.loglik_poisson(y, mu)

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    model = {
        "model": "naive_sog_v1",
        "spec": "docs/market_discovery_plan.md 6.2 + D3 + D6; docs/naive_model.md",
        "target": "player shots on goal in 60 minutes (sog_reg)",
        "trained_on": TRAIN,
        "fit_rows": int(len(fit_rows)),
        "league_team_shots": const["league_team_shots"],
        "prior_rate_per_s": const["prior_rate_per_s"],
        "ot_ratio": const["ot_ratio"],
        "nb_k": k,
        "loglik_nb": ll_nb, "loglik_poisson": ll_po,
        "params": {"W_seconds": ns.W_SECONDS, "opp_window": ns.OPP_WINDOW,
                   "opp_shrink_games": ns.OPP_SHRINK_GAMES, "toi_window": ns.TOI_WINDOW,
                   "min_gp_season": ns.MIN_GP_SEASON, "min_gp_prior": ns.MIN_GP_PRIOR,
                   "min_gp_prev_live": ns.MIN_GP_PREV_LIVE},
        "code_commit": head,
        "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(model, indent=1, sort_keys=True) + "\n")
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()

    print(f"trenovaci radky (vstup >= 10 zapasu v sezone): {len(fit_rows)}")
    print(f"liga: {const['league_team_shots']:.2f} strel tymu za 60 min na zapas")
    print("prior na 60 min ledu: " + ", ".join(f"{g} {v * 3600:.3f}"
                                               for g, v in const["prior_rate_per_s"].items()))
    print("podil strel v prodlouzeni: " + ", ".join(f"{g} {v:.4f}" for g, v in const["ot_ratio"].items()))
    print(f"disperze k = {k:.2f} | loglik NB {ll_nb:.1f} vs Poisson {ll_po:.1f}")
    print("\n--- kontrola v treninku (in-sample, jen spravnost kodu) ---")
    print(f"prumer predikce {mu.mean():.3f} vs skutecnost {y.mean():.3f}")
    fit_rows = fit_rows.assign(bin=np.digitize(mu, np.quantile(mu, np.linspace(0.1, 0.9, 9))))
    print("decil | predikce | skutecnost | radku")
    for b, part in fit_rows.groupby("bin"):
        print(f"{b + 1:5d} | {part.mu_60.mean():8.3f} | {part.sog_reg.mean():10.3f} | {len(part)}")
    for line in (0.5, 1.5, 2.5, 3.5):
        p = ns.p_over(mu, line, k)
        print(f"P(> {line}): model {p.mean():.4f} vs skutecnost {(y > line).mean():.4f}")
    print(f"\nzapsano {OUT.relative_to(ROOT)} | SHA-256 {sha}")


if __name__ == "__main__":
    main()

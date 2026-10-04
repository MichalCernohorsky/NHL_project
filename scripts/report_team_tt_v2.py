#!/usr/bin/env python3
"""Amendment T-3: the T-T market (team two-minute penalties) with the CMP
distribution on the validation season 2025-26 - criterion T1, calibration
next to version 1, null simulation. Writes docs/team_tt_v2_report.md.

Run once, after models/naive_team_tt_v2.json is frozen.

Usage:
    python scripts/report_team_tt_v2.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_model as tm
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
V2 = ROOT / "models" / "naive_team_tt_v2.json"
OUT = ROOT / "docs" / "team_tt_v2_report.md"
NULL_REPS = 500


def cz(x, d=4):
    return f"{x:.{d}f}".replace(".", ",")


def main():
    const = json.loads(V1.read_text())["families"]["penalties"]
    v2 = json.loads(V2.read_text())
    nu, bnu = v2["nu"], v2["baselines_nu"]
    conn = connect(resolve_db_path(load_config()))
    df = tm.add_asof(tm.load_team_games(conn, [*tm.TRAIN, tm.VALID], "penalties"))
    val = df[df["season"] == tm.VALID].reset_index(drop=True)
    y = val["y"].to_numpy()
    mu = tm.predict(val, const)
    base = tm.baselines(val, const["league_mean_train"])
    assert min(mu.min(), base["z0"].min(), base["z1"].min()) > 0, "a zero mean has no CMP"
    day_idx, counts = tm.boot_counts(val["game_date"].to_numpy())
    base_loss = {n: -tm.cmp_logpmf(y, base[n], bnu[n]) for n in ("z0", "z1")}
    res = tm.t1_losses(-tm.cmp_logpmf(y, mu, nu), base_loss, day_idx, counts)
    lines = tm.LINES["penalties"][0]
    cal2 = tm.calibration(y, mu, nu, lines, p_over=tm.cmp_p_over)
    cal1 = tm.calibration(y, mu, const["k_team"], lines)
    per_line = [(line, tm.ns.p_over(mu, line, const["k_team"]).mean(),
                 tm.cmp_p_over(mu, line, nu).mean(), (y > line).mean()) for line in lines]

    rng = np.random.default_rng(17)
    opp_def = tm.opponent_defence(val, const)
    passes = {"a": 0, "b": 0}
    for _ in range(NULL_REPS):
        for kind, mu_null in (("a", tm.predict(val, const, defence_override=rng.permutation(opp_def))),
                              ("b", rng.permutation(mu))):
            passes[kind] += tm.t1_losses(-tm.cmp_logpmf(y, mu_null, nu), base_loss,
                                         day_idx, counts)["pass"]
    null = {k: v / NULL_REPS for k, v in passes.items()}
    print(f"T-T v2: n={len(y)} | ztrata {res['loss_model']:.4f} | Z0 +{res['z0']['gain']:.4f} "
          f"[{res['z0']['lo']:.4f}, {res['z0']['hi']:.4f}] | Z1 +{res['z1']['gain']:.4f} "
          f"[{res['z1']['lo']:.4f}, {res['z1']['hi']:.4f}] | T1 {'ANO' if res['pass'] else 'ne'} | "
          f"nula a {null['a']:.3f} b {null['b']:.3f}")

    out = ["# Tresty týmu (T-T), verze 2 — užší rozdělení (dodatek T-3)\n",
           "Plán `docs/team_markets_plan.md`, dodatek T-3. Průměr ze zamrazeného "
           "`models/naive_team.json`, rozdělení CMP ze zamrazeného "
           f"`models/naive_team_tt_v2.json` (ν = {cz(nu)}, odhad jen na "
           f"{', '.join(v2['trained_on'])}). Sezóna 2025-26 je u tohoto trhu použita "
           "k ověření **podruhé** (poprvé v `docs/team_stage1_report.md`). Vygenerováno "
           "skriptem `scripts/report_team_tt_v2.py`; ručně se needituje.\n",
           "## Kritérium T1\n",
           "Základy mají vlastní ν odhadnuté na trénovacích sezónách "
           f"(Z0 {cz(bnu['z0'])}, Z1 {cz(bnu['z1'])}).\n",
           "| řádků | herních dnů | ztráta modelu | zisk proti Z0 (liga) | 95% interval | "
           "zisk proti Z1 (průměr týmu) | 95% interval | T1 |",
           "|---|---|---|---|---|---|---|---|",
           f"| {len(y)} | {counts.shape[1]} | {cz(res['loss_model'])} | {cz(res['z0']['gain'])} | "
           f"{cz(res['z0']['lo'])} až {cz(res['z0']['hi'])} | {cz(res['z1']['gain'])} | "
           f"{cz(res['z1']['lo'])} až {cz(res['z1']['hi'])} | "
           f"**{'splněno' if res['pass'] else 'nesplněno'}** |",
           "\n## Kalibrace po lajnách: P(více než lajna), průměr přes všechny řádky\n",
           "| lajna | verze 1 (Poisson) | verze 2 (CMP) | skutečnost |", "|---|---|---|---|"]
    for line, p1, p2, obs in per_line:
        out.append(f"| {cz(line, 1)} | {cz(p1 * 100, 1)} % | {cz(p2 * 100, 1)} % | {cz(obs * 100, 1)} % |")
    out += ["\n## Kalibrace v pěti pásmech (lajny 3.5 a 4.5 dohromady)\n",
            "| pásmo | případů | v1 předpověď | v1 skutečnost | v2 předpověď | v2 skutečnost |",
            "|---|---|---|---|---|---|"]
    for i in range(len(cal2)):
        a, b = cal1.iloc[i], cal2.iloc[i]
        out.append(f"| {i + 1} | {int(b['n'])} | {cz(a['predicted'] * 100, 1)} % | "
                   f"{cz(a['observed'] * 100, 1)} % | {cz(b['predicted'] * 100, 1)} % | "
                   f"{cz(b['observed'] * 100, 1)} % |")
    out += ["\n## Simulace nulového efektu\n",
            f"{NULL_REPS} opakování. Podíl, který by splnil T1: promíchaní soupeři "
            f"{cz(null['a'] * 100, 1)} %, promíchané předpovědi {cz(null['b'] * 100, 1)} %.\n"]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

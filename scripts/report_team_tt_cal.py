#!/usr/bin/env python3
"""Amendment T-4: the T-T market (team two-minute penalties) with calibrated
P(over) at 3.5 and 4.5 on the validation season 2025-26 - criterion T1 on
the over/under outcome, calibration, null simulation. Writes
docs/team_tt_cal_report.md. Run once, after models/naive_team_tt_cal.json
is frozen.

Usage:
    python scripts/report_team_tt_cal.py
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
CAL = ROOT / "models" / "naive_team_tt_cal.json"
OUT = ROOT / "docs" / "team_tt_cal_report.md"
NULL_REPS = 500


def cz(x, d=4):
    return f"{x:.{d}f}".replace(".", ",")


def as_cal(d: dict) -> dict:
    return {float(line): (v["a"], v["b"]) for line, v in d.items()}


def main():
    const = json.loads(V1.read_text())["families"]["penalties"]
    model = json.loads(CAL.read_text())
    cal = as_cal(model["lines"])
    base_cal = {name: as_cal(c) for name, c in model["baselines"].items()}
    conn = connect(resolve_db_path(load_config()))
    df = tm.add_asof(tm.load_team_games(conn, [*tm.TRAIN, tm.VALID], "penalties"))
    val = df[df["season"] == tm.VALID].reset_index(drop=True)
    y = val["y"].to_numpy()
    mu = tm.predict(val, const)
    base = tm.baselines(val, const["league_mean_train"])
    days = np.tile(val["game_date"].to_numpy(), len(cal))
    day_idx, counts = tm.boot_counts(days)
    loss, over = tm.cal_losses(y, mu, cal)
    base_loss = {n: tm.cal_losses(y, base[n], base_cal[n])[0] for n in ("z0", "z1")}
    res = tm.t1_losses(loss, base_loss, day_idx, counts)
    n = len(y)
    per_line = []
    for i, line in enumerate(cal):
        sl = slice(i * n, (i + 1) * n)
        r = tm.t1_losses(loss[sl], {k: v[sl] for k, v in base_loss.items()},
                         *tm.boot_counts(val["game_date"].to_numpy()))
        r.update(line=line, predicted=float(tm.logit_p(mu, cal[line]).mean()),
                 observed=float(over[sl].mean()))
        per_line.append(r)
    cal_tab = tm.cal_calibration(y, mu, cal)

    rng = np.random.default_rng(17)
    opp_def = tm.opponent_defence(val, const)
    passes = {"a": 0, "b": 0}
    for _ in range(NULL_REPS):
        for kind, mu_null in (("a", tm.predict(val, const, defence_override=rng.permutation(opp_def))),
                              ("b", rng.permutation(mu))):
            passes[kind] += tm.t1_losses(tm.cal_losses(y, mu_null, cal)[0], base_loss,
                                         day_idx, counts)["pass"]
    null = {k: v / NULL_REPS for k, v in passes.items()}
    print(f"T-T kalibrace: n={n} dnu={len(set(val['game_date']))} | ztrata {res['loss_model']:.4f} | "
          f"Z0 +{res['z0']['gain']:.4f} [{res['z0']['lo']:.4f}, {res['z0']['hi']:.4f}] | "
          f"Z1 +{res['z1']['gain']:.4f} [{res['z1']['lo']:.4f}, {res['z1']['hi']:.4f}] | "
          f"T1 {'ANO' if res['pass'] else 'ne'} | nula a {null['a']:.3f} b {null['b']:.3f}")
    for r in per_line:
        print(f"  lajna {r['line']}: predpoved {r['predicted'] * 100:.1f} % | skutecnost "
              f"{r['observed'] * 100:.1f} % | Z0 +{r['z0']['gain']:.4f} [{r['z0']['lo']:.4f}, "
              f"{r['z0']['hi']:.4f}] | Z1 +{r['z1']['gain']:.4f} [{r['z1']['lo']:.4f}, {r['z1']['hi']:.4f}]")

    out = ["# Tresty týmu (T-T) s kalibrací P(více) — dodatek T-4, sezóna 2025-26\n",
           "Plán `docs/team_markets_plan.md`, dodatek T-4. Průměr μ ze zamrazeného "
           "`models/naive_team.json`, kalibrace ze zamrazeného `models/naive_team_tt_cal.json` "
           f"(odhad jen na {', '.join(model['trained_on'])}). Sezóna 2025-26 je u tohoto trhu "
           "použita k ověření **podruhé** (poprvé `docs/team_stage1_report.md`). Vygenerováno "
           "skriptem `scripts/report_team_tt_cal.py`; ručně se needituje.\n",
           "## Kritérium T1 (na výsledku více / méně, lajny 3.5 a 4.5 dohromady)\n",
           "Ztráta = −ln pravděpodobnosti toho, co nastalo. Zisk = o kolik má základ větší "
           "ztrátu než model. Bootstrap 95 %, seed 17, 10 000, převzorkují se herní dny.\n",
           "| řádků × lajny | herních dnů | ztráta modelu | zisk proti Z0 | 95% interval | "
           "zisk proti Z1 | 95% interval | T1 |", "|---|---|---|---|---|---|---|---|",
           f"| {len(loss)} | {counts.shape[1]} | {cz(res['loss_model'])} | {cz(res['z0']['gain'])} | "
           f"{cz(res['z0']['lo'])} až {cz(res['z0']['hi'])} | {cz(res['z1']['gain'])} | "
           f"{cz(res['z1']['lo'])} až {cz(res['z1']['hi'])} | **{'splněno' if res['pass'] else 'nesplněno'}** |",
           "\n## Po lajnách\n",
           "| lajna | předpověď „více" | skutečnost | zisk proti Z0 | 95% interval | zisk proti Z1 | 95% interval |",
           "|---|---|---|---|---|---|---|"]
    for r in per_line:
        out.append(f"| {cz(r['line'], 1)} | {cz(r['predicted'] * 100, 1)} % | {cz(r['observed'] * 100, 1)} % | "
                   f"{cz(r['z0']['gain'])} | {cz(r['z0']['lo'])} až {cz(r['z0']['hi'])} | "
                   f"{cz(r['z1']['gain'])} | {cz(r['z1']['lo'])} až {cz(r['z1']['hi'])} |")
    out += ["\n## Kalibrace v pěti pásmech (obě lajny)\n",
            "| pásmo | případů | předpověď | skutečnost |", "|---|---|---|---|"]
    for i, row in cal_tab.iterrows():
        out.append(f"| {i + 1} | {int(row['n'])} | {cz(row['predicted'] * 100, 1)} % | "
                   f"{cz(row['observed'] * 100, 1)} % |")
    out += ["\n## Simulace nulového efektu\n",
            f"{NULL_REPS} opakování, kalibrace se nepřeodhadovala. Podíl, který by splnil T1: "
            f"promíchaní soupeři {cz(null['a'] * 100, 1)} %, promíchané předpovědi "
            f"{cz(null['b'] * 100, 1)} %.\n"]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

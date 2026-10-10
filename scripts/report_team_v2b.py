#!/usr/bin/env python3
"""Block B of the team models v2 (game script from the main lines) on the
validation season 2025-26: B against block A (the replacement rule of
docs/models_v2_plan.md 5), referees on top of B, with power and null
simulations. Writes docs/team_v2b_report.md. Run once, after
models/team_v2b.json is frozen.

Usage:
    python scripts/report_team_v2b.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from report_team_v2 import SIMS, cz, gain_row, pct, sim_bands, sim_counts
from nhl_tool import main_lines as ml
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
CAL = ROOT / "models" / "naive_team_tt_cal.json"
V2 = ROOT / "models" / "team_v2.json"
V2B = ROOT / "models" / "team_v2b.json"
OUT = ROOT / "docs" / "team_v2b_report.md"


def main():
    const = json.loads(V1.read_text())["families"]
    cal_v1 = t2.as_cal(json.loads(CAL.read_text())["lines"])
    v2, vb = json.loads(V2.read_text()), json.loads(V2B.read_text())
    assert vb["builds_on"]["team_v2.json"] == hashlib.sha256(V2.read_bytes()).hexdigest()
    conn = connect(resolve_db_path(load_config()))
    frames = t2.load_frames(conn, [*tm.TRAIN, tm.VALID], const)
    games = set(frames["shots"]["game_id"]) & set(frames["penalties"]["game_id"])
    ts = t2.team_script(conn, ml.game_script(conn), vb["goals_mean_train"])
    val = {f: t2.add_script(df[(df["season"] == tm.VALID) & df["game_id"].isin(games)].reset_index(drop=True), ts)
           for f, df in frames.items()}
    rng = np.random.default_rng(17)

    s = val["shots"]
    y = s["y"].to_numpy()
    mu1 = tm.predict(s, const["shots"])
    mua = t2.predict_a(s, const["shots"], v2["shots"])
    mub = t2.predict_b(s, mua, vb["shots"])
    k1, ka, kb = const["shots"]["k_team"], v2["shots"]["k"], vb["shots"]["k"]
    day_idx, counts = tm.boot_counts(s["game_date"].to_numpy())
    l1, la, lb = (-tm.nb_logpmf(y, mu, k) for mu, k in ((mu1, k1), (mua, ka), (mub, kb)))
    st = gain_row("S-T", la - lb, day_idx, counts)
    st.update(loss_a=float(la.mean()), loss_b=float(lb.mean()), n=len(y), days=counts.shape[1],
              lines=float(s["S0"].mean()),
              null=sim_counts(mua, ka, mub, kb, "a", day_idx, counts, rng),
              power=sim_counts(mua, ka, mub, kb, "b", day_idx, counts, rng))
    st_v1 = gain_row("S-T proti v1", l1 - lb, day_idx, counts)

    p = val["penalties"]
    yp = p["y"].to_numpy()
    lines = list(cal_v1)
    over = (yp[:, None] > np.array(lines)[None, :]).astype(float)
    m1 = tm.predict(p, const["penalties"])
    ma = t2.predict_a(p, const["penalties"], v2["penalties"])
    mb = t2.predict_b(p, ma, vb["penalties"])
    mr = mb * np.exp(vb["referees"]["rho"] * p["R"].to_numpy(dtype=float))
    cal_a, cal_b, cal_r = (t2.as_cal(x) for x in (v2["penalties"]["cal"], vb["penalties"]["cal"],
                                                  vb["referees"]["cal"]))
    p1, pa, pb, pr = (t2.tt_probs(m, c) for m, c in ((m1, cal_v1), (ma, cal_a), (mb, cal_b), (mr, cal_r)))
    didx, dcounts = tm.boot_counts(np.tile(p["game_date"].to_numpy(), len(lines)))
    b1, ba, bb, br = (t2.bern_loss(x, over) for x in (p1, pa, pb, pr))
    tt = gain_row("T-T", ba - bb, didx, dcounts)
    tt.update(loss_a=float(ba.mean()), loss_b=float(bb.mean()), n=len(yp), days=dcounts.shape[1],
              lines=float(p["S0"].mean()),
              null=sim_bands(pa, pb, "a", didx, dcounts, rng),
              power=sim_bands(pa, pb, "b", didx, dcounts, rng))
    tt_v1 = gain_row("T-T proti v1", b1 - bb, didx, dcounts)
    rr = gain_row("R nad B", bb - br, didx, dcounts)

    for r, v1r in ((st, st_v1), (tt, tt_v1)):
        print(f"{r['name']}: n={r['n']} dnu={r['days']} s kurzy {r['lines'] * 100:.1f} % | ztrata A "
              f"{r['loss_a']:.4f} B {r['loss_b']:.4f} | zisk {r['gain']:+.4f} [{r['lo']:+.4f}, {r['hi']:+.4f}] | "
              f"{'B NAHRADI A' if r['pass'] else 'zustava A'} | falesny poplach {r['null']:.3f} | sila "
              f"{r['power']:.3f} || proti v1 {v1r['gain']:+.4f} [{v1r['lo']:+.4f}, {v1r['hi']:+.4f}]")
    print(f"R nad B: {rr['gain']:+.4f} [{rr['lo']:+.6f}, {rr['hi']:+.4f}]")

    out = ["# Týmové modely v2, blok B (průběh zápasu z hlavních kurzů) na sezóně 2025-26\n",
           "Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md` (dodatek N-2). Blok B = "
           "zamrazený blok A × násobitel z pravděpodobnosti výhry a čekaného počtu gólů (medián "
           "aspoň 3 amerických knih, snímek v 15:00 UTC herního dne). Koeficienty ze zamrazeného "
           f"`models/team_v2b.json` (odhad jen na {', '.join(vb['trained_on'])}). Sezóna 2025-26 je tu "
           "použita **potřetí** (verze 1, blok A, blok B); čistý test je až potvrzení dopředu. "
           "Vygenerováno skriptem `scripts/report_team_v2b.py`; ručně se needituje.\n",
           "## Verdikt bloku B\n",
           "Zisk = ztráta bloku A − ztráta bloku B; kladný = B je lepší. Bootstrap 95 %, seed 17, "
           "10 000, herní dny. B nahradí A, když je **celý interval nad nulou**.\n",
           "| trh | řádků | s kurzy | ztráta A | ztráta B | zisk | 95% interval | verdikt | B proti verzi 1 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r, v1r, label in ((st, st_v1, "střely týmu (S-T)"), (tt, tt_v1, "tresty týmu (T-T)")):
        out.append(f"| {label} | {r['n']} | {pct(r['lines'])} | {cz(r['loss_a'])} | {cz(r['loss_b'])} | "
                   f"{cz(r['gain'])} | {cz(r['lo'])} až {cz(r['hi'])} | "
                   f"**{'B nahradí A' if r['pass'] else 'zůstává A'}** | {cz(v1r['gain'])} "
                   f"({cz(v1r['lo'])} až {cz(v1r['hi'])}) |")
    out += ["\n## Síla testu a nulový efekt\n",
            f"{SIMS} simulovaných sezón. *Falešný poplach*: pravdou je blok A. *Síla*: pravdou je blok B.\n",
            "| srovnání | falešný poplach | síla |", "|---|---|---|",
            f"| S-T: B proti A | {pct(st['null'])} | {pct(st['power'])} |",
            f"| T-T: B proti A | {pct(tt['null'])} | {pct(tt['power'])} |",
            "\n## Koeficienty (odhad jen na tréninku)\n",
            "| atribut | střely týmu | tresty týmu |", "|---|---|---|"]
    for col, label, scale in (("S0", "úroveň (zápasy s kurzy)", 1.0),
                              ("S1", "pravděpodobnost výhry +10 p. b.", 0.1),
                              ("S2", "čekaný počet gólů zápasu +0,5", 0.5)):
        out.append(f"| {label} | {pct(np.exp(vb['shots']['coef'][col] * scale) - 1, 2)} | "
                   f"{pct(np.exp(vb['penalties']['coef'][col] * scale) - 1, 2)} |")
    out += [f"\nPrůměr čekaných gólů v tréninku {cz(vb['goals_mean_train'], 2)}. Rozptyl k střel "
            f"{cz(kb, 2)} (blok A {cz(ka, 2)}).\n",
            "## Rozhodčí nad blokem B (jen tresty, popis)\n",
            f"Zisk proti bloku B {cz(rr['gain'])} (95% interval {cz(rr['lo'], 5)} až {cz(rr['hi'])}).\n"]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

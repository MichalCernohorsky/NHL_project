#!/usr/bin/env python3
"""Team models v2 on the validation season 2025-26: block A against version
1 (the replacement rule of docs/models_v2_plan.md 5), block R against block
A, with power and null simulations (docs/models_v2_notes.md 4). Writes
docs/team_v2_report.md. Run once, after models/team_v2.json is frozen.

Usage:
    python scripts/report_team_v2.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

V1 = ROOT / "models" / "naive_team.json"
CAL = ROOT / "models" / "naive_team_tt_cal.json"
V2 = ROOT / "models" / "team_v2.json"
OUT = ROOT / "docs" / "team_v2_report.md"
SIMS = 500
PARTS = (("říjen", lambda m: m == 10), ("listopad", lambda m: m == 11),
         ("zbytek", lambda m: ~np.isin(m, (10, 11))))


def cz(x, d=4):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def gain_row(name, diff, day_idx, counts):
    gain, lo, hi = tm.mean_ci(diff, day_idx, counts)
    return {"name": name, "gain": gain, "lo": lo, "hi": hi, "pass": bool(lo > 0)}


def sim_counts(mu_a, k_a, mu_b, k_b, truth, day_idx, counts, rng):
    """Share of simulated seasons in which B would replace A (whole interval
    of loss A - loss B above zero) when the counts come from `truth`."""
    mu_t, k_t = (mu_a, k_a) if truth == "a" else (mu_b, k_b)
    hits = 0
    for _ in range(SIMS):
        y = rng.negative_binomial(k_t, k_t / (k_t + mu_t))
        diff = -tm.nb_logpmf(y, mu_a, k_a) + tm.nb_logpmf(y, mu_b, k_b)
        hits += tm.mean_ci(diff, day_idx, counts)[1] > 0
    return hits / SIMS


def sim_bands(p_a, p_b, truth, day_idx, counts, rng):
    p_t = p_a if truth == "a" else p_b
    p_t = np.minimum.accumulate(p_t, axis=1)              # over 4.5 never likelier than over 3.5
    hits = 0
    for _ in range(SIMS):
        over = t2.draw_bands(p_t, rng)
        diff = t2.bern_loss(p_a, over) - t2.bern_loss(p_b, over)
        hits += tm.mean_ci(diff, day_idx, counts)[1] > 0
    return hits / SIMS


def main():
    const = json.loads(V1.read_text())["families"]
    cal_v1 = t2.as_cal(json.loads(CAL.read_text())["lines"])
    v2 = json.loads(V2.read_text())
    assert v2["builds_on"]["naive_team.json"] == hashlib.sha256(V1.read_bytes()).hexdigest()
    conn = connect(resolve_db_path(load_config()))
    frames = t2.load_frames(conn, [*tm.TRAIN, tm.VALID], const)
    games = set(frames["shots"]["game_id"]) & set(frames["penalties"]["game_id"])
    val = {f: df[(df["season"] == tm.VALID) & df["game_id"].isin(games)].reset_index(drop=True)
           for f, df in frames.items()}
    rng = np.random.default_rng(17)
    out = ["# Týmové modely v2 na sezóně 2025-26\n",
           "Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md`. Koeficienty ze "
           f"zamrazeného `models/team_v2.json` (odhad jen na {', '.join(v2['trained_on'])}), verze 1 "
           "ze zamrazených `models/naive_team.json` a `models/naive_team_tt_cal.json`. Sezóna "
           "2025-26 už ověřovala verzi 1 — tohle je **druhý pohled** na stejná data; jediný čistý "
           "test je potvrzení dopředu na sezóně 2026-27. Vygenerováno skriptem "
           "`scripts/report_team_v2.py`; ručně se needituje.\n"]

    # ------------------------------------------------------------ shots
    s = val["shots"]
    y = s["y"].to_numpy()
    mu1 = tm.predict(s, const["shots"])
    mu2 = t2.predict_a(s, const["shots"], v2["shots"])
    k1, k2 = const["shots"]["k_team"], v2["shots"]["k"]
    day_idx, counts = tm.boot_counts(s["game_date"].to_numpy())
    l1, l2 = -tm.nb_logpmf(y, mu1, k1), -tm.nb_logpmf(y, mu2, k2)
    st = gain_row("S-T", l1 - l2, day_idx, counts)
    st.update(loss1=float(l1.mean()), loss2=float(l2.mean()), n=len(y), days=counts.shape[1],
              null=sim_counts(mu1, k1, mu2, k2, "a", day_idx, counts, rng),
              power=sim_counts(mu1, k1, mu2, k2, "b", day_idx, counts, rng))
    month_s = pd.to_datetime(s["game_date"]).dt.month.to_numpy()
    lines_s = tm.LINES["shots"][0]
    cal_s = [tm.calibration(y, mu, k, lines_s) for mu, k in ((mu1, k1), (mu2, k2))]

    # -------------------------------------------------------- penalties
    p = val["penalties"]
    yp = p["y"].to_numpy()
    lines = list(cal_v1)
    over = (yp[:, None] > np.array(lines)[None, :]).astype(float)
    m1 = tm.predict(p, const["penalties"])
    ma = t2.predict_a(p, const["penalties"], v2["penalties"])
    mr = t2.predict_r(p, const["penalties"], v2["penalties"], v2["referees"]["rho"])
    cal_a, cal_r = t2.as_cal(v2["penalties"]["cal"]), t2.as_cal(v2["referees"]["cal"])
    assert list(cal_a) == lines and list(cal_r) == lines
    p1, pa, pr = t2.tt_probs(m1, cal_v1), t2.tt_probs(ma, cal_a), t2.tt_probs(mr, cal_r)
    days_p = np.tile(p["game_date"].to_numpy(), len(lines))
    didx, dcounts = tm.boot_counts(days_p)
    b1, ba, br = (t2.bern_loss(x, over) for x in (p1, pa, pr))
    tt = gain_row("T-T", b1 - ba, didx, dcounts)
    tt.update(loss1=float(b1.mean()), loss2=float(ba.mean()), n=len(yp), days=dcounts.shape[1],
              null=sim_bands(p1, pa, "a", didx, dcounts, rng),
              power=sim_bands(p1, pa, "b", didx, dcounts, rng))
    rr = gain_row("R", ba - br, didx, dcounts)
    rr.update(loss1=float(ba.mean()), loss2=float(br.mean()),
              null=sim_bands(pa, pr, "a", didx, dcounts, rng),
              power=sim_bands(pa, pr, "b", didx, dcounts, rng))
    rv1 = gain_row("R proti v1", b1 - br, didx, dcounts)
    month_p = pd.to_datetime(p["game_date"]).dt.month.to_numpy()
    cal_p = [tm.cal_calibration(yp, mu, cal) for mu, cal in ((m1, cal_v1), (ma, cal_a), (mr, cal_r))]

    for r in (st, tt):
        print(f"{r['name']}: n={r['n']} dnu={r['days']} | ztrata v1 {r['loss1']:.4f} v2 {r['loss2']:.4f} | "
              f"zisk {r['gain']:+.4f} [{r['lo']:+.4f}, {r['hi']:+.4f}] | "
              f"{'NAHRADI v1' if r['pass'] else 'zustava v1'} | falesny poplach {r['null']:.3f} | "
              f"sila {r['power']:.3f}")
    print(f"R (nad A): zisk {rr['gain']:+.4f} [{rr['lo']:+.4f}, {rr['hi']:+.4f}] | falesny poplach "
          f"{rr['null']:.3f} | sila {rr['power']:.3f} || R proti v1: {rv1['gain']:+.4f} "
          f"[{rv1['lo']:+.4f}, {rv1['hi']:+.4f}]")

    # ----------------------------------------------------------- report
    out += ["## Verdikt bloku A\n",
            "Ztráta = −ln pravděpodobnosti toho, co nastalo (S-T: skutečný počet střel; T-T: více / "
            "méně na 3,5 a 4,5). Zisk = ztráta verze 1 − ztráta verze 2; kladný = verze 2 je lepší. "
            "Bootstrap 95 %, seed 17, 10 000, převzorkují se herní dny. Verze 2 nahradí verzi 1, "
            "když je **celý interval nad nulou**.\n",
            "| trh | řádků | herních dnů | ztráta v1 | ztráta v2 | zisk | 95% interval | verdikt |",
            "|---|---|---|---|---|---|---|---|"]
    for r, label in ((st, "střely týmu (S-T)"), (tt, "tresty týmu (T-T)")):
        out.append(f"| {label} | {r['n']} | {r['days']} | {cz(r['loss1'])} | {cz(r['loss2'])} | "
                   f"{cz(r['gain'])} | {cz(r['lo'])} až {cz(r['hi'])} | "
                   f"**{'v2 nahradí v1' if r['pass'] else 'zůstává v1'}** |")
    out += ["\n## Síla testu a nulový efekt\n",
            f"{SIMS} simulovaných sezón na stejných zápasech a se stejným bootstrapem. *Falešný "
            "poplach*: pravdou je verze 1 — jak často by test přesto řekl „v2 nahradí“. *Síla*: "
            "pravdou je verze 2 — jak často by to test poznal.\n",
            "| srovnání | falešný poplach | síla |", "|---|---|---|",
            f"| S-T: v2 proti v1 | {pct(st['null'])} | {pct(st['power'])} |",
            f"| T-T: v2 proti v1 | {pct(tt['null'])} | {pct(tt['power'])} |",
            f"| T-T: rozhodčí proti bloku A | {pct(rr['null'])} | {pct(rr['power'])} |",
            "\n## Rozhodčí (blok R, jen tresty)\n",
            "V historii jsou rozhodčí známi vždy; tohle říká, o kolik by jejich znalost zlepšila "
            "předpověď trestů — o nasazení nerozhoduje.\n",
            "| srovnání | zisk | 95% interval | celý nad nulou |", "|---|---|---|---|",
            f"| blok A + rozhodčí proti bloku A | {cz(rr['gain'])} | {cz(rr['lo'])} až {cz(rr['hi'])} | "
            f"{'ano' if rr['pass'] else 'ne'} |",
            f"| blok A + rozhodčí proti verzi 1 | {cz(rv1['gain'])} | {cz(rv1['lo'])} až {cz(rv1['hi'])} | "
            f"{'ano' if rv1['pass'] else 'ne'} |",
            "\n## Koeficienty (odhad jen na tréninku)\n",
            "Násobitel = exp(koeficient): o kolik procent atribut posune očekávaný počet.\n",
            "| atribut | střely týmu | tresty týmu |", "|---|---|---|"]
    names = {"c0": "úroveň (všechny zápasy)", "D": "jedna očekávaná přesilovka navíc", "F1": "1.–10. zápas sezóny",
             "F2": "11.–20. zápas sezóny", "B_team": "tým hraje druhý den po sobě",
             "B_opp": "soupeř hraje druhý den po sobě"}
    for col, label in names.items():
        cs, cp = v2["shots"]["coef"][col], v2["penalties"]["coef"][col]
        out.append(f"| {label} | {pct(np.exp(cs) - 1, 2)} | {pct(np.exp(cp) - 1, 2)} |")
    sd_r = float(frames["penalties"].loc[frames["penalties"]["season"] == tm.VALID, "R"].std())
    out += [f"| váha pokusů o střelu ve formě (α) | {cz(v2['shots']['alpha'], 1)} | — |",
            f"| rozhodčí: +1 trest na zápas nad ligou (po stažení) | — | "
            f"{pct(np.exp(v2['referees']['rho']) - 1, 2)} |",
            f"\nRozptyl k: střely {cz(v2['shots']['k'], 2)} (verze 1: {cz(k1, 2)}). Směrodatná odchylka "
            f"R mezi zápasy 2025-26: {cz(sd_r, 3)} trestu.\n",
            "## Po částech sezóny (popis)\n",
            "| část | řádků | střely: skutečnost | v1 | v2 | „více než 3,5“ trestu: skutečnost | v1 | v2 |",
            "|---|---|---|---|---|---|---|---|"]
    for label, pick in PARTS:
        ms, mp = pick(month_s), pick(month_p)
        out.append(f"| {label} | {int(ms.sum())} | {cz(y[ms].mean(), 2)} | {cz(mu1[ms].mean(), 2)} | "
                   f"{cz(mu2[ms].mean(), 2)} | {pct(over[mp, 0].mean())} | {pct(p1[mp, 0].mean())} | "
                   f"{pct(pa[mp, 0].mean())} |")
    out += ["\n## Kalibrace v pěti pásmech (popis)\n",
            f"Střely týmu, lajny {lines_s[0]}–{lines_s[-1]} dohromady:\n",
            "| pásmo | v1 předpověď | v1 skutečnost | v2 předpověď | v2 skutečnost |", "|---|---|---|---|---|"]
    for i in range(5):
        a, b = cal_s[0].iloc[i], cal_s[1].iloc[i]
        out.append(f"| {i + 1} | {pct(a['predicted'])} | {pct(a['observed'])} | {pct(b['predicted'])} | "
                   f"{pct(b['observed'])} |")
    out += ["\nTresty týmu, lajny 3,5 a 4,5 dohromady:\n",
            "| pásmo | v1 předpověď | v1 skutečnost | v2 předpověď | v2 skutečnost | s rozhodčími předpověď "
            "| s rozhodčími skutečnost |", "|---|---|---|---|---|---|---|"]
    for i in range(5):
        a, b, c = (t.iloc[i] for t in cal_p)
        out.append(f"| {i + 1} | {pct(a['predicted'])} | {pct(a['observed'])} | {pct(b['predicted'])} | "
                   f"{pct(b['observed'])} | {pct(c['predicted'])} | {pct(c['observed'])} |")
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

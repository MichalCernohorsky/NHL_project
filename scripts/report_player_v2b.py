#!/usr/bin/env python3
"""Block B of the player shots model v2 on the purchased closing lines of
the 2025-26 sample (330 games): the phase 0 criteria next to version 1 and
block A, and the plan's final word on the player model
(docs/models_v2_plan.md 5). Writes docs/player_v2b_report.md. Run once,
after models/player_v2b.json is frozen.

Usage:
    python scripts/report_player_v2b.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from report_player_v2 import cz, evaluate, pct
from nhl_tool import main_lines as ml
from nhl_tool import naive_sog as ns
from nhl_tool import phase0, tips
from nhl_tool import player_v2 as pv
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

VA = ROOT / "models" / "player_v2.json"
VB = ROOT / "models" / "player_v2b.json"
TEAM = ROOT / "models" / "naive_team.json"
OUT = ROOT / "docs" / "player_v2b_report.md"


def main():
    cfg = load_config()
    season = cfg["odds"]["backfill_season"]
    margin = cfg["odds"]["tipsport_margin"]
    v1, va, vb = tips.load_model(), json.loads(VA.read_text()), json.loads(VB.read_text())
    assert vb["builds_on"]["player_v2.json"] == hashlib.sha256(VA.read_bytes()).hexdigest()
    const_pen = json.loads(TEAM.read_text())["families"]["penalties"]
    conn = connect(resolve_db_path(cfg))

    lines = phase0.load_closing(conn, season)
    sample = set(lines["game_id"])
    sample_days = int(lines["game_date"].nunique())
    players_per_game = float(lines.groupby("game_id")["player_name_raw"].nunique().mean())
    matched = lines[lines["player_id"].notna()].copy()
    matched["player_id"] = matched["player_id"].astype(int)
    wide = phase0.both_sides(matched)
    cons = phase0.consensus(wide)

    seasons = [ns.prev_season(season), season]
    f1 = ns.features(ns.load_skater_games(conn, seasons), tips.constants(v1))
    f1 = f1[(f1["season"] == season) & f1["game_id"].isin(sample)]
    pens = tm.load_team_games(conn, [*tm.TRAIN, season], "penalties")
    ctx = pv.context(tm.add_asof(pens), t2.load_b2b(conn), const_pen)
    fa = pv.with_mu(pv.features(pv.load_skater_games(conn, seasons), pens, ctx, va), va)
    fa = fa[(fa["season"] == season) & fa["game_id"].isin(sample)].reset_index(drop=True)
    fb = t2.add_script(fa, t2.team_script(conn, ml.game_script(conn), vb["goals_mean_train"]))
    fb["mu_60"] = t2.predict_b(fb, fa["mu_60"].to_numpy(), vb)
    fb["mu_full"] = fb["mu_60"] * (1 + fb["group"].map(vb["ot_ratio"]))
    with_lines = float(fb.groupby("game_id")["S0"].first().mean())

    res = {"v1": evaluate(wide, cons, f1, v1, margin, sample_days, players_per_game),
           "A": evaluate(wide, cons, fa, va, margin, sample_days, players_per_game),
           "B": evaluate(wide, cons, fb, vb, margin, sample_days, players_per_game)}
    key = ["game_id", "player_id", "line"]
    both = res["A"]["rows"][key + ["game_date", "p_model", "over"]].merge(
        res["B"]["rows"][key + ["p_model"]], on=key, suffixes=("_a", "_b"))
    gain = (both["p_model_a"] - both["over"]) ** 2 - (both["p_model_b"] - both["over"]) ** 2
    bg, blo, bhi = tm.mean_ci(gain.to_numpy(), *tm.boot_counts(both["game_date"].to_numpy()))

    for name, r in res.items():
        a, b, v = r["a"], r["b"], r["v"]
        print(f"{name}: K4a n={a['n']} Brier {a['brier_model']:.4f} vs trh {a['brier_market']:.4f} "
              f"rozdil {a['gap']:+.4f} [{a['lo']:+.4f}, {a['hi']:+.4f}] {'ANO' if a['pass'] else 'ne'} | "
              f"K4b sazek {b['n']} vyhry {b['hit'] * 100:.1f} % (model {b['p_model'] * 100:.1f} %, trh "
              f"{b['p_market'] * 100:.1f} %) ROI {b['roi'] * 100:+.1f} % [{b['lo'] * 100:+.1f}, "
              f"{b['hi'] * 100:+.1f}] US {b['roi_us'] * 100:+.1f} % {'ANO' if b['pass'] else 'ne'} | "
              f"K5 {v['per_day_tipsport']:.2f} | nula {r['null']['pass_rate'] * 100:.1f} % | "
              f"sila {r['power']['pass_rate'] * 100:.1f} %")
    print(f"zapasu vzorku s hlavnimi kurzy: {with_lines * 100:.1f} % | Brier A - B na {len(both)} radcich: "
          f"{bg:+.5f} [{blo:+.5f}, {bhi:+.5f}]")
    any_pass = res["A"]["b"]["pass"] or res["B"]["b"]["pass"]

    yes = lambda ok: "splněno" if ok else "nesplněno"  # noqa: E731
    out = ["# Hráčský model v2, blok B (průběh zápasu) na vzorku 330 zápasů 2025-26\n",
           "Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md` (dodatek N-2). Blok B = "
           "zamrazený blok A × násobitel z pravděpodobnosti výhry týmu a čekaného počtu gólů (hlavní "
           f"kurzy, snímek v 15:00 UTC; {pct(with_lines)} zápasů vzorku je má). Stejné closingové kurzy, "
           "kód a kritéria jako fáze 0. Je to **třetí model na stejných kurzech**. Vygenerováno "
           "skriptem `scripts/report_player_v2b.py`; ručně se needituje.\n",
           "## Verdikt: " + ("některý blok splnil K4b — následovalo by potvrzení na novém vzorku"
                             if any_pass else "žádný blok K4b nesplnil — hráčský model podle plánu končí") + "\n",
           "| | verze 1 | blok A | blok B |", "|---|---|---|---|"]
    row = lambda label, fn: out.append(f"| {label} | " + " | ".join(fn(res[n]) for n in res) + " |")  # noqa: E731
    row("K4a Brier modelu − Brier trhu (≤ 0,010)",
        lambda r: f"{cz(r['a']['gap'], 4)} ({cz(r['a']['lo'], 4)} až {cz(r['a']['hi'], 4)}) — {yes(r['a']['pass'])}")
    row("**K4b ROI za simulovaný kurz Tipsportu (> 0)**",
        lambda r: f"**{pct(r['b']['roi'])}** ({pct(r['b']['lo'])} až {pct(r['b']['hi'])}) — {yes(r['b']['pass'])}")
    row("K5 sázek na herní den (≥ 3)", lambda r: f"{cz(r['v']['per_day_tipsport'])} — {yes(r['v']['pass'])}")
    row("sázek", lambda r: str(r["b"]["n"]))
    row("výhry", lambda r: pct(r["b"]["hit"]))
    row("model čekal", lambda r: pct(r["b"]["p_model"]))
    row("trh čekal", lambda r: pct(r["b"]["p_market"]))
    row("vedlejší: ROI za nejlepší americký kurz",
        lambda r: f"{pct(r['b']['roi_us'])} ({pct(r['b']['us_lo'])} až {pct(r['b']['us_hi'])})")
    row("Brier modelu (trh " + cz(res["B"]["a"]["brier_market"], 4) + ")", lambda r: cz(r["a"]["brier_model"], 4))
    row("simulace: pravdou je trh — K4b by prošlo", lambda r: pct(r["null"]["pass_rate"]))
    row("simulace: pravdou je model — K4b by prošlo", lambda r: pct(r["power"]["pass_rate"]))
    out += ["\nIntervaly jsou 95% bootstrap (seed 17, 10 000, herní dny). „Skoro“ znamená ne.\n",
            f"Zlepšení Brier A − B na {len(both)} společných řádcích: {cz(bg, 5)} (95% interval "
            f"{cz(blo, 5)} až {cz(bhi, 5)}).\n",
            "## Koeficienty bloku B (odhad jen na tréninku)\n", "| | |", "|---|---|",
            f"| úroveň (zápasy s kurzy) | {pct(np.exp(vb['coef']['S0']) - 1, 2)} |",
            f"| pravděpodobnost výhry týmu +10 p. b. | {pct(np.exp(vb['coef']['S1'] * 0.1) - 1, 2)} |",
            f"| čekaný počet gólů zápasu +0,5 | {pct(np.exp(vb['coef']['S2'] * 0.5) - 1, 2)} |",
            f"| rozptyl k | {cz(vb['nb_k'], 2)} (blok A {cz(va['nb_k'], 2)}) |",
            "\n## Co se nevyhodnocovalo\n",
            "Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; "
            "žádná jiná kombinace atributů než bloky plánu. Zbylé zápasy sezóny 2025-26 se neotvíraly."]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

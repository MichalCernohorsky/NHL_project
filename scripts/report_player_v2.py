#!/usr/bin/env python3
"""Player shots model v2 on the purchased closing lines of the 2025-26
sample (330 games): the phase 0 criteria K4a / K4b / K5 with the same code
as the phase 0 verdict, next to version 1 (docs/models_v2_plan.md 5;
docs/models_v2_notes.md 6). Writes docs/player_v2_report.md. Run once,
after models/player_v2.json is frozen.

Only the games of the purchased sample are evaluated; the other games of
2025-26 stay unopened for a possible confirmation purchase.

Usage:
    python scripts/report_player_v2.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns
from nhl_tool import phase0, tips
from nhl_tool import player_v2 as pv
from nhl_tool import team_model as tm
from nhl_tool import team_v2 as t2
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect
from nhl_tool.stats import SEED

V2 = ROOT / "models" / "player_v2.json"
TEAM = ROOT / "models" / "naive_team.json"
OUT = ROOT / "docs" / "player_v2_report.md"
TIPSPORT_PLAYERS = 6.0
BLOCK = "A"


def cz(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def model_sim(bets, sims: int = phase0.NULL_SIMS, seed: int = SEED) -> dict:
    """Power of K4b: every bet wins with the MODEL's probability of its side."""
    if bets.empty:
        return {"pass_rate": 0.0, "roi_mean": float("nan")}
    rng = np.random.default_rng(seed)
    wins = rng.random((sims, len(bets))) < bets["p_model"].to_numpy()
    roi = np.where(wins, bets["price_tipsport"].to_numpy() - 1.0, -1.0).mean(axis=1)
    return {"pass_rate": float((roi > 0).mean()), "roi_mean": float(roi.mean())}


def evaluate(wide, cons, feats, model, margin, sample_days, players_per_game) -> dict:
    rows = phase0.brier_rows(cons, feats, model["nb_k"])
    bets = phase0.select_bets(wide, cons, feats, model, margin)
    b = phase0.k4b(bets, sample_days)
    return {"rows": rows, "bets": bets, "a": phase0.k4a(rows), "b": b,
            "v": phase0.k5(b["per_day"], players_per_game, TIPSPORT_PLAYERS),
            "null": phase0.null_sim(bets), "power": model_sim(bets)}


def main():
    cfg = load_config()
    season = cfg["odds"]["backfill_season"]
    margin = cfg["odds"]["tipsport_margin"]
    v1 = tips.load_model()
    v2 = json.loads(V2.read_text())
    assert v2["builds_on"]["naive_team.json"] == hashlib.sha256(TEAM.read_bytes()).hexdigest()
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
    f2 = pv.with_mu(pv.features(pv.load_skater_games(conn, seasons), pens, ctx, v2), v2)
    f2 = f2[(f2["season"] == season) & f2["game_id"].isin(sample)]

    r1 = evaluate(wide, cons, f1, v1, margin, sample_days, players_per_game)
    r2 = evaluate(wide, cons, f2, v2, margin, sample_days, players_per_game)
    key = ["game_id", "player_id", "line"]
    both = r1["rows"][key + ["game_date", "p_model", "over"]].merge(
        r2["rows"][key + ["p_model"]], on=key, suffixes=("_v1", "_v2"))
    gain = (both["p_model_v1"] - both["over"]) ** 2 - (both["p_model_v2"] - both["over"]) ** 2
    day_idx, counts = tm.boot_counts(both["game_date"].to_numpy())
    bg, blo, bhi = tm.mean_ci(gain.to_numpy(), day_idx, counts)

    for name, r in (("v1", r1), ("v2", r2)):
        a, b, v = r["a"], r["b"], r["v"]
        print(f"{name}: K4a n={a['n']} Brier {a['brier_model']:.4f} vs trh {a['brier_market']:.4f} "
              f"rozdil {a['gap']:+.4f} [{a['lo']:+.4f}, {a['hi']:+.4f}] {'ANO' if a['pass'] else 'ne'} | "
              f"K4b sazek {b['n']} vyhry {b['hit'] * 100:.1f} % (model {b['p_model'] * 100:.1f} %, trh "
              f"{b['p_market'] * 100:.1f} %) ROI {b['roi'] * 100:+.1f} % [{b['lo'] * 100:+.1f}, "
              f"{b['hi'] * 100:+.1f}] US {b['roi_us'] * 100:+.1f} % {'ANO' if b['pass'] else 'ne'} | "
              f"K5 {v['per_day_tipsport']:.2f} | nula {r['null']['pass_rate'] * 100:.1f} % | "
              f"sila {r['power']['pass_rate'] * 100:.1f} %")
    print(f"Brier v1 - v2 na {len(both)} spolecnych radcich: {bg:+.5f} [{blo:+.5f}, {bhi:+.5f}]")
    a, b, v = r2["a"], r2["b"], r2["v"]
    passed = a["pass"] and b["pass"] and v["pass"]

    yes = lambda ok: "**splněno**" if ok else "**nesplněno**"  # noqa: E731
    out = [f"# Hráčský model v2 (blok {BLOCK}) na vzorku 330 zápasů 2025-26\n",
           "Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md`. Zamrazený model "
           f"`models/player_v2.json` (odhad jen na {', '.join(v2['trained_on'])}); stejné closingové "
           "kurzy, stejný kód a stejná kritéria jako verdikt fáze 0 (`docs/phase0_report.md`). Je to "
           "**druhý model na stejných kurzech** — případný úspěch tu není důkaz a musel by se potvrdit "
           "na novém vzorku. Zbylé zápasy sezóny 2025-26 se nevyhodnocovaly. Vygenerováno skriptem "
           "`scripts/report_player_v2.py`; ručně se needituje.\n",
           f"## Verdikt bloku {BLOCK}: " + ("kritéria fáze 0 splněna — následovalo by potvrzení na "
                                             "novém vzorku" if passed else "kritéria fáze 0 nesplněna") + "\n",
           "| kritérium | práh | verze 1 | verze 2 | verze 2: splněno? |", "|---|---|---|---|---|"]
    a1, b1, v1r = r1["a"], r1["b"], r1["v"]
    out += [f"| K4a Brier modelu − Brier trhu | ≤ {cz(phase0.K4A_MAX_GAP, 3)} | {cz(a1['gap'], 4)} "
            f"({cz(a1['lo'], 4)} až {cz(a1['hi'], 4)}) | {cz(a['gap'], 4)} ({cz(a['lo'], 4)} až "
            f"{cz(a['hi'], 4)}) | {yes(a['pass'])} |",
            f"| K4b ROI za simulovaný kurz Tipsportu | > 0 | {pct(b1['roi'])} ({pct(b1['lo'])} až "
            f"{pct(b1['hi'])}) | {pct(b['roi'])} ({pct(b['lo'])} až {pct(b['hi'])}) | {yes(b['pass'])} |",
            f"| K5 sázek na herní den po přepočtu na 6 hráčů | ≥ {cz(phase0.K5_MIN_BETS, 0)} | "
            f"{cz(v1r['per_day_tipsport'])} | {cz(v['per_day_tipsport'])} | {yes(v['pass'])} |",
            "\nIntervaly jsou 95% bootstrap (seed 17, 10 000, převzorkují se herní dny). „Skoro“ "
            "znamená ne.\n",
            "## Sázky filtru (hrana ≥ 3 p. b., kurz Tipsportu simulovaný s m = "
            f"{cz(margin, 4)}, 60 minut)\n",
            "| | verze 1 | verze 2 |", "|---|---|---|",
            f"| sázek | {b1['n']} | {b['n']} |",
            f"| výhry | {pct(b1['hit'])} | {pct(b['hit'])} |",
            f"| model čekal | {pct(b1['p_model'])} | {pct(b['p_model'])} |",
            f"| trh čekal | {pct(b1['p_market'])} | {pct(b['p_market'])} |",
            f"| průměrný simulovaný kurz | {cz(b1['avg_price'], 3)} | {cz(b['avg_price'], 3)} |",
            f"| **ROI za kurz Tipsportu** | {pct(b1['roi'])} ({pct(b1['lo'])} až {pct(b1['hi'])}) | "
            f"**{pct(b['roi'])}** ({pct(b['lo'])} až {pct(b['hi'])}) |",
            f"| vedlejší: ROI za nejlepší americký kurz | {pct(b1['roi_us'])} ({pct(b1['us_lo'])} až "
            f"{pct(b1['us_hi'])}) | {pct(b['roi_us'])} ({pct(b['us_lo'])} až {pct(b['us_hi'])}) |",
            "\n## Přesnost předpovědi (Brier, hlavní lajna, celý zápas)\n",
            "| | Brier |", "|---|---|",
            f"| trh | {cz(a['brier_market'], 4)} |", f"| verze 1 | {cz(a1['brier_model'], 4)} |",
            f"| verze 2 | {cz(a['brier_model'], 4)} |",
            f"| zlepšení v1 − v2 na {len(both)} společných řádcích | {cz(bg, 5)} (95% interval "
            f"{cz(blo, 5)} až {cz(bhi, 5)}) |",
            "\n## Síla testu a nulový efekt\n",
            f"{phase0.NULL_SIMS} simulací na vybraných sázkách verze 2. *Pravdou je trh* (výsledek se "
            f"losuje z pravděpodobnosti trhu): K4b by prošlo v {pct(r2['null']['pass_rate'])} simulací, "
            f"průměrné ROI {pct(r2['null']['roi_mean'])}. *Pravdou je model* (losuje se "
            f"z pravděpodobnosti modelu): prošlo by v {pct(r2['power']['pass_rate'])}, průměrné ROI "
            f"{pct(r2['power']['roi_mean'])} — tolik by test ukázal, kdyby měl model pravdu.\n",
            "## Koeficienty (odhad jen na tréninku)\n",
            "| | |", "|---|---|",
            f"| váha pokusů o střelu ve střelbě hráče (α) | {cz(v2['alpha'], 1)} |",
            f"| mocnina očekávaných přesilovek (π) | {cz(v2['pi'], 2)} |",
            f"| úroveň (všechny zápasy) | {pct(np.exp(v2['coef']['c0']) - 1, 2)} |",
            f"| tým hraje druhý den po sobě | {pct(np.exp(v2['coef']['B_team']) - 1, 2)} |",
            f"| soupeř hraje druhý den po sobě | {pct(np.exp(v2['coef']['B_opp']) - 1, 2)} |",
            f"| rozptyl k | {cz(v2['nb_k'], 2)} (verze 1: {cz(v1['nb_k'], 2)}) |",
            "\n## Co se nevyhodnocovalo\n",
            "Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; "
            "žádná jiná kombinace atributů než blok plánu."]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

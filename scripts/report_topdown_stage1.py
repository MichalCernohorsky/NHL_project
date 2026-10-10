#!/usr/bin/env python3
"""Stage 1 of the market-as-model plan (docs/topdown_plan.md section 3,
amendment TD-1): is the consensus of the other books closer to the truth
than a book that deviates from it? Leave-one-book-out on the purchased
closing lines of the 2025-26 sample. Writes docs/topdown_stage1_report.md.

Run once. Criterion P1: the point estimate of ROI is above zero.

Usage:
    python scripts/report_topdown_stage1.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns
from nhl_tool import phase0, tips, topdown
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

OUT = ROOT / "docs" / "topdown_stage1_report.md"


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def main():
    cfg = load_config()
    season = cfg["odds"]["backfill_season"]
    k = tips.load_model()["nb_k"]
    conn = connect(resolve_db_path(cfg))
    lines = phase0.load_closing(conn, season)
    lines = lines[lines["player_id"].notna()].copy()
    lines["player_id"] = lines["player_id"].astype(int)
    wide = phase0.both_sides(lines)
    results = ns.load_skater_games(conn, [season])[["game_id", "player_id", "sog", "toi_s"]]
    cand = topdown.loo_candidates(wide)
    bets = topdown.select_bets(cand, results)
    s = topdown.summary(bets)
    sim = topdown.simulate(bets, wide, k)
    books = int(wide["bookmaker"].nunique())
    print(f"knih {books} | radku (zapas, hrac, lajna, kniha) s >= 3 dalsimi knihami: {len(cand)} | "
          f"sazek {s['n']} ({pct(s['n'] / max(len(cand), 1))} radku) na {s['players']} hracich v {s['days']} dnech")
    print(f"ROI {s['roi'] * 100:+.2f} % [{s['lo'] * 100:+.2f}, {s['hi'] * 100:+.2f}] | vyhry {s['hit'] * 100:.1f} % "
          f"(pravidlo cekalo {s['p_fair'] * 100:.1f} %) | prumerny kurz {s['avg_price']:.3f} | "
          f"ocekavany zisk podle pravidla {s['ev_rule'] * 100:+.1f} % | vice {s['over_share'] * 100:.0f} %")
    print(f"simulace 'princip plati': prumer {sim['holds_mean'] * 100:+.1f} % (5-95 %: {sim['holds_p05'] * 100:+.1f} az "
          f"{sim['holds_p95'] * 100:+.1f}) | 'nulovy efekt': prumer {sim['null_mean'] * 100:+.1f} %, "
          f"ROI > 0 v {sim['null_positive'] * 100:.1f} % simulaci")
    print("P1:", "SPLNENO" if s["pass"] else "NESPLNENO", "| podporeno (cely interval nad nulou):",
          "ano" if s["supported"] else "ne")

    verdict = ("**splněno**" if s["pass"] else "**nesplněno**")
    avg_price = f"{s['avg_price']:.3f}".replace(".", ",")
    out = [
        "# Trh jako model — etapa 1: kontrola principu na koupených kurzech\n",
        "Plán `docs/topdown_plan.md` (schválen a zamrazen 10. 10. 2026), sekce 3, dodatek TD-1. "
        f"Closingové kurzy amerických knih, vzorek 330 zápasů sezóny {season}. Vygenerováno skriptem "
        "`scripts/report_topdown_stage1.py`, který byl commitnut před výpočtem; ručně se needituje.\n",
        "**Otázka:** když jedna kniha platí o 3 % a víc nad férový kurz podle ostatních knih, "
        "vyplatí se u ní vsadit? Jinak řečeno: má pravdu konsensus, nebo kniha, která se odchýlila?\n",
        f"## Kritérium P1 (bodový odhad ROI > 0): {verdict}\n",
        "| | |", "|---|---|",
        f"| knih ve vzorku | {books} |",
        f"| řádků (zápas, hráč, lajna, kniha) s ≥ 3 dalšími knihami | {len(cand)} |",
        f"| sázek podle pravidla | {s['n']} na {s['players']} dvojicích (zápas, hráč), {s['days']} herních dnů |",
        f"| očekávaný zisk podle pravidla | {pct(s['ev_rule'])} |",
        f"| **skutečné ROI** | **{pct(s['roi'], 2)}** (95% interval {pct(s['lo'], 2)} až {pct(s['hi'], 2)}; "
        "bootstrap, seed 17, 10 000, herní dny) |",
        f"| výhry | {pct(s['hit'])} (pravidlo čekalo {pct(s['p_fair'])}) |",
        f"| průměrný kurz | {avg_price} |",
        f"| podíl „více“ | {pct(s['over_share'], 0)} |",
        f"| celý interval nad nulou („podpořeno“) | {'ano' if s['supported'] else 'ne'} |",
        "\n## Simulace (dodatek TD-1, po 2 000)\n",
        "| scénář | průměrné ROI | rozpětí 5–95 % | podíl simulací s ROI > 0 |", "|---|---|---|---|",
        f"| princip platí beze zbytku (pravda = konsensus všech knih) | {pct(sim['holds_mean'])} | "
        f"{pct(sim['holds_p05'])} až {pct(sim['holds_p95'])} | {pct(sim['holds_positive'])} |",
        f"| nulový efekt (pravdu má kniha, u které se sází) | {pct(sim['null_mean'])} | "
        f"do {pct(sim['null_p95'])} (95. percentil) | {pct(sim['null_positive'])} |",
        "\nSkutečné ROI se čte proti oběma: čím blíž k prvnímu řádku, tím víc má pravdu konsensus; "
        "čím blíž k druhému, tím víc kniha, která se odchýlila.\n",
        "## Co to říká a co ne\n",
        "- Vypořádání podle pravidel amerických knih (celý zápas), hráč bez času na ledě = void, "
        "nejvýš jedna sázka na (zápas, hráč, kniha).",
        "- Je to test principu mezi americkými knihami navzájem, na closingu. O Tipsportu neříká "
        "nic jistého: jeho odchylky mohou mít jinou příčinu. To měří až etapa 2 na kurzech z tiketů.",
        "- Žádné řezy podle knihy, hráče, lajny ani strany (plán, sekce 6).",
    ]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Phase 0 verdict for player shots on goal: the frozen naive model on the
purchased closing lines of the 2025-26 sample (docs/market_discovery_plan.md
sections 3 and 6, amendments D1-D3, D8). Writes docs/phase0_report.md.

Run once, after the stage A purchase. Nothing is tuned by it; "almost
passed" means did not pass (plan 6.6).

Usage:
    python scripts/report_phase0.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import naive_sog as ns
from nhl_tool import phase0, tips
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

OUT = ROOT / "docs" / "phase0_report.md"
TIPSPORT_PLAYERS = 6.0          # plan D2, fixed by D8 on 10. 10. 2026


def cz(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def main():
    cfg = load_config()
    season = cfg["odds"]["backfill_season"]
    margin = cfg["odds"]["tipsport_margin"]
    model = tips.load_model()
    k = model["nb_k"]
    conn = connect(resolve_db_path(cfg))

    lines = phase0.load_closing(conn, season)
    games = int(lines["game_id"].nunique())
    sample_days = int(lines["game_date"].nunique())
    players_per_game = float(lines.groupby("game_id")["player_name_raw"].nunique().mean())
    unmatched = int(lines.loc[lines["player_id"].isna(), "player_name_raw"].nunique())
    whole = int(((lines["line"] * 2) % 2 == 0).sum())

    hist = ns.load_skater_games(conn, [ns.prev_season(season), season])
    feats = ns.features(hist, tips.constants(model))
    feats = feats[feats["season"] == season]

    matched = lines[lines["player_id"].notna()].copy()
    matched["player_id"] = matched["player_id"].astype(int)
    wide = phase0.both_sides(matched)
    cons = phase0.consensus(wide)

    rows = phase0.brier_rows(cons, feats, k)
    a = phase0.k4a(rows)
    bets = phase0.select_bets(wide, cons, feats, model, margin)
    b = phase0.k4b(bets, sample_days)
    v = phase0.k5(b["per_day"], players_per_game, TIPSPORT_PLAYERS)
    null = phase0.null_sim(bets)
    k3 = games >= phase0.K3_MIN_GAMES
    passed = k3 and a["pass"] and b["pass"] and v["pass"]

    print(f"K3 zapasu s lajnou {games} (dnu {sample_days}) | hracu na zapas {players_per_game:.1f} | "
          f"nesparovanych jmen {unmatched} | kotaci na celociselne lajne {whole}")
    print(f"K4a radku {a['n']} | Brier model {a['brier_model']:.4f} trh {a['brier_market']:.4f} | "
          f"rozdil {a['gap']:+.4f} [{a['lo']:+.4f}, {a['hi']:+.4f}] | {'ANO' if a['pass'] else 'ne'}")
    if b["n"]:
        print(f"K4b sazek {b['n']} ({b['per_day']:.1f} na den) | vyhry {b['hit'] * 100:.1f} % (model cekal "
              f"{b['p_model'] * 100:.1f} %, trh {b['p_market'] * 100:.1f} %) | kurz {b['avg_price']:.3f} | "
              f"ROI {b['roi'] * 100:+.1f} % [{b['lo'] * 100:+.1f}, {b['hi'] * 100:+.1f}] | "
              f"US ROI {b['roi_us'] * 100:+.1f} % [{b['us_lo'] * 100:+.1f}, {b['us_hi'] * 100:+.1f}] | "
              f"{'ANO' if b['pass'] else 'ne'}")
    print(f"K5 {v['per_day_tipsport']:.2f} na den po prepoctu | {'ANO' if v['pass'] else 'ne'} | "
          f"nulova simulace: proslo {null['pass_rate'] * 100:.1f} %")
    print("VERDIKT:", "POSTUPUJE" if passed else "NEPOSTUPUJE")

    yes = lambda ok: "**splněno**" if ok else "**nesplněno**"  # noqa: E731
    out = [
        "# Fáze 0 — verdikt pro střely hráče na branku\n",
        "Plán `docs/market_discovery_plan.md` (schválen a zamrazen 10. 10. 2026, před nákupem). "
        f"Zamrazený model `{model['model']}` (odhad jen na {', '.join(model['trained_on'])}), closingové "
        f"kurzy amerických knih pro vzorek sezóny {season} koupené 10. 10. 2026. Vygenerováno skriptem "
        "`scripts/report_phase0.py`, který byl commitnut před prvním pohledem na koupená data; "
        "ručně se needituje.\n",
        f"## Verdikt: trh {'POSTUPUJE do fáze 1' if passed else 'NEPOSTUPUJE'}\n",
        "| kritérium | práh | výsledek | |",
        "|---|---|---|---|",
        "| K1 Tipsport trh vypisuje | ≥ 75 % zápasů, ≥ 4 hráči, do 18:00 | 22 zápasů z 22, 6 hráčů "
        "(dodatek D8) | **splněno** |",
        "| K2 data zdarma a denně | NHL API | 3 sezóny, počty za 60 minut, 0 chyb | **splněno** |",
        f"| K3 historické kurzy | ≥ {phase0.K3_MIN_GAMES} zápasů s closingovou lajnou | {games} zápasů "
        f"({sample_days} herních dnů) | {yes(k3)} |",
        f"| K4a model není beznadějně za trhem | Brier modelu − Brier trhu ≤ {cz(phase0.K4A_MAX_GAP, 3)} | "
        f"{cz(a['gap'], 4)} (95% interval {cz(a['lo'], 4)} až {cz(a['hi'], 4)}) | {yes(a['pass'])} |",
        f"| K4b filtr není celý pod nulou | ROI za simulovaný kurz Tipsportu > 0 | "
        + (f"{pct(b['roi'])} (95% interval {pct(b['lo'])} až {pct(b['hi'])})" if b["n"] else "žádná sázka")
        + f" | {yes(b['pass'])} |",
        f"| K5 objem | ≥ {cz(phase0.K5_MIN_BETS, 0)} sázky na herní den po přepočtu na 6 hráčů | "
        f"{cz(v['per_day_tipsport'])} | {yes(v['pass'])} |",
        "",
        "Trh postupuje jen při splnění všech kritérií. „Skoro prošel“ znamená neprošel; druhé kolo "
        "s jinými parametry se nekoná (plán 6.6).\n",
        "## K4a — Brier proti trhu (celý zápas, hlavní lajna)\n",
        f"{a['n']} řádků (zápas, hráč) z {a['days']} herních dnů; hráči s ≥ 10 zápasy v sezóně, "
        "kteří nastoupili. Americký trh počítá prodloužení, proto se tu model i výsledek berou "
        "za celý zápas.\n",
        "| | Brier |", "|---|---|",
        f"| model | {cz(a['brier_model'], 4)} |", f"| trh | {cz(a['brier_market'], 4)} |",
        f"| rozdíl (model − trh) | {cz(a['gap'], 4)} (95% interval {cz(a['lo'], 4)} až {cz(a['hi'], 4)}; "
        "bootstrap, seed 17, 10 000, herní dny) |",
        "\nKalibrace v decilech (jen diagnostika, o postupu nerozhoduje):\n",
        "| decil | model: předpověď | model: skutečnost | trh: předpověď | trh: skutečnost |",
        "|---|---|---|---|---|",
    ]
    cm, ck = phase0.calibration(rows, "p_model"), phase0.calibration(rows, "p_market")
    for i in range(len(cm)):
        out.append(f"| {i + 1} | {pct(cm['predicted'][i])} | {pct(cm['observed'][i])} | "
                   f"{pct(ck['predicted'][i])} | {pct(ck['observed'][i])} |")
    out += ["\n## K4b — filtr hrany ≥ 3 p.b., výplata za simulovaný kurz Tipsportu\n"]
    if b["n"]:
        out += [
            f"Sázka = strana a lajna s největší hranou modelu proti de-vig kurzu téže knihy (přepočteno "
            f"na 60 minut), nejvýš jedna na (zápas, hráč). Výplata 1 / (p_trhu × (1 + m)), m = "
            f"{cz(margin, 4)}, kde p_trhu je medián knih na téže lajně a straně přepočtený na 60 minut. "
            "Vypořádání za 60 minut.\n",
            "| | |", "|---|---|",
            f"| sázek | {b['n']} v {b['days']} herních dnech ({cz(b['per_day'], 1)} na herní den vzorku) |",
            f"| podíl „více“ | {pct(b['over_share'])} |",
            f"| výhry | {pct(b['hit'])} (model čekal {pct(b['p_model'])}, trh {pct(b['p_market'])}) |",
            f"| průměrná hrana podle modelu | {cz(b['edge'] * 100, 1)} p.b. |",
            f"| průměrný simulovaný kurz | {cz(b['avg_price'], 3)} (break-even {pct(b['break_even'])}) |",
            f"| **ROI za kurz Tipsportu** | **{pct(b['roi'])}** (95% interval {pct(b['lo'])} až {pct(b['hi'])}) |",
            f"| vedlejší: ROI za nejlepší kurz amerických knih, jejich pravidla | {pct(b['roi_us'])} "
            f"(95% interval {pct(b['us_lo'])} až {pct(b['us_hi'])}) |",
        ]
    else:
        out.append("Filtr nevybral žádnou sázku.\n")
    out += [
        "\n## K5 — objem\n",
        f"{cz(v['per_day_all'], 1)} sázky na herní den na všech hráčích s lajnou; americké knihy kotují "
        f"v průměru {cz(players_per_game, 1)} hráče na zápas, Tipsport 6 → po přepočtu "
        f"**{cz(v['per_day_tipsport'])}** sázky na herní den.\n",
        "## Simulace nulového efektu (plán 6.5)\n",
        f"{phase0.NULL_SIMS} simulací, ve kterých je pravda = trh (výsledek každé sázky se losuje "
        "z pravděpodobnosti trhu, výběr sázek a kurzy zůstávají). K4b by prošlo v "
        f"**{pct(null['pass_rate'])}** simulací; průměrné ROI simulací {pct(null['roi_mean'])}, "
        f"95. percentil {pct(null['roi_p95'])}. Sázky se losují nezávisle; závislost sázek téhož "
        "zápasu by rozptyl mírně zvětšila.\n",
        "## Data\n",
        f"- zápasů vzorku s closingovou lajnou: {games}; herních dnů: {sample_days}",
        f"- hráčů s lajnou na zápas (americké knihy): {cz(players_per_game, 1)}",
        f"- jmen, která se nepodařilo spárovat s hráčem: {unmatched}",
        f"- kotací na celočíselné lajně (vynechány, hrozí push): {whole}",
        "",
        "## Co se nevyhodnocovalo\n",
        "Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; žádný "
        "druhý model (plán 6.6). Podíl „více“ a kalibrace jsou jen popis.",
    ]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

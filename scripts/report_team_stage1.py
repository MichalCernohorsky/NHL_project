#!/usr/bin/env python3
"""Stage 1 of the team markets plan: the frozen naive team models on the
validation season 2025-26, without any odds (docs/team_markets_plan.md 5,
docs/team_models.md). Criterion T1, calibration and the null simulation
for all four markets; writes docs/team_stage1_report.md.

Run once, after models/naive_team.json is frozen. Nothing is tuned by it.

Usage:
    python scripts/report_team_stage1.py
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

MODEL = ROOT / "models" / "naive_team.json"
OUT = ROOT / "docs" / "team_stage1_report.md"
NULL_REPS = 500
NAMES = {"S-T": "střely týmu", "S-Z": "střely v zápasu", "T-T": "dvouminutové tresty týmu",
         "T-Z": "dvouminutové tresty v zápasu"}


def cz(x, d=4):
    return f"{x:.{d}f}".replace(".", ",")


def market(y, mu, k, base_mu, base_k, days, lines):
    day_idx, counts = tm.boot_counts(np.asarray(days))
    res = tm.t1(y, mu, k, base_mu, base_k, day_idx, counts)
    res.update(n=int(len(y)), days=int(counts.shape[1]), mean_y=float(np.mean(y)),
               mean_mu=float(np.mean(mu)), cal=tm.calibration(y, mu, k, lines),
               boot=(day_idx, counts))
    return res


def main():
    model = json.loads(MODEL.read_text())
    conn = connect(resolve_db_path(load_config()))
    rng = np.random.default_rng(17)
    out, summary = [], []
    for family in tm.FAMILIES:
        const = model["families"][family]
        lm = const["league_mean_train"]
        df = tm.add_asof(tm.load_team_games(conn, [*tm.TRAIN, tm.VALID], family))
        val = df[df["season"] == tm.VALID].reset_index(drop=True)
        mu = tm.predict(val, const)
        base = tm.baselines(val, lm)
        games = tm.game_frame(val, mu, base, lm)
        team_lines, game_lines = tm.LINES[family]
        m_team, m_game = tm.MARKETS[family]
        y_t = val["y"].to_numpy()
        y_g = games["y"].to_numpy()
        bk = const["baselines"]
        res = {
            m_team: market(y_t, mu, const["k_team"], base,
                           {n: bk[n]["k_team"] for n in bk}, val["game_date"], team_lines),
            m_game: market(y_g, games["mu"].to_numpy(), const["k_game"],
                           {n: games[n].to_numpy() for n in ("z0", "z1")},
                           {n: bk[n]["k_game"] for n in bk}, games["game_date"], game_lines),
        }
        # null simulation: (a) shuffled opponents, (b) shuffled predictions
        opp_def = tm.opponent_defence(val, const)
        passes = {m: {"a": 0, "b": 0} for m in res}
        for _ in range(NULL_REPS):
            mu_a = tm.predict(val, const, defence_override=rng.permutation(opp_def))
            mu_b = rng.permutation(mu)
            for kind, mu_null in (("a", mu_a), ("b", mu_b)):
                g_null = tm.game_frame(val, mu_null, base, lm)["mu"].to_numpy()
                if kind == "b":
                    g_null = rng.permutation(games["mu"].to_numpy())
                passes[m_team][kind] += tm.t1(
                    y_t, mu_null, const["k_team"], base, {n: bk[n]["k_team"] for n in bk},
                    *res[m_team]["boot"])["pass"]
                passes[m_game][kind] += tm.t1(
                    y_g, g_null, const["k_game"], {n: games[n].to_numpy() for n in ("z0", "z1")},
                    {n: bk[n]["k_game"] for n in bk}, *res[m_game]["boot"])["pass"]
        for m, r in res.items():
            r["null"] = {kind: passes[m][kind] / NULL_REPS for kind in ("a", "b")}
            summary.append((m, r))
            print(f"{m}: n={r['n']} dnu={r['days']} | ztrata model {r['loss_model']:.4f} | "
                  f"Z0 +{r['z0']['gain']:.4f} [{r['z0']['lo']:.4f}, {r['z0']['hi']:.4f}] | "
                  f"Z1 +{r['z1']['gain']:.4f} [{r['z1']['lo']:.4f}, {r['z1']['hi']:.4f}] | "
                  f"T1 {'ANO' if r['pass'] else 'ne'} | prumer y {r['mean_y']:.2f} vs mu {r['mean_mu']:.2f} | "
                  f"nula a {r['null']['a']:.3f} b {r['null']['b']:.3f}")

    out.append("# Týmové trhy — etapa 1: zpětné ověření bez kurzů (sezóna 2025-26)\n")
    out.append("Plán `docs/team_markets_plan.md` (sekce 5, dodatek T-1), výklad "
               "`docs/team_models.md`. Zamrazený model `models/naive_team.json` "
               f"(`{model['model']}`, odhad jen na {', '.join(model['trained_on'])}). "
               "Vygenerováno skriptem `scripts/report_team_stage1.py`; ručně se needituje.\n")
    out.append("**Co tahle čísla říkají a co ne:** jestli model předpovídá počty lépe než "
               "dva jednoduché základy. O zisku proti Tipsportu neříkají nic — historické "
               "kurzy těchto trhů neexistují.\n")
    out.append("## Kritérium T1\n")
    out.append("Zisk = o kolik je logaritmická ztráta modelu menší než ztráta základu "
               "(kladné = model lepší). Interval: bootstrap 95 %, seed 17, 10 000, "
               "převzorkují se herní dny. T1 = oba intervaly nad nulou.\n")
    out.append("| trh | řádků | herních dnů | ztráta modelu | zisk proti Z0 (liga) | 95% interval | "
               "zisk proti Z1 (průměr týmu) | 95% interval | T1 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for m, r in summary:
        out.append(f"| {m} {NAMES[m]} | {r['n']} | {r['days']} | {cz(r['loss_model'])} | "
                   f"{cz(r['z0']['gain'])} | {cz(r['z0']['lo'])} až {cz(r['z0']['hi'])} | "
                   f"{cz(r['z1']['gain'])} | {cz(r['z1']['lo'])} až {cz(r['z1']['hi'])} | "
                   f"**{'splněno' if r['pass'] else 'nesplněno'}** |")
    out.append("\n## Průměr předpovědi proti skutečnosti\n")
    out.append("| trh | skutečný průměr | průměr modelu | rozdíl % |")
    out.append("|---|---|---|---|")
    for m, r in summary:
        out.append(f"| {m} | {cz(r['mean_y'], 2)} | {cz(r['mean_mu'], 2)} | "
                   f"{cz((r['mean_mu'] / r['mean_y'] - 1) * 100, 1)} |")
    out.append("\n## Kalibrace P(více než lajna)\n")
    out.append("Všechny lajny trhu dohromady, pět stejně velkých pásem podle předpovědi.\n")
    for m, r in summary:
        out.append(f"**{m} {NAMES[m]}**\n")
        out.append("| pásmo | případů | předpověď | skutečnost |")
        out.append("|---|---|---|---|")
        for i, row in r["cal"].iterrows():
            out.append(f"| {i + 1} | {int(row['n'])} | {cz(row['predicted'] * 100, 1)} % | "
                       f"{cz(row['observed'] * 100, 1)} % |")
        out.append("")
    out.append("## Simulace nulového efektu\n")
    out.append(f"{NULL_REPS} opakování, stejná bootstrap losování. Podíl opakování, která by "
               "splnila T1: (a) model zná tým, ale soupeře má náhodného; (b) předpovědi "
               "náhodně přeházené mezi zápasy.\n")
    out.append("| trh | (a) promíchaní soupeři | (b) promíchané předpovědi |")
    out.append("|---|---|---|")
    for m, r in summary:
        out.append(f"| {m} | {cz(r['null']['a'] * 100, 1)} % | {cz(r['null']['b'] * 100, 1)} % |")
    out.append("\n## Konstanty zamrazeného modelu\n")
    out.append("| rodina | liga (trénink) | domácí faktor h | w | c | k tým | k zápas |")
    out.append("|---|---|---|---|---|---|---|")
    for family in tm.FAMILIES:
        c = model["families"][family]
        out.append(f"| {'střely' if family == 'shots' else 'tresty'} | {cz(c['league_mean_train'], 3)} | "
                   f"{cz(c['h'], 4)} | {c['w']} | {cz(c['c'], 1)} | {cz(c['k_team'], 2)} | "
                   f"{cz(c['k_game'], 2)} |")
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

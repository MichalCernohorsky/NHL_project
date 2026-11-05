#!/usr/bin/env python3
"""Edge ladder, look 1 (docs/edge_ladder_plan.md, section 6): the tips with
games up to 4. 11. 2026 by band of their promised return at the simulated
Tipsport price, the one slope test with its two simulations, and the
candidate arm (forward from 6. 11.; earlier tips only as description).
Writes docs/edge_ladder_report.md. Nothing here is tuned.

Usage:
    python scripts/report_edge_ladder.py
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nhl_tool import edge_ladder as el
from nhl_tool import tips
from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

PLAN = ROOT / "docs" / "edge_ladder_plan.md"
OUT = ROOT / "docs" / "edge_ladder_report.md"


def cz(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def pct(x, d=1):
    return cz(x * 100, d) + " %"


def plan_sha() -> str:
    text = PLAN.read_text()
    approved, tail = text.split("<!-- konec schváleného znění -->")
    sha = hashlib.sha256(approved.encode()).hexdigest()
    assert re.search(rf"`{sha}`", tail), "the plan changed since it was frozen"
    return sha


def main():
    sha = plan_sha()
    conn = connect(resolve_db_path(load_config()))
    model = tips.load_model()
    df = el.load_tips(conn, upto=el.LOOK1_UPTO)
    pc = el.closing_p(conn, df, model)
    lad = el.ladder(df, pc)
    test = el.slope_test(df)
    false_alarm = el.slope_sims(df, "market")
    power = el.slope_sims(df, "model")
    retro = el.arm_status(el.arm(df, start=None))
    s = df[df["settled"]]

    print(f"tipu {test['n']} dnu {test['days']} | slib (EV) {test['ev'] * 100:+.1f} % | ROI {test['roi'] * 100:+.1f} % | "
          f"sklon {test['b']:+.3f} [{test['lo']:+.3f}, {test['hi']:+.3f}] | {'ROSTE' if test['pass'] else 'neprokazano'} | "
          f"falesny poplach {false_alarm:.3f} | sila {power:.3f}")
    for r in lad.itertuples():
        if r.n:
            print(f"  {r.name:>8}: n={r.n:4d} vyhry {r.hit * 100:5.1f} % (model {r.p_model * 100:5.1f}, trh {r.p_market * 100:5.1f}) "
                  f"EV {r.ev * 100:+6.1f} % ROI {r.roi * 100:+6.1f} % [{r.lo * 100:+6.1f}, {r.hi * 100:+6.1f}] | closing {r.n_close} "
                  f"posun {r.move_pp:+.2f} pb, ROI podle closingu {r.roi_close * 100:+.1f} %")
    print(f"kandidat zpetne (popis): {retro}")

    verdict = "ROI s hranou roste" if test["pass"] else "růst ROI s hranou se neprokázal"
    out = ["# Žebříček hrany — pohled 1\n",
           f"Plán `docs/edge_ladder_plan.md` (schválen a zamrazen 5. 11. 2026, otisk `{sha[:12]}…`). Hratelné tipy "
           f"na střely hráčů se zápasy od 29. 9. do 4. 11. 2026, vyhodnocené za 60 minut, výnos za simulovaný kurz "
           "Tipsportu. Vygenerováno skriptem `scripts/report_edge_ladder.py`; ručně se needituje.\n",
           f"## Verdikt pohledu 1: {verdict}\n",
           "Sklon = o kolik jednotek se v průměru změní výnos tipu, když je jeho slíbený výnos (EV) vyšší o 1 "
           "(o 100 %). Kdyby měl model pravdu, sklon by byl 1; kdyby pravdu měl trh, 0.\n",
           "| tipů | herních dnů | průměrný slib (EV) | skutečné ROI | sklon | 95% interval | verdikt |",
           "|---|---|---|---|---|---|---|",
           f"| {test['n']} | {test['days']} | {pct(test['ev'])} | {pct(test['roi'])} | {cz(test['b'], 2)} | "
           f"{cz(test['lo'], 2)} až {cz(test['hi'], 2)} | **{'roste' if test['pass'] else 'neprokázáno'}** |",
           f"\nSimulace (po {el.SIMS} sezónách se stejnými tipy a kurzy): když má pravdu trh, test by „roste“ "
           f"ohlásil v **{pct(false_alarm)}** případů (falešný poplach); když má pravdu model, v **{pct(power)}** "
           "(síla testu).\n",
           "## Pásma\n",
           "ROI s bootstrap 95% intervalem (seed 17, 10 000, herní dny). Posun trhu = o kolik p. b. se americký trh "
           "do closingu posunul ke straně tipu; ROI podle closingu = co by tip vydělal, kdyby pravdu měl closing.\n",
           "| slíbený výnos | tipů | výhry | model sliboval | trh čekal | průměrný slib | ROI | 95% interval | "
           "s closingem | posun trhu | ROI podle closingu |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in lad.itertuples():
        if not r.n:
            out.append(f"| {r.name} | 0 | | | | | | | | | |")
            continue
        out.append(f"| {r.name} | {r.n} | {pct(r.hit)} | {pct(r.p_model)} | {pct(r.p_market)} | {pct(r.ev)} | "
                   f"**{pct(r.roi)}** | {pct(r.lo)} až {pct(r.hi)} | {r.n_close} | {cz(r.move_pp, 2)} p. b. | "
                   f"{pct(r.roi_close)} |")
    out += ["\n## Kandidát „≥ 10 %, 1 na zápas“\n",
            f"Sleduje se jen dopředu, od zápasů {el.ARM_START[8:10].lstrip('0')}. 11. 2026; pohled po "
            f"{el.ARM_LOOK} tipech a na konci základní části. Zpětně na tipech do 4. 11. (jen popis, o ničem "
            f"nerozhoduje): {retro['n']} tipů, ROI {pct(retro['roi'])} (95% interval {pct(retro['lo'])} až "
            f"{pct(retro['hi'])}), výhry {pct(retro['hit'])}, průměrný slib {pct(retro['ev'])}.\n"
            if retro["n"] else "Zpětně žádný tip.\n",
            "## Co se nevyhodnocovalo\n",
            "Žádná jiná pásma, prahy ani kandidáti; žádné řezy podle hráče, týmu, pozice, strany, lajny ani knihy."]
    OUT.write_text("\n".join(out) + "\n")
    print(f"zapsano {OUT.relative_to(ROOT)} | tipu se slibem celkem {len(s)}")


if __name__ == "__main__":
    main()

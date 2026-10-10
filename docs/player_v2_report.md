# Hráčský model v2 (blok A) na vzorku 330 zápasů 2025-26

Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md`. Zamrazený model `models/player_v2.json` (odhad jen na 2023-24, 2024-25); stejné closingové kurzy, stejný kód a stejná kritéria jako verdikt fáze 0 (`docs/phase0_report.md`). Je to **druhý model na stejných kurzech** — případný úspěch tu není důkaz a musel by se potvrdit na novém vzorku. Zbylé zápasy sezóny 2025-26 se nevyhodnocovaly. Vygenerováno skriptem `scripts/report_player_v2.py`; ručně se needituje.

## Verdikt bloku A: kritéria fáze 0 nesplněna

| kritérium | práh | verze 1 | verze 2 | verze 2: splněno? |
|---|---|---|---|---|
| K4a Brier modelu − Brier trhu | ≤ 0,010 | 0,0032 (0,0016 až 0,0048) | 0,0012 (-0,0002 až 0,0027) | **splněno** |
| K4b ROI za simulovaný kurz Tipsportu | > 0 | -6,9 % (-9,9 % až -4,2 %) | -4,8 % (-7,9 % až -1,9 %) | **nesplněno** |
| K5 sázek na herní den po přepočtu na 6 hráčů | ≥ 3 | 30,04 | 30,20 | **splněno** |

Intervaly jsou 95% bootstrap (seed 17, 10 000, převzorkují se herní dny). „Skoro“ znamená ne.

## Sázky filtru (hrana ≥ 3 p. b., kurz Tipsportu simulovaný s m = 0,0874, 60 minut)

| | verze 1 | verze 2 |
|---|---|---|
| sázek | 3153 | 3170 |
| výhry | 51,7 % | 53,1 % |
| model čekal | 56,7 % | 57,0 % |
| trh čekal | 51,0 % | 51,1 % |
| průměrný simulovaný kurz | 1,836 | 1,832 |
| **ROI za kurz Tipsportu** | -6,9 % (-9,9 % až -4,2 %) | **-4,8 %** (-7,9 % až -1,9 %) |
| vedlejší: ROI za nejlepší americký kurz | -3,5 % (-6,6 % až -0,6 %) | -1,1 % (-4,5 % až 2,0 %) |

## Přesnost předpovědi (Brier, hlavní lajna, celý zápas)

| | Brier |
|---|---|
| trh | 0,2437 |
| verze 1 | 0,2469 |
| verze 2 | 0,2449 |
| zlepšení v1 − v2 na 4336 společných řádcích | 0,00193 (95% interval 0,00086 až 0,00307) |

## Síla testu a nulový efekt

2000 simulací na vybraných sázkách verze 2. *Pravdou je trh* (výsledek se losuje z pravděpodobnosti trhu): K4b by prošlo v 0,0 % simulací, průměrné ROI -8,0 %. *Pravdou je model* (losuje se z pravděpodobnosti modelu): prošlo by v 95,2 %, průměrné ROI 2,8 % — tolik by test ukázal, kdyby měl model pravdu.

## Koeficienty (odhad jen na tréninku)

| | |
|---|---|
| váha pokusů o střelu ve střelbě hráče (α) | 0,7 |
| mocnina očekávaných přesilovek (π) | 0,25 |
| úroveň (všechny zápasy) | -1,51 % |
| tým hraje druhý den po sobě | -3,39 % |
| soupeř hraje druhý den po sobě | 3,49 % |
| rozptyl k | 17,92 (verze 1: 16,84) |

## Co se nevyhodnocovalo

Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; žádná jiná kombinace atributů než blok plánu.

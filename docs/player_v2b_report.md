# Hráčský model v2, blok B (průběh zápasu) na vzorku 330 zápasů 2025-26

Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md` (dodatek N-2). Blok B = zamrazený blok A × násobitel z pravděpodobnosti výhry týmu a čekaného počtu gólů (hlavní kurzy, snímek v 15:00 UTC; 100,0 % zápasů vzorku je má). Stejné closingové kurzy, kód a kritéria jako fáze 0. Je to **třetí model na stejných kurzech**. Vygenerováno skriptem `scripts/report_player_v2b.py`; ručně se needituje.

## Verdikt: žádný blok K4b nesplnil — hráčský model podle plánu končí

| | verze 1 | blok A | blok B |
|---|---|---|---|
| K4a Brier modelu − Brier trhu (≤ 0,010) | 0,0032 (0,0016 až 0,0048) — splněno | 0,0012 (-0,0002 až 0,0027) — splněno | 0,0010 (-0,0005 až 0,0026) — splněno |
| **K4b ROI za simulovaný kurz Tipsportu (> 0)** | **-6,9 %** (-9,9 % až -4,2 %) — nesplněno | **-4,8 %** (-7,9 % až -1,9 %) — nesplněno | **-4,4 %** (-7,7 % až -1,5 %) — nesplněno |
| K5 sázek na herní den (≥ 3) | 30,04 — splněno | 30,20 — splněno | 30,45 — splněno |
| sázek | 3153 | 3170 | 3196 |
| výhry | 51,7 % | 53,1 % | 53,3 % |
| model čekal | 56,7 % | 57,0 % | 57,0 % |
| trh čekal | 51,0 % | 51,1 % | 51,1 % |
| vedlejší: ROI za nejlepší americký kurz | -3,5 % (-6,6 % až -0,6 %) | -1,1 % (-4,5 % až 2,0 %) | -0,7 % (-4,0 % až 2,4 %) |
| Brier modelu (trh 0,2437) | 0,2469 | 0,2449 | 0,2447 |
| simulace: pravdou je trh — K4b by prošlo | 0,0 % | 0,0 % | 0,0 % |
| simulace: pravdou je model — K4b by prošlo | 92,9 % | 95,2 % | 95,9 % |

Intervaly jsou 95% bootstrap (seed 17, 10 000, herní dny). „Skoro“ znamená ne.

Zlepšení Brier A − B na 4336 společných řádcích: 0,00020 (95% interval -0,00000 až 0,00042).

## Koeficienty bloku B (odhad jen na tréninku)

| | |
|---|---|
| úroveň (zápasy s kurzy) | -0,11 % |
| pravděpodobnost výhry týmu +10 p. b. | 1,51 % |
| čekaný počet gólů zápasu +0,5 | -0,13 % |
| rozptyl k | 18,01 (blok A 17,92) |

## Co se nevyhodnocovalo

Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; žádná jiná kombinace atributů než bloky plánu. Zbylé zápasy sezóny 2025-26 se neotvíraly.

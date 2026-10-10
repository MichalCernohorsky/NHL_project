# Fáze 0 — verdikt pro střely hráče na branku

Plán `docs/market_discovery_plan.md` (schválen a zamrazen 10. 10. 2026, před nákupem). Zamrazený model `naive_sog_v1` (odhad jen na 2023-24, 2024-25), closingové kurzy amerických knih pro vzorek sezóny 2025-26 koupené 10. 10. 2026. Vygenerováno skriptem `scripts/report_phase0.py`, který byl commitnut před prvním pohledem na koupená data; ručně se needituje.

## Verdikt: trh NEPOSTUPUJE

| kritérium | práh | výsledek | |
|---|---|---|---|
| K1 Tipsport trh vypisuje | ≥ 75 % zápasů, ≥ 4 hráči, do 18:00 | 22 zápasů z 22, 6 hráčů (dodatek D8) | **splněno** |
| K2 data zdarma a denně | NHL API | 3 sezóny, počty za 60 minut, 0 chyb | **splněno** |
| K3 historické kurzy | ≥ 300 zápasů s closingovou lajnou | 330 zápasů (42 herních dnů) | **splněno** |
| K4a model není beznadějně za trhem | Brier modelu − Brier trhu ≤ 0,010 | 0,0032 (95% interval 0,0016 až 0,0048) | **splněno** |
| K4b filtr není celý pod nulou | ROI za simulovaný kurz Tipsportu > 0 | -6,9 % (95% interval -9,9 % až -4,2 %) | **nesplněno** |
| K5 objem | ≥ 3 sázky na herní den po přepočtu na 6 hráčů | 30,04 | **splněno** |

Trh postupuje jen při splnění všech kritérií. „Skoro prošel“ znamená neprošel; druhé kolo s jinými parametry se nekoná (plán 6.6).

## K4a — Brier proti trhu (celý zápas, hlavní lajna)

4336 řádků (zápas, hráč) z 37 herních dnů; hráči s ≥ 10 zápasy v sezóně, kteří nastoupili. Americký trh počítá prodloužení, proto se tu model i výsledek berou za celý zápas.

| | Brier |
|---|---|
| model | 0,2469 |
| trh | 0,2437 |
| rozdíl (model − trh) | 0,0032 (95% interval 0,0016 až 0,0048; bootstrap, seed 17, 10 000, herní dny) |

Kalibrace v decilech (jen diagnostika, o postupu nerozhoduje):

| decil | model: předpověď | model: skutečnost | trh: předpověď | trh: skutečnost |
|---|---|---|---|---|
| 1 | 33,3 % | 37,3 % | 39,2 % | 36,2 % |
| 2 | 39,1 % | 44,7 % | 42,6 % | 44,5 % |
| 3 | 42,3 % | 48,4 % | 45,3 % | 42,4 % |
| 4 | 44,9 % | 43,3 % | 47,7 % | 47,0 % |
| 5 | 47,4 % | 53,2 % | 49,9 % | 48,2 % |
| 6 | 49,8 % | 52,5 % | 52,2 % | 54,8 % |
| 7 | 52,3 % | 49,4 % | 54,4 % | 54,5 % |
| 8 | 55,0 % | 56,8 % | 56,5 % | 54,7 % |
| 9 | 58,2 % | 63,0 % | 58,9 % | 56,1 % |
| 10 | 63,2 % | 57,7 % | 61,4 % | 68,1 % |

## K4b — filtr hrany ≥ 3 p.b., výplata za simulovaný kurz Tipsportu

Sázka = strana a lajna s největší hranou modelu proti de-vig kurzu téže knihy (přepočteno na 60 minut), nejvýš jedna na (zápas, hráč). Výplata 1 / (p_trhu × (1 + m)), m = 0,0874, kde p_trhu je medián knih na téže lajně a straně přepočtený na 60 minut. Vypořádání za 60 minut.

| | |
|---|---|
| sázek | 3153 v 37 herních dnech (75,1 na herní den vzorku) |
| podíl „více“ | 27,8 % |
| výhry | 51,7 % (model čekal 56,7 %, trh 51,0 %) |
| průměrná hrana podle modelu | 6,7 p.b. |
| průměrný simulovaný kurz | 1,836 (break-even 54,5 %) |
| **ROI za kurz Tipsportu** | **-6,9 %** (95% interval -9,9 % až -4,2 %) |
| vedlejší: ROI za nejlepší kurz amerických knih, jejich pravidla | -3,5 % (95% interval -6,6 % až -0,6 %) |

## K5 — objem

75,1 sázky na herní den na všech hráčích s lajnou; americké knihy kotují v průměru 15,0 hráče na zápas, Tipsport 6 → po přepočtu **30,04** sázky na herní den.

## Simulace nulového efektu (plán 6.5)

2000 simulací, ve kterých je pravda = trh (výsledek každé sázky se losuje z pravděpodobnosti trhu, výběr sázek a kurzy zůstávají). K4b by prošlo v **0,0 %** simulací; průměrné ROI simulací -8,0 %, 95. percentil -5,4 %. Sázky se losují nezávisle; závislost sázek téhož zápasu by rozptyl mírně zvětšila.

## Data

- zápasů vzorku s closingovou lajnou: 330; herních dnů: 42
- hráčů s lajnou na zápas (americké knihy): 15,0
- jmen, která se nepodařilo spárovat s hráčem: 2
- kotací na celočíselné lajně (vynechány, hrozí push): 0

## Co se nevyhodnocovalo

Žádné řezy podle pozice, týmu, výšky lajny, strany ani knihy; žádný jiný práh hrany; žádný druhý model (plán 6.6). Podíl „více“ a kalibrace jsou jen popis.

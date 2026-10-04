# Týmové trhy — etapa 1: zpětné ověření bez kurzů (sezóna 2025-26)

Plán `docs/team_markets_plan.md` (sekce 5, dodatek T-1), výklad `docs/team_models.md`. Zamrazený model `models/naive_team.json` (`naive_team_v1`, odhad jen na 2023-24, 2024-25). Vygenerováno skriptem `scripts/report_team_stage1.py`; ručně se needituje.

**Co tahle čísla říkají a co ne:** jestli model předpovídá počty lépe než dva jednoduché základy. O zisku proti Tipsportu neříkají nic — historické kurzy těchto trhů neexistují.

## Kritérium T1

Zisk = o kolik je logaritmická ztráta modelu menší než ztráta základu (kladné = model lepší). Interval: bootstrap 95 %, seed 17, 10 000, převzorkují se herní dny. T1 = oba intervaly nad nulou.

| trh | řádků | herních dnů | ztráta modelu | zisk proti Z0 (liga) | 95% interval | zisk proti Z1 (průměr týmu) | 95% interval | T1 |
|---|---|---|---|---|---|---|---|---|
| S-T střely týmu | 2624 | 167 | 3,2035 | 0,0641 | 0,0472 až 0,0801 | 0,0471 | 0,0304 až 0,0647 | **splněno** |
| S-Z střely v zápasu | 1312 | 167 | 3,4963 | 0,0328 | 0,0128 až 0,0516 | -0,0016 | -0,0145 až 0,0115 | **nesplněno** |
| T-T dvouminutové tresty týmu | 2624 | 167 | 1,9238 | 0,0198 | 0,0084 až 0,0315 | 0,0270 | 0,0179 až 0,0365 | **splněno** |
| T-Z dvouminutové tresty v zápasu | 1312 | 167 | 2,4608 | 0,0248 | 0,0077 až 0,0414 | 0,0079 | -0,0006 až 0,0166 | **nesplněno** |

## Průměr předpovědi proti skutečnosti

| trh | skutečný průměr | průměr modelu | rozdíl % |
|---|---|---|---|
| S-T | 27,37 | 27,53 | 0,6 |
| S-Z | 54,74 | 55,05 | 0,6 |
| T-T | 3,35 | 3,36 | 0,4 |
| T-Z | 6,70 | 6,73 | 0,4 |

## Kalibrace P(více než lajna)

Všechny lajny trhu dohromady, pět stejně velkých pásem podle předpovědi.

**S-T střely týmu**

| pásmo | případů | předpověď | skutečnost |
|---|---|---|---|
| 1 | 4724 | 24,5 % | 24,9 % |
| 2 | 4723 | 41,6 % | 41,8 % |
| 3 | 4723 | 55,0 % | 53,4 % |
| 4 | 4723 | 67,7 % | 65,4 % |
| 5 | 4723 | 82,4 % | 80,2 % |

**S-Z střely v zápasu**

| pásmo | případů | předpověď | skutečnost |
|---|---|---|---|
| 1 | 3149 | 25,5 % | 26,7 % |
| 2 | 3149 | 41,5 % | 40,2 % |
| 3 | 3149 | 54,3 % | 52,4 % |
| 4 | 3149 | 66,8 % | 65,1 % |
| 5 | 3148 | 80,8 % | 78,0 % |

**T-T dvouminutové tresty týmu**

| pásmo | případů | předpověď | skutečnost |
|---|---|---|---|
| 1 | 1050 | 18,0 % | 16,8 % |
| 2 | 1050 | 26,0 % | 22,2 % |
| 3 | 1050 | 33,5 % | 31,1 % |
| 4 | 1049 | 41,2 % | 37,5 % |
| 5 | 1049 | 52,0 % | 48,5 % |

**T-Z dvouminutové tresty v zápasu**

| pásmo | případů | předpověď | skutečnost |
|---|---|---|---|
| 1 | 1050 | 20,9 % | 20,0 % |
| 2 | 1050 | 32,4 % | 30,1 % |
| 3 | 1050 | 42,8 % | 39,4 % |
| 4 | 1049 | 53,9 % | 51,8 % |
| 5 | 1049 | 67,5 % | 63,1 % |

## Simulace nulového efektu

500 opakování, stejná bootstrap losování. Podíl opakování, která by splnila T1: (a) model zná tým, ale soupeře má náhodného; (b) předpovědi náhodně přeházené mezi zápasy.

| trh | (a) promíchaní soupeři | (b) promíchané předpovědi |
|---|---|---|
| S-T | 0,0 % | 0,0 % |
| S-Z | 0,0 % | 0,0 % |
| T-T | 0,4 % | 0,0 % |
| T-Z | 0,0 % | 0,0 % |

## Konstanty zamrazeného modelu

| rodina | liga (trénink) | domácí faktor h | w | c | k tým | k zápas |
|---|---|---|---|---|---|---|
| střely | 28,903 | 1,0198 | 12 | 0,6 | 95,67 | 527,64 |
| tresty | 3,300 | 0,9675 | 30 | 0,6 | 5000,00 | 26,72 |

# Tresty týmu (T-T) s kalibrací P(více) — dodatek T-4, sezóna 2025-26

Plán `docs/team_markets_plan.md`, dodatek T-4. Průměr μ ze zamrazeného `models/naive_team.json`, kalibrace ze zamrazeného `models/naive_team_tt_cal.json` (odhad jen na 2023-24, 2024-25). Sezóna 2025-26 je u tohoto trhu použita k ověření **podruhé** (poprvé `docs/team_stage1_report.md`). Vygenerováno skriptem `scripts/report_team_tt_cal.py`; ručně se needituje.

## Kritérium T1 (na výsledku více / méně, lajny 3.5 a 4.5 dohromady)

Ztráta = −ln pravděpodobnosti toho, co nastalo. Zisk = o kolik má základ větší ztrátu než model. Bootstrap 95 %, seed 17, 10 000, převzorkují se herní dny.

| řádků × lajny | herních dnů | ztráta modelu | zisk proti Z0 | 95% interval | zisk proti Z1 | 95% interval | T1 |
|---|---|---|---|---|---|---|---|
| 5248 | 167 | 0,5904 | 0,0132 | 0,0071 až 0,0192 | 0,0079 | 0,0024 až 0,0134 | **splněno** |

## Po lajnách

| lajna | předpověď „více“ | skutečnost | zisk proti Z0 | 95% interval | zisk proti Z1 | 95% interval |
|---|---|---|---|---|---|---|
| 3,5 | 39,6 % | 40,3 % | 0,0135 | 0,0076 až 0,0193 | 0,0081 | 0,0025 až 0,0138 |
| 4,5 | 21,6 % | 22,1 % | 0,0130 | 0,0059 až 0,0201 | 0,0077 | 0,0015 až 0,0139 |

## Kalibrace v pěti pásmech (obě lajny)

| pásmo | případů | předpověď | skutečnost |
|---|---|---|---|
| 1 | 1050 | 15,5 % | 16,8 % |
| 2 | 1050 | 22,6 % | 22,0 % |
| 3 | 1050 | 30,4 % | 31,9 % |
| 4 | 1049 | 37,8 % | 36,8 % |
| 5 | 1049 | 46,7 % | 48,6 % |

## Simulace nulového efektu

500 opakování, kalibrace se nepřeodhadovala. Podíl, který by splnil T1: promíchaní soupeři 0,0 %, promíchané předpovědi 0,0 %.


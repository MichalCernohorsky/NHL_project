# Týmové modely v2 na sezóně 2025-26

Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md`. Koeficienty ze zamrazeného `models/team_v2.json` (odhad jen na 2023-24, 2024-25), verze 1 ze zamrazených `models/naive_team.json` a `models/naive_team_tt_cal.json`. Sezóna 2025-26 už ověřovala verzi 1 — tohle je **druhý pohled** na stejná data; jediný čistý test je potvrzení dopředu na sezóně 2026-27. Vygenerováno skriptem `scripts/report_team_v2.py`; ručně se needituje.

## Verdikt bloku A

Ztráta = −ln pravděpodobnosti toho, co nastalo (S-T: skutečný počet střel; T-T: více / méně na 3,5 a 4,5). Zisk = ztráta verze 1 − ztráta verze 2; kladný = verze 2 je lepší. Bootstrap 95 %, seed 17, 10 000, převzorkují se herní dny. Verze 2 nahradí verzi 1, když je **celý interval nad nulou**.

| trh | řádků | herních dnů | ztráta v1 | ztráta v2 | zisk | 95% interval | verdikt |
|---|---|---|---|---|---|---|---|
| střely týmu (S-T) | 2624 | 167 | 3,2035 | 3,1973 | 0,0062 | 0,0025 až 0,0098 | **v2 nahradí v1** |
| tresty týmu (T-T) | 2624 | 167 | 0,5904 | 0,5881 | 0,0023 | 0,0007 až 0,0041 | **v2 nahradí v1** |

## Síla testu a nulový efekt

500 simulovaných sezón na stejných zápasech a se stejným bootstrapem. *Falešný poplach*: pravdou je verze 1 — jak často by test přesto řekl „v2 nahradí“. *Síla*: pravdou je verze 2 — jak často by to test poznal.

| srovnání | falešný poplach | síla |
|---|---|---|
| S-T: v2 proti v1 | 0,0 % | 75,0 % |
| T-T: v2 proti v1 | 0,0 % | 16,4 % |
| T-T: rozhodčí proti bloku A | 0,0 % | 14,0 % |

## Rozhodčí (blok R, jen tresty)

V historii jsou rozhodčí známi vždy; tohle říká, o kolik by jejich znalost zlepšila předpověď trestů — o nasazení nerozhoduje.

| srovnání | zisk | 95% interval | celý nad nulou |
|---|---|---|---|
| blok A + rozhodčí proti bloku A | 0,0012 | 0,0000 až 0,0024 | ano |
| blok A + rozhodčí proti verzi 1 | 0,0035 | 0,0014 až 0,0057 | ano |

## Koeficienty (odhad jen na tréninku)

Násobitel = exp(koeficient): o kolik procent atribut posune očekávaný počet.

| atribut | střely týmu | tresty týmu |
|---|---|---|
| úroveň (všechny zápasy) | -0,37 % | -2,52 % |
| jedna očekávaná přesilovka navíc | -0,15 % | 2,77 % |
| 1.–10. zápas sezóny | 1,01 % | 5,87 % |
| 11.–20. zápas sezóny | -1,66 % | -3,90 % |
| tým hraje druhý den po sobě | -3,02 % | 0,62 % |
| soupeř hraje druhý den po sobě | 2,57 % | 0,01 % |
| váha pokusů o střelu ve formě (α) | 0,4 | — |
| rozhodčí: +1 trest na zápas nad ligou (po stažení) | — | 13,24 % |

Rozptyl k: střely 100,13 (verze 1: 95,67). Směrodatná odchylka R mezi zápasy 2025-26: 0,202 trestu.

## Po částech sezóny (popis)

| část | řádků | střely: skutečnost | v1 | v2 | „více než 3,5“ trestu: skutečnost | v1 | v2 |
|---|---|---|---|---|---|---|---|
| říjen | 360 | 27,78 | 27,86 | 27,96 | 48,6 % | 40,8 % | 43,5 % |
| listopad | 450 | 27,09 | 27,62 | 27,22 | 38,9 % | 41,8 % | 40,3 % |
| zbytek | 1814 | 27,36 | 27,44 | 27,32 | 39,0 % | 38,8 % | 38,6 % |

## Kalibrace v pěti pásmech (popis)

Střely týmu, lajny 22.5–30.5 dohromady:

| pásmo | v1 předpověď | v1 skutečnost | v2 předpověď | v2 skutečnost |
|---|---|---|---|---|
| 1 | 24,5 % | 24,9 % | 23,9 % | 24,5 % |
| 2 | 41,6 % | 41,8 % | 40,9 % | 41,4 % |
| 3 | 55,0 % | 53,4 % | 54,1 % | 53,3 % |
| 4 | 67,7 % | 65,4 % | 67,0 % | 65,5 % |
| 5 | 82,4 % | 80,2 % | 81,7 % | 81,0 % |

Tresty týmu, lajny 3,5 a 4,5 dohromady:

| pásmo | v1 předpověď | v1 skutečnost | v2 předpověď | v2 skutečnost | s rozhodčími předpověď | s rozhodčími skutečnost |
|---|---|---|---|---|---|---|
| 1 | 15,5 % | 16,8 % | 15,1 % | 16,3 % | 15,2 % | 16,9 % |
| 2 | 22,6 % | 22,0 % | 22,6 % | 22,1 % | 22,8 % | 21,8 % |
| 3 | 30,4 % | 31,9 % | 30,3 % | 31,5 % | 30,4 % | 31,0 % |
| 4 | 37,8 % | 36,8 % | 37,8 % | 37,0 % | 38,0 % | 37,1 % |
| 5 | 46,7 % | 48,6 % | 47,2 % | 49,2 % | 47,5 % | 49,3 % |

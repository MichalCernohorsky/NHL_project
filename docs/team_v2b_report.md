# Týmové modely v2, blok B (průběh zápasu z hlavních kurzů) na sezóně 2025-26

Plán `docs/models_v2_plan.md`, výklad `docs/models_v2_notes.md` (dodatek N-2). Blok B = zamrazený blok A × násobitel z pravděpodobnosti výhry a čekaného počtu gólů (medián aspoň 3 amerických knih, snímek v 15:00 UTC herního dne). Koeficienty ze zamrazeného `models/team_v2b.json` (odhad jen na 2023-24, 2024-25). Sezóna 2025-26 je tu použita **potřetí** (verze 1, blok A, blok B); čistý test je až potvrzení dopředu. Vygenerováno skriptem `scripts/report_team_v2b.py`; ručně se needituje.

## Verdikt bloku B

Zisk = ztráta bloku A − ztráta bloku B; kladný = B je lepší. Bootstrap 95 %, seed 17, 10 000, herní dny. B nahradí A, když je **celý interval nad nulou**.

| trh | řádků | s kurzy | ztráta A | ztráta B | zisk | 95% interval | verdikt | B proti verzi 1 |
|---|---|---|---|---|---|---|---|---|
| střely týmu (S-T) | 2624 | 99,9 % | 3,1973 | 3,1949 | 0,0024 | -0,0002 až 0,0049 | **zůstává A** | 0,0086 (0,0037 až 0,0134) |
| tresty týmu (T-T) | 2624 | 99,9 % | 0,5881 | 0,5881 | 0,0000 | -0,0003 až 0,0003 | **zůstává A** | 0,0023 (0,0007 až 0,0041) |

## Síla testu a nulový efekt

500 simulovaných sezón. *Falešný poplach*: pravdou je blok A. *Síla*: pravdou je blok B.

| srovnání | falešný poplach | síla |
|---|---|---|
| S-T: B proti A | 0,0 % | 38,0 % |
| T-T: B proti A | 0,6 % | 5,6 % |

## Koeficienty (odhad jen na tréninku)

| atribut | střely týmu | tresty týmu |
|---|---|---|
| úroveň (zápasy s kurzy) | -0,08 % | -0,02 % |
| pravděpodobnost výhry +10 p. b. | 1,42 % | -0,87 % |
| čekaný počet gólů zápasu +0,5 | 0,09 % | 0,22 % |

Průměr čekaných gólů v tréninku 6,27. Rozptyl k střel 103,07 (blok A 100,13).

## Rozhodčí nad blokem B (jen tresty, popis)

Zisk proti bloku B 0,0012 (95% interval 0,00002 až 0,0024).


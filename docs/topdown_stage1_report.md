# Trh jako model — etapa 1: kontrola principu na koupených kurzech

Plán `docs/topdown_plan.md` (schválen a zamrazen 10. 10. 2026), sekce 3, dodatek TD-1. Closingové kurzy amerických knih, vzorek 330 zápasů sezóny 2025-26. Vygenerováno skriptem `scripts/report_topdown_stage1.py`, který byl commitnut před výpočtem; ručně se needituje.

**Otázka:** když jedna kniha platí o 3 % a víc nad férový kurz podle ostatních knih, vyplatí se u ní vsadit? Jinak řečeno: má pravdu konsensus, nebo kniha, která se odchýlila?

## Kritérium P1 (bodový odhad ROI > 0): **splněno**

| | |
|---|---|
| knih ve vzorku | 8 |
| řádků (zápas, hráč, lajna, kniha) s ≥ 3 dalšími knihami | 27925 |
| sázek podle pravidla | 76 na 72 dvojicích (zápas, hráč), 28 herních dnů |
| očekávaný zisk podle pravidla | 4,3 % |
| **skutečné ROI** | **1,93 %** (95% interval -21,25 % až 24,73 %; bootstrap, seed 17, 10 000, herní dny) |
| výhry | 46,1 % (pravidlo čekalo 46,2 %) |
| průměrný kurz | 2,280 |
| podíl „více“ | 38 % |
| celý interval nad nulou („podpořeno“) | ne |

## Simulace (dodatek TD-1, po 2 000)

| scénář | průměrné ROI | rozpětí 5–95 % | podíl simulací s ROI > 0 |
|---|---|---|---|
| princip platí beze zbytku (pravda = konsensus všech knih) | 3,5 % | -19,0 % až 25,5 % | 60,2 % |
| nulový efekt (pravdu má kniha, u které se sází) | -6,4 % | do 15,2 % (95. percentil) | 31,8 % |

Skutečné ROI se čte proti oběma: čím blíž k prvnímu řádku, tím víc má pravdu konsensus; čím blíž k druhému, tím víc kniha, která se odchýlila.

## Co to říká a co ne

- Vypořádání podle pravidel amerických knih (celý zápas), hráč bez času na ledě = void, nejvýš jedna sázka na (zápas, hráč, kniha).
- Je to test principu mezi americkými knihami navzájem, na closingu. O Tipsportu neříká nic jistého: jeho odchylky mohou mít jinou příčinu. To měří až etapa 2 na kurzech z tiketů.
- Žádné řezy podle knihy, hráče, lajny ani strany (plán, sekce 6).

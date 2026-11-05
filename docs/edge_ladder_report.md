# Žebříček hrany — pohled 1

Plán `docs/edge_ladder_plan.md` (schválen a zamrazen 5. 11. 2026, otisk `b110ee0225c1…`). Hratelné tipy na střely hráčů se zápasy od 29. 9. do 4. 11. 2026, vyhodnocené za 60 minut, výnos za simulovaný kurz Tipsportu. Vygenerováno skriptem `scripts/report_edge_ladder.py`; ručně se needituje.

## Verdikt pohledu 1: ROI s hranou roste

Sklon = o kolik jednotek se v průměru změní výnos tipu, když je jeho slíbený výnos (EV) vyšší o 1 (o 100 %). Kdyby měl model pravdu, sklon by byl 1; kdyby pravdu měl trh, 0.

| tipů | herních dnů | průměrný slib (EV) | skutečné ROI | sklon | 95% interval | verdikt |
|---|---|---|---|---|---|---|
| 3246 | 34 | 4,2 % | −4,3 % | 0,72 | 0,32 až 1,08 | **roste** |

Simulace (po 1000 sezónách se stejnými tipy a kurzy): když má pravdu trh, test by „roste“ ohlásil v **4,5 %** případů (falešný poplach); když má pravdu model, v **99,6 %** (síla testu).

## Pásma

ROI s bootstrap 95% intervalem (seed 17, 10 000, herní dny). Posun trhu = o kolik p. b. se americký trh do closingu posunul ke straně tipu; ROI podle closingu = co by tip vydělal, kdyby pravdu měl closing.

| slíbený výnos | tipů | výhry | model sliboval | trh čekal | průměrný slib | ROI | 95% interval | s closingem | posun trhu | ROI podle closingu |
|---|---|---|---|---|---|---|---|---|---|---|
| < 0 % | 1116 | 51,4 % | 55,6 % | 52,6 % | −2,9 % | **−10,2 %** | −15,7 % až −4,5 % | 1105 | 0,05 p. b. | −7,9 % |
| 0–5 % | 880 | 54,9 % | 58,8 % | 52,8 % | 2,4 % | **−3,8 %** | −9,4 % až 1,5 % | 866 | 0,29 p. b. | −7,5 % |
| 5–10 % | 599 | 55,3 % | 61,5 % | 52,7 % | 7,3 % | **−2,5 %** | −9,3 % až 4,5 % | 579 | 0,48 p. b. | −7,1 % |
| 10–20 % | 537 | 57,4 % | 64,1 % | 51,8 % | 13,9 % | **2,1 %** | −5,7 % až 9,5 % | 519 | 1,02 p. b. | −6,1 % |
| ≥ 20 % | 114 | 57,9 % | 65,9 % | 48,1 % | 26,5 % | **10,6 %** | −4,3 % až 27,3 % | 110 | 1,66 p. b. | −4,7 % |

## Kandidát „≥ 10 %, 1 na zápas“

Sleduje se jen dopředu, od zápasů 6. 11. 2026; pohled po 300 tipech a na konci základní části. Zpětně na tipech do 4. 11. (jen popis, o ničem nerozhoduje): 203 tipů, ROI 13,2 % (95% interval 0,2 % až 24,8 %), výhry 60,6 %, průměrný slib 20,5 %.

## Co se nevyhodnocovalo

Žádná jiná pásma, prahy ani kandidáti; žádné řezy podle hráče, týmu, pozice, strany, lajny ani knihy.

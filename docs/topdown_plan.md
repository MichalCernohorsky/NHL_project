# Trh jako model — sázka, když Tipsport platí víc než férový kurz amerického trhu

Stav: **SCHVÁLENO uživatelem 10. 10. 2026.** Sepsáno po verdiktu fáze 0
(`docs/phase0_report.md`) a po jednom průzkumném pohledu popsaném v sekci 1;
žádný další výsledek tohoto postupu nebyl v době schválení spočítán. Znění
je zamrazené otiskem SHA-256 (oddíl na konci); změny jen jako datované
dodatky.

## 1. Proč, a odkud se ta myšlenka vzala

Fáze 0 ukázala dvě věci: náš model je **horší než americký trh** (Brier
0,2469 proti 0,2437) a jeho tipy vyhrávaly skoro přesně tak často, jak
říkal trh (51,7 % proti 51,0 %). Lepší vlastní model má tedy strop: nejvýš
se trhu vyrovná. Pak ale rozhoduje jediná otázka — **liší se kurzy
Tipsportu od amerického trhu víc, než kolik činí jeho marže?**

**Průzkumný pohled (10. 10. 2026, přiznaně průzkumný):** 65 hráčských lajn
ze dvou dnů (4. a 10. 10.), u nichž máme kurz Tipsportu ze screenshotu
a americký konsensus ze snímku pořízeného 15–35 minut předtím, obojí na
60 minut:

| | |
|---|---|
| odchylka pravděpodobnosti Tipsport − USA (po odečtení marží) | průměr −0,05 p.b., medián absolutní 2,1 p.b., 90. percentil 5,8 p.b., maximum 8,2 p.b. |
| očekávaný zisk všech stran u Tipsportu při pravděpodobnosti z USA | −8,0 % (= marže) |
| lajn, kde má jedna strana kladný očekávaný zisk | **12 z 65** (největší +9,4 %) |

Tipsport tedy v průměru oceňuje stejně jako americký trh, ale u jednotlivých
hráčů se odchyluje dost na to, aby zhruba u každé páté lajny jedna strana
platila víc než férový kurz.

**Proč to ještě nic nedokazuje (nahlas):**

- 65 lajn, dva dny. Žádný výsledek zápasů v tom není.
- **Prokletí vítěze:** největší odchylky vybírají právě případy, kde se
  může mýlit *náš* odhad férové pravděpodobnosti — málo knih, novinka
  o sestavě mezi snímkem a screenshotem, špatně spárované jméno, chyba
  přepočtu na 60 minut. Skutečný zisk vybraných sázek bude menší než
  spočítaný.
- Americký ranní trh hráčských sázek není tak přesný jako closing.
- Tipsport může sázky a vklady na hráčské trhy omezovat.

## 2. Pravidlo (pevné teď)

- **Férová pravděpodobnost** p strany = medián proporcionálně odšťavených
  pravděpodobností amerických knih na téže lajně, přepočtený na 60 minut
  (dodatek D3.3 plánu fáze 0). Jen lajny, které kotují **aspoň 3 knihy**
  oběma stranami.
- **Sázka u Tipsportu**, když kurz × p − 1 ≥ **3 %**, tj. kurz ≥
  **1,03 / p** („minimální kurz"). Na (zápas, hráč) nejvýš jedna sázka:
  strana a lajna s nejvyšším očekávaným ziskem.
- Americký snímek nesmí být v okamžiku tiketu starší než **60 minut**.
- Žádný vlastní model, žádné výjimky podle hráče, týmu, lajny nebo strany.

Práh 3 % je polštář na chyby odhadu; neladí se.

## 3. Etapa 1 — kontrola principu na koupených datech (zdarma)

Historické kurzy Tipsportu neexistují. Dá se ale ověřit sám princip
„konsensus je blíž pravdě než kniha, která se od něj odchýlí" na
closingových kurzech 330 zápasů sezóny 2025-26, které už máme:

- Pro každou knihu B a každou (zápas, hráč, lajna): p = medián ostatních
  knih (aspoň 3 ostatní, obě strany). Sázka u knihy B za její kurz, když
  kurz × p − 1 ≥ 3 %; nejvýš jedna sázka na (zápas, hráč, kniha).
  Vypořádání podle pravidel amerických knih (celý zápas); hráč bez času
  na ledě = void.
- ROI s bootstrap 95% intervalem (seed 17, 10 000, herní dny), počet sázek,
  průměrný očekávaný zisk podle pravidla proti skutečnému.
- **Simulace nulového efektu:** výsledky losované z konsensu všech knih
  (pravda = trh); jak často vyjde ROI > 0.
- **Kritérium P1:** bodový odhad ROI > 0. Nesplněno → postup **končí**
  (odchýlená kniha má pravdu častěji než ostatní). Splněno → etapa 2.
  Interval a simulace se vykazují vždy; „podpořeno" se smí říct, jen když
  je celý interval nad nulou.

Co etapa 1 neříká: nic jistého o Tipsportu. Jeho odchylky mohou mít jinou
příčinu než odchylky amerických knih mezi sebou.

## 4. Etapa 2 — dopředný papírový test u Tipsportu

- Stránka „Férové kurzy": u každého zápasu hráči s lajnou u ≥ 3 knih,
  férový a minimální kurz obou stran, stáří snímku. Tlačítko „obnovit
  snímek" (asi 1 kredit na zápas; nejvýš 3× denně).
- Uživatel porovná s Tipsportem (6 hráčů na zápas) a zapíše tiket, kde
  kurz Tipsportu ≥ minimální kurz: **papírový**, nebo skutečný. Zámek od
  začátku zápasu, vyhodnocení za 60 minut, kurz z tiketu.
- **Metrika:** ROI v jednotkách s bootstrap intervalem přes herní dny.
  Dva pohledy: po **300** a po **800** tiketech; po 300 konec, je-li celý
  interval pod nulou; po 800 „podpořeno" jen s celým intervalem nad nulou.
- **Diagnostika (ne metrika):** posun trhu — férová pravděpodobnost naší
  strany v closingu proti té při tiketu. Kladný průměr znamená, že trh se
  k naší straně přiklonil; ukáže se dřív než ROI.
- **Síla (předem):** při 800 tiketech je interval široký asi ±6,4 p.b.
  a test s 80% pravděpodobností odhalí jen skutečné ROI nad +9 %. Podle
  průzkumného pohledu vychází 2–3 tikety na zápas se 6 hráči Tipsportu,
  tedy 800 tiketů zhruba za 2–3 měsíce.

Doporučení: do pohledu po 300 tiketech jen papírově. Rozhodnutí je
uživatelovo.

## 5. Náklady

- Etapa 1: nic.
- Etapa 2: živé snímky 1–3 kredity na zápas a den (nejvýš ~4 000 kreditů
  za sezónu). Closing pro diagnostiku posunu trhu 10 kreditů na zápas
  (~13 000 za sezónu) — ranní archivní snímek (dalších 10 na zápas) už
  potřeba není a vypne se.

## 6. Co se nedělá

- Žádné řezy podle hráče, týmu, pozice, výšky lajny, strany nebo knihy.
- Žádná změna prahu 3 %, počtu knih ani stáří snímku podle výsledků.
- Žádné stahování kurzů z webu Tipsportu; kurzy zapisuje uživatel.
- Střely hráčů podle naivního modelu se dál nesází (verdikt fáze 0).
<!-- konec schváleného znění -->

## Schválení a dodatky

Schváleno uživatelem 10. 10. 2026 („schvaluji"). Otisk schváleného znění
(vše nad značkou konce schváleného znění): **SHA-256 `10aec8625498de102b661270d2a2600c63c81703acba5174c6ea3fef0735c741`**.
Hlídá ho `tests/test_topdown_plan.py`. Dodatky se připisují sem, s datem.

### Dodatek TD-1 — simulace v etapě 1 (10. 10. 2026, před kódem a před výpočtem)

Sekce 3 nazývá „simulací nulového efektu" simulaci, v níž má pravdu
konsensus všech knih. To je nepřesné pojmenování: taková simulace neukazuje
„žádný efekt", ale naopak **co čekat, když princip platí beze zbytku**
(horní mez). Skutečný nulový stav je opačný: **pravdu má odchýlená kniha**.
Report proto uvede obě simulace (po 2 000):

- *princip platí:* pravda = konsensus všech knih → jaké ROI by pravidlo mělo;
- *nulový efekt:* pravda = kurz knihy, u které se sází (po odečtení její
  marže) → jak často by kritérium P1 (ROI > 0) prošlo náhodou.

V obou se pro každého (zápas, hráč) losuje jeden počet střel z negativně
binomického rozdělení (rozptyl ze zamrazeného modelu), aby sázky na téhož
hráče u více knih a lajn měly společný výsledek. Kritérium P1 se nemění.

### Dodatek TD-2 — denní nákup z archivu: jen closing (10. 10. 2026, rozhodnutí uživatele)

Od 10. 10. 2026 se pro živou sezónu z archivu kupuje jen closingový snímek
(10 kreditů na zápas); ranní archivní snímek se vypíná (`odds.hist_daily_kinds`).
Closing slouží diagnostice posunu trhu v etapě 2.

### Dodatek TD-3 — výsledek etapy 1 a oprava odhadu objemu (10. 10. 2026)

**Etapa 1 (`docs/topdown_stage1_report.md`, jeden běh po commitu kódu):**
8 knih, 27 925 řádků s ≥ 3 dalšími knihami; pravidlo vsadilo jen **76×**
(0,3 % řádků) — na closingu se americké knihy mezi sebou liší málokdy
o víc než své marže. ROI **+1,9 %** (95% interval −21,3 až +24,7 %), výhry
46,1 % proti 46,2 % čekaným pravidlem. **P1 (bodový odhad > 0) je
splněno, „podpořeno" není.**

**Síla té kontroly je malá (nahlas):** v simulaci, kde má pravdu odchýlená
kniha, by P1 prošlo ve 31,8 % případů (průměr −6,4 %); kdyby princip
platil beze zbytku, čekalo by se +3,5 % s rozpětím −19 až +26 %. 76 sázek
tyto dva stavy nerozliší. Etapa 1 tedy princip nevyvrátila, ale ani
nepotvrdila. Podle sekce 3 se pokračuje etapou 2.

**Chyba v sekci 4 schváleného znění.** Odhad „2–3 tikety na zápas, 800
tiketů za 2–3 měsíce" je špatně. V průzkumném vzorku splnily pravidlo
(očekávaný zisk ≥ 3 % **a** ≥ 3 knihy) jen 4 lajny z 65, tj. asi
**0,33 tiketu na zápas**. Do konce základní části (~1 270 zápasů) to dává
zhruba **400 tiketů**: první pohled (300) kolem března, druhý (800) letos
nenastane. Při 300 tiketech je interval široký asi ±11 p.b.; test letos
nejspíš skončí „nerozhodnuto", pokud není výhoda velká.

**Doplnění diagnostiky (ne metriky, pravidlo se nemění).** Aby se dřív
poznalo, jestli odchylky Tipsportu něco vědí, vyhodnocuje se posun trhu
u **všech** lajn Tipsportu přepsaných ze screenshotů, ne jen u tiketů:
o kolik se americký konsensus mezi snímkem a closingem posunul směrem ke
kurzu Tipsportu. Posun blízko nule = odchylka Tipsportu není informace
(dobře pro pravidlo); posun blízko celé odchylce = Tipsport měl pravdu.
Při ~40 lajnách denně je odhad přesný po jednom až dvou týdnech.

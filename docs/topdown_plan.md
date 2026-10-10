# Trh jako model — sázka, když Tipsport platí víc než férový kurz amerického trhu

Stav: **NÁVRH ke schválení** (10. 10. 2026). Sepsáno po verdiktu fáze 0
(`docs/phase0_report.md`) a po jednom průzkumném pohledu popsaném v sekci 1;
žádný další výsledek tohoto postupu nebyl spočítán. Po schválení se
zamrazí otiskem SHA-256; změny jen jako datované dodatky.

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

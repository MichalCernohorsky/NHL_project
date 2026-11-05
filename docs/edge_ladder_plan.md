# Žebříček hrany — roste ROI tipů s jejich hranou?

Stav: **SCHVÁLENO uživatelem 5. 11. 2026** („schvaluji, pusť se do toho"
na návrh z 4. 11. v konverzaci). Sepsáno a commitnuto **před** jakýmkoli
výpočtem výsledků tipů po pásmech hrany; do té chvíle se z tipů četlo jen
rozložení slibů (sloupce `p_model`, `sim_tipsport_price`, `edge`), žádný
výsledek. Znění je zamrazené otiskem SHA-256 (oddíl na konci); změny jen
jako datované dodatky. Vzor: měsíční audit MLB, bod 2 („žebříček edge").

## 1. Proč

Model hráčských střel fázi 0 neprošel a v živých tipech slibuje víc, než
vychází (59 % proti 54 %). Otázka: **mají tipy s vyšší hranou vyšší ROI?**
Když ano, model umí tipy aspoň seřadit a má smysl ostře testovat jen ty
nejsilnější. Když ne (jako u MLB, korelace pásmo ↔ ROI +0,02), víme to hned
a nesledujeme náhodu.

Očekávání předem, nahlas: žebříček vyjde plochý.

## 2. Hrana = slíbený výnos na kurzu Tipsportu

    hrana (EV) = p_model × kurz − 1

- **Tipy na střely hráčů** (`tips`, model `naive_sog_v1`): `p_model` je
  pravděpodobnost strany tipu za 60 minut podle modelu, `kurz` je
  `sim_tipsport_price` = 1 / (p_konsenzus × 1,0874) — odhad kurzu Tipsportu
  z mediánu amerických knih v čase tipu (dodatek D1, m = 0,0874). Obojí se
  zapisuje před zápasem a nemění se.
- **Týmové tikety** (S-T, T-T): `p_model` strany podle modelu, kterým stránka
  tiket posoudila, `kurz` = kurz z tiketu.

Dosavadní práh tipu (3 p. b. proti americké knize) marži Tipsportu
nepokryje; třetina tipů má EV < 0. Práh tipu se tímto plánem **nemění**.

## 3. Populace

- Tipy: `playable = 1`, výsledek `win` nebo `loss` (`void` = hráč nenastoupil,
  vynechává se), sezóna 2026-27 od prvního tipu (29. 9. 2026).
- Výnos tipu = `profit_units` (kurz − 1 při výhře, −1 při prohře), tedy za
  simulovaný kurz Tipsportu. Skutečný kurz Tipsportu u tipů na hráče nemáme.

## 4. Pásma (pevně)

| pásmo | EV |
|---|---|
| 1 | < 0 % |
| 2 | 0 % až < 5 % |
| 3 | 5 % až < 10 % |
| 4 | 10 % až < 20 % |
| 5 | ≥ 20 % |

Zvoleno podle rozložení slibů (bez výsledků): 1 105 / 877 / 597 / 538 / 117
hratelných tipů k 4. 11. 2026.

## 5. Co se v každém pásmu vykazuje (popis)

- počet tipů; podíl výher; průměrný slib modelu (`p_model`); průměrné
  očekávání trhu (`p_konsenzus`); průměrný slíbený výnos (EV);
- **ROI** s bootstrap 95% intervalem (seed 17, 10 000 opakování, převzorkují
  se herní dny; `stats.roi_ci`);
- **posun trhu do closingu**: p_close − p_konsenzus strany tipu v p. b.
  (kladné = trh se do zápasu posunul ke straně tipu) a **očekávané ROI podle
  closingu**: p_close × kurz − 1. p_close = medián proporčně odmaržovaných
  P(strana) knih kotujících obě strany téže lajny v posledním closingovém
  snímku před začátkem zápasu, převedený na 60 minut jako ve fázi 0
  (`phase0.p60`, k a podíl prodloužení zamrazeného modelu, skupina F / D
  tipu). Bez closingu na téže lajně se u tipu nevykazuje.

## 6. Jediný test: roste výnos s hranou?

- **Statistika:** sklon b přímky výnos_tipu = a + b × EV_tipu (metoda
  nejmenších čtverců přes všechny tipy populace).
- **95% interval** sklonu bootstrapem (seed 17, 10 000, převzorkují se
  herní dny).
- **„ROI roste s hranou"** = celý interval nad nulou. Jinak „neprokázáno".
- **Simulace (1 000 opakování, stejné tipy a kurzy, seed 17):**
  (a) *pravdou je trh* — výsledek tipu se losuje s pravděpodobností
  p_konsenzus; skutečný sklon je pak 0; vykáže se podíl simulací, které by
  test splnily (falešný poplach);
  (b) *pravdou je model* — losuje se s `p_model`; skutečný sklon je 1;
  vykáže se podíl, který by test splnil (síla).
- **Pohledy:** (1) hned po zamrazení tohoto plánu na tipech se zápasy do
  4. 11. 2026 včetně; (2) po posledním dni základní části 2026-27 na všech
  tipech. Mezi nimi se žebříček ukazuje v dashboardu průběžně, **rozhoduje
  se jen při pohledech**.

## 7. Jediný kandidát na ostrý test

**„≥ 10 %, 1 na zápas":** z hratelných tipů zápasu ten s nejvyšším EV
(při shodě vyšší `p_model`, pak nižší `tip_id`), je-li jeho EV ≥ 10 %.

- Sleduje se **jen dopředu**: zápasy od **6. 11. 2026** (tipy zapsané až po
  zamrazení plánu). Tipy do 5. 11. se u kandidáta vykazují jen jako popis.
- Výnos za simulovaný kurz Tipsportu, ROI s intervalem jako výše.
- **Pohledy:** po 300 tipech kandidáta a po posledním dni základní části.
  Po 300: konec, když je celý interval pod nulou, jinak pokračovat. Na konci:
  „podpořeno" jen při celém intervalu nad nulou, „vyvráceno" při celém pod
  nulou, jinak „nerozhodnuto".
- Ani „podpořeno" neznamená sázet: kurz je simulovaný. Následoval by
  samostatný plán testu za **skutečné** kurzy Tipsportu (screenshoty
  uživatele) a jeho souhlas.
- Síla (předem, hrubě): při 300 tipech za kurz ~1,85 je interval ROI široký
  asi ±10,5 p. b.; poznat jde jen velká výhoda. Přesně ji vykáže simulace
  „pravdou je model" při pohledu.

## 8. Týmové tikety

Stejná pásma (sekce 4) a stejná tabulka (sekce 5, bez closingu — u týmových
trhů americký trh není) se na stránce Týmové trhy ukáže, až budou tikety.
Test ani kandidát pro ně v tomto plánu nejsou.

## 9. Co se nedělá

- Žádná jiná pásma, prahy ani kandidáti než výše; žádné řezy podle hráče,
  týmu, pozice, strany, lajny ani knihy.
- Žádná změna tipů, prahu tipu, modelu ani dashboardu Tipů dne kromě
  přidaného žebříčku a karty kandidáta.
- Kredity: 0 (closingové kurzy se kupují v denním běhu tak jako tak).
<!-- konec schváleného znění -->

## Schválení a dodatky

Otisk schváleného znění (vše nad značkou konce schváleného znění):
**SHA-256 `b110ee0225c10e47ee50956fddfa4457e94be8a44163d22513c827f8eb0ba3be`**. Hlídá ho `tests/test_edge_ladder_plan.py`.

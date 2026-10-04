# Týmové trhy: střely týmů a dvouminutové tresty — plán před daty

Stav: **schváleno uživatelem 4. 10. 2026.** Sepsáno před prvním pohledem na
jakýkoli výsledek modelu těchto trhů. Znění je zamrazené otiskem SHA-256
(oddíl „Schválení a dodatky" na konci); změny jen jako datované dodatky.
Fáze 0 (střely hráčů, `docs/market_discovery_plan.md`) má přednost
a tímhle plánem se nemění.

## 1. Proč a co je jinak než u střel hráčů

Tipsport tyhle trhy vypisuje u každého zápasu a s nižší marží (7,5–8,1 %
proti 8,7 % u střel hráčů; `docs/tipsport_k1_log.md`, 4. 10.). **Zásadní
rozdíl: nikdo neprodává jejich historické kurzy.** The Odds API je nemá,
SportsGameOdds, OddsPapi ani odds-api.io je neuvádějí (ověřeno 4. 10.),
Tipsport v žádném zdroji není. Nejde tedy zpětně změřit, jestli model
poráží trh. Zbývá:

1. zpětně ověřit, že model předpovídá lépe než jednoduché základy (bez kurzů),
2. dopředu měřit skutečné tikety za skutečné kurzy Tipsportu.

To je slabší důkaz než u střel hráčů a trvá déle (sekce 6).

## 2. Trhy

Podle nabídky Tipsportu 4. 10. 2026 (všech 5 zápasů dne, `docs/tipsport_k1_log.md`):

| # | trh u Tipsportu | lajny 4. 10. | v plánu |
|---|---|---|---|
| S-T | Počet střel *týmu* na branku v zápasu | 23.5–28.5, jedna až dvě na tým | **ano** |
| S-Z | Počet střel na branku v zápasu (oba týmy) | šest lajn po jedné, 49.5–54.5 až 53.5–58.5 | **ano** |
| T-Z | Počet dvouminutových trestů v zápasu | tři lajny, 5.5–7.5 nebo 6.5–8.5 | **ano** |
| T-T | Počet dvouminutových trestů *týmu* | 3.5, jednou 4.5 | **ano** |
| — | Kdo bude mít víc střel / trestů (1 / X / 2) | — | ne: marže 10,2–10,8 % |
| — | Každý tým 3+ / 4+ trestů | — | ne: složená sázka, závislost týmů |
| — | Počet využitých přesilovek | 0.5 / 1.5 | ne: jiný jev (góly), případně později |

Vyhodnocení se bere z pravidel Tipsportu. **Otevřené, potvrdí uživatel
z pravidel (ikona ⓘ / herní plán), před zamrazením modelu:**

- O1: počítají se střely týmu a tresty jen za **60 minut**, nebo i prodloužení?
  (U střel hráče platí 60 minut, dodatek D3.) Výchozí předpoklad: 60 minut.
- O2: dvojitý menší trest (2+2) = dva dvouminutové tresty? Výchozí: ano.
- O3: 2+10 (menší + osobní) = jeden dvouminutový? Výchozí: ano. Větší (5),
  osobní a do konce utkání se nepočítají.
- O4: trest pro hráčskou lavici se počítá týmu? Výchozí: ano.
- O5: trestné střílení místo trestu se nepočítá. Výchozí: nepočítá.

Tresty se proto ukládají **po jednotlivých událostech** (tým, třetina, čas,
druh, délka), takže se pravidlo dá přepočítat bez nového stahování.

## 3. Data (zdarma, NHL API)

- Střely týmu za 60 minut: součet střel hráčů bez prodloužení — v databázi
  pro 3 sezóny (3 936 zápasů) a denně.
- Tresty: události `penalty` z play-by-play (druh, délka, tým, třetina).
  Je potřeba je znovu stáhnout pro 3 sezóny (~4 000 dotazů, bez kreditů).
- Rozhodčí: `gameInfo.referees` z right-rail, u odehraných zápasů vždy.
  **Kdy jsou známí předem, se neví:** 4. 10. v 10:30 CZ je API nemělo ani
  u zápasu se začátkem v 19:00 CZ. Denní běh proto začne zapisovat, zda už
  je u dnešních zápasů má (čas běhu, zápas, ano/ne). Model **nesmí** použít
  rozhodčí, dokud se neprokáže, že jsou známí před sázením (18:00 CZ)
  u ≥ 75 % zápasů v ≥ 10 herních dnech. Do té doby jen bez nich.

## 4. Naivní modely (zamrazí se před prvním vyhodnocením)

Stejný duch jako u střel hráčů: málo parametrů, vše odhadnuto jen na
2023-24 + 2024-25, sezóna 2025-26 slouží jen k ověření.

**Střely týmu (S-T).** Očekávání za 60 minut
μ = L × útok_T × obrana_S × doma, kde L je ligový průměr, útok_T = střely
týmu / L a obrana_S = střely povolené soupeřem / L, obojí z posledních
20 zápasů a stažené k 1 (váha se odhadne na trénovacích sezónách; začátek
sezóny stojí na loňsku staženém k 1), „doma" jeden ligový faktor. Rozdělení
negativně binomické s jedním rozptylem.

**Střely v zápasu (S-Z).** μ = μ_domácí + μ_hosté; rozdělení negativně
binomické s vlastním rozptylem odhadnutým na součtech (střely obou týmů
v jednom zápase nejsou nezávislé).

**Tresty týmu (T-T) a zápasu (T-Z).** Stejná stavba: μ = L × faul_T ×
vynucení_S × doma, kde faul_T = tresty týmu / L, vynucení_S = tresty,
které soupeř svým protivníkům přivodí / L. T-Z jako součet s vlastním
rozptylem. Bez rozhodčích (sekce 3).

Zamrazení: konstanty do `models/naive_team.json`, otisk SHA-256 do tohoto
plánu, test ho hlídá (jako `tests/test_frozen_model.py`).

## 5. Etapa 1 — zpětné ověření bez kurzů (zdarma, ~1 týden po schválení)

Na sezóně 2025-26, kterou model neviděl, pro každý trh:

- **Skóre:** průměrná logaritmická ztráta skutečného počtu (střel / trestů)
  pod rozdělením modelu.
- **Základy:** Z0 = ligový průměr pro všechny (stejné rozdělení), Z1 =
  průměr týmu za sezónu do daného dne (pro součty průměr obou).
- **Kritérium T1:** model je lepší než Z0 **i** Z1 a 95% interval rozdílu
  (bootstrap, seed 17, 10 000, převzorkují se herní dny) neobsahuje nulu.
- **Kalibrace:** P(více než lajna) pro lajny, které Tipsport používá
  (S-T 22.5–30.5, S-Z 48.5–59.5, T-Z 5.5–8.5, T-T 3.5 a 4.5): předpověď
  proti skutečné četnosti v pěti pásmech.
- **Simulace nulového efektu:** stejné vyhodnocení s promíchanými soupeři
  (model, který nic neví) — jak často by „prošel" T1 náhodou.

Trh, který T1 nesplní, **končí** — model, který neporazí průměr týmu,
nemá co nabídnout proti sázkovce. Výsledek „nic neprošlo" je platný.

**Co etapa 1 neříká:** nic o zisku. Porazit průměr týmu neznamená porazit
Tipsport. Tipsport týmové trhy mezi zápasy rozlišuje (4. 10.: lajny střel
týmu 23.5–28.5, trestů v zápasu 5.5–7.5 i 6.5–8.5, FLA s lajnou trestů
4.5) — neoceňuje je naslepo. Domněnka z prvních dvou zápasů, že kurzy na
tresty jsou všude stejné, se na pěti zápasech nepotvrdila.

## 6. Etapa 2 — dopředný test za kurzy Tipsportu

Jen pro trhy, které prošly T1.

- Dashboard ukáže pro každý zápas a trh **nejnižší kurz, při kterém sázka
  splní pravidlo** (p_model − 1/kurz ≥ 3 p.b.; stejný práh jako u střel
  hráčů), pro lajny kolem očekávání modelu, obě strany.
- Uživatel porovná s Tipsportem. Co pravidlo splní, zapíše jako tiket:
  **papírový** (bez peněz) nebo skutečný. Vyhodnocuje se kurz z tiketu.
- Prvních 5 herních dnů navíc screenshoty týmových trhů jako 4. 10.
  (přepíšou se do `docs/tipsport_k1_log.md`) — na popis toho, jak moc
  Tipsport kurzy mezi zápasy mění. Nic se podle toho neladí.

**Vyhodnocení (pevně předem):** ROI v jednotkách za kurz z tiketu,
všechny trhy dohromady i zvlášť, bootstrap 95% interval přes herní dny.
Dva pohledy, žádné další: po **300** a po **800** tiketech (nebo na konci
základní části).

- po 300: konec, když je celý interval pod nulou; jinak pokračovat;
- po 800: „podpořeno", jen když je celý interval nad nulou; „vyvráceno",
  když celý pod nulou; jinak „nerozhodnuto".

**Síla (nahlas, předem).** Jedna sázka za kurz ~1,86 má směrodatnou
odchylku ~0,93 jednotky. Při 800 tiketech je interval široký zhruba
±6,4 p.b. a test odhalí s 80% pravděpodobností jen skutečné ROI **nad
+9 %**. Menší výhodu (třeba +5 %) letos nepozná — na tu by bylo potřeba
~2 700 tiketů. Počítáno pro nezávislé sázky; tikety z jednoho zápasu
nezávislé nejsou, skutečný interval bude spíš širší. Při 4–6 tiketech
denně (předpoklad, ne měření) vyjde 800 tiketů zhruba na 5–7 měsíců.
**Verdikt o týmových trzích tedy letos přijde nejdřív na jaře a jen pro
velkou výhodu.**

**Peníze.** Doporučení: do verdiktu „podpořeno" jen papírové tikety.
Rozhodnutí je uživatelovo.

## 7. Co se nedělá

- Žádné řezy podle atributů (tým, doma/venku, výška lajny, rozhodčí,
  den v týdnu) při vyhodnocení. Trhy S-T, S-Z, T-Z, T-T jsou jediné
  předem dané členění.
- Žádné ladění modelu podle dopředných výsledků. Lepší model (rozhodčí,
  přesilovky, sestavy) až jako nová éra s vlastním plánem.
- Žádné stahování kurzů z webu Tipsportu, dokud nejsou ověřené jeho
  podmínky. Kurzy zapisuje uživatel.
- Žádné kredity The Odds API.

## 8. Pořadí prací

| krok | co | závisí na |
|---|---|---|
| 1 | schválení plánu, odpovědi O1–O5 | uživatel |
| 2 | stažení trestů a rozhodčích za 3 sezóny, denní krok, záznam „rozhodčí známi ano/ne" | 1 |
| 3 | odhad modelů na 2023-25, zamrazení (SHA-256) | 2, O1–O5 |
| 4 | etapa 1: report s T1, kalibrací a nulovou simulací | 3 |
| 5 | stránka „Týmové trhy" + papírové tikety | trhy, které prošly 4 |
| 6 | etapa 2: pohledy po 300 a 800 tiketech | 5 |

Krok 2–4 nestojí žádný kredit a neblokuje fázi 0.
<!-- konec schváleného znění -->

## Schválení a dodatky

Schváleno uživatelem 4. 10. 2026 („schvaluji plán"). Otisk schváleného
znění (vše nad značkou konce schváleného znění): **SHA-256 `ff5ca38c3c63e2373f65c47bc252a8c520c862e63c4f62e93d65497b5b2617d8`**.
Hlídá ho `tests/test_team_plan.py`. Text nad značkou se už nemění; dodatky
se připisují sem, s datem.

Otázky O1–O5 (pravidla vyhodnocení Tipsportu) zůstávají otevřené. Platí
u nich výchozí předpoklady ze sekce 2, dokud je uživatel nepotvrdí nebo
neopraví; odpověď se zapíše jako dodatek **před** zamrazením modelů
(krok 3). Krok 2 (stažení trestů a rozhodčích) na nich nezávisí — tresty
se ukládají po jednotlivých událostech.

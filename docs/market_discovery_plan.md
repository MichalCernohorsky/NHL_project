# Fáze 0 — plán výběru trhu NHL (CO SÁZET)

**Zapsáno 28. 9. 2026, PŘED nákupem jediného historického kurzu a před
stažením jediného řádku statistik.** Stav: **NÁVRH ke schválení**. Schválení
= uživatelovo „jeď" k nákupu kurzů; v tu chvíli se zapíše otisk SHA-256
tohoto souboru a test ho zapinuje (jako A3/A4 v NBA). Po schválení se text
nemění; případná změna je jen datovaný dodatek na konci a jeho dopad se
vykazuje zvlášť.

**Co tento plán NENÍ.** Není to sázkové pravidlo pro sezónu 2026-27. Jeho
výstupem je jen rozhodnutí, **které 1–2 trhy** postoupí do fáze 1 (data)
a fáze 2 (model a předregistrace). Nic z výsledku fáze 0 se nesází.

## 1. Termíny, ze kterých plán vychází (ověřeno 28. 9. 2026)

| Událost | Termín | Zdroj |
|---|---|---|
| Preseason | 19.–26. 9. 2026 (už proběhla) | nhl.com |
| **Opening night** | **út 29. 9. 2026** (FLA@CAR 23:00 CZ, pak MTL@TOR, NYR@BOS, VAN@EDM, CHI@VGK) | `api-web.nhle.com/v1/schedule/2026-09-29`, nhl.com |
| Základní část | **84 zápasů na tým, 1 344 celkem** (první 84zápasová sezóna) | tamtéž + vlastní sken rozpisu |
| Pauzy bez zápasů | 20. 11., 26. 11., 23.–25. 12., 4.–7. 2. 2027 (All-Star 6. 2.) | sken rozpisu |
| Olympijská / 4 Nations pauza | **není** | sken rozpisu |
| Uzávěrka přestupů | po 1. 3. 2027 (jen média, NHL nepotvrdila) | The Athletic via SI |
| Konec základní části | so 10. 4. 2027 | NHL API |

**Nahlas: sezóna začíná o týden dřív, než počítalo zadání** („začátkem
října"). Na plánu fází to nic nemění — živě se od prvního dne nesází —
ale živý sběr kurzů „od prvního dne" by musel běžet už zítra (sekce 8).

## 2. Kandidátní trhy a pořadí priorit

Klíče ověřené v dokumentaci The Odds API (sport `icehockey_nhl`). Hráčské
propsy mají historii od **3. 5. 2023**, takže sezóna 2025-26 je pokrytá
celá. Historie je po 5 minutách.

| priorita | trh | klíč | kupuje se ve fázi 0 | proč |
|---|---|---|---|---|
| 1 | střely na branku hráče | `player_shots_on_goal` | **ano** | objem (odhad ~10–16 hráčů na zápas, ověří etapa A), hrubé lajny 1,5 / 2,5 / 3,5, TOI a role se dají modelovat, v NBA-analogii „malé číslo, trh daleko od 50 %" (asistence/doskoky daly 7–10 tipů denně) |
| 2 | zásahy brankáře | `player_total_saves` | **ano** | závisí hlavně na střelách soupeře a tempu, ne na identitě brankáře; dvě lajny na zápas, tedy malý objem |
| 3 | zblokované střely | `player_blocked_shots` | **ano** | okrajový, pravděpodobně měkký trh; obránci se stabilní rolí |
| 4 | body / asistence / góly | `player_points`, `player_assists`, `player_goals`, `player_goal_scorer_anytime` | **ne** | 0/1 náhoda, vysoká marže; až po 1–3 |
| 5 | totaly, puck line, moneyline, periody | `totals`, `team_totals`, `spreads`, `h2h`, `*_p1` … | **ne** | ostré trhy; později jen jako data (tempo, favorit), nikdy sázka bez důkazu |

Alternativní lajny (`*_alternate`) se ve fázi 0 **nekupují**: stojí druhý
kredit za trh a pro otázku „porazí naivní model hlavní lajnu?" nejsou
potřeba. Model dává celé rozdělení, takže ocení jakoukoli lajnu, kterou
vypíše Tipsport.

## 3. Kritéria výběru — zapsaná teď, po datech se jen odškrtávají

Trh postoupí do fáze 1, jen když platí **všech pět**:

| # | kritérium | jak se měří | práh |
|---|---|---|---|
| K1 | **Tipsport ho vypisuje** | uživatel ručně, screenshoty (sekce 7) | ve ≥ 3 herních dnech: trh u ≥ 75 % zápasů dne, v průměru ≥ 4 hráči na zápas (u zásahů ≥ 1 brankář na zápas), vypsaný nejpozději v 18:00 CZ |
| K2 | **Data na atributy zdarma a denně** | ověřeno v sekci 5 | TOI, PP TOI, SOG, bloky, zásahy z NHL API; potvrzení brankáře z veřejného zdroje |
| K3 | **Historické kurzy existují a vejdou se do rozpočtu** | výsledek nákupu (sekce 4) | ≥ 300 zápasů vzorku s aspoň jednou closingovou lajnou trhu |
| K4a | **Naivní model není beznadějně za trhem** | Brier na closingových lajnách (sekce 6.3) | Brier modelu − Brier trhu **≤ 0,010** |
| K4b | **Jednoduchý filtr není celý pod nulou** | pravidlo sekce 6.4 na closingu | bodový odhad ROI **> 0** a horní mez 95% CI > 0 |
| K5 | **Objem** | totéž pravidlo | **≥ 3 sázky na herní den** v průměru |

**Postupují nejvýš 2 trhy.** Když projdou všechny tři, rozhoduje pořadí
priorit ze sekce 2 (SOG > zásahy > bloky), **ne** výsledek. Vybírat vítěze
podle nejvyššího ROI by byla přesně „kletba vítěze": nejlepší ze tří
šumových odhadů je vždycky přestřelený.

**Když neprojde žádný trh**, výsledek fáze 0 zní „NHL se v sezóně 2026-27
nesází, jen se sbírají data". Je to platný výsledek, ne selhání.

### 3.1 Jak silná ta kritéria jsou (nahlas, předem)

- **K4a je měkké.** Model bodů v NBA byl na closingu horší o 0,0072
  (0,2535 vs. 0,2463) — tedy by K4a **prošel** — a fixní pravidlo přesto
  dalo −3,3 %. K4a jen vyřazuje beznadějné trhy, ziskovost neprokazuje.
- **K4b je podmínka nutná, ne postačující.** Report proto u každého trhu
  uvede **simulaci nulového efektu** (sekce 6.5): jak často by K4b prošel
  trh, na kterém nemáme žádnou hranu. Hrubý odhad předem — počty sázek
  jsou **předpoklad, ne měření** (kurz ~1,9, marže ~4,5 %, SOG ~1 400
  sázek, bloky ~600, zásahy ~200): nulový trh by prošel K4b s
  pravděpodobností u SOG kolem 4–7 %, u bloků kolem 12 %, u zásahů kolem
  25 %. **Aspoň jeden ze tří nulových trhů by prošel zhruba ve 35–40 %.**
  Proto se o sázení nerozhoduje ve fázi 0, ale až dopředným testem.
- K1 je nejtvrdší filtr a stojí nula kreditů. Proto se **kupuje až po K1**
  (sekce 4.3): trh, který Tipsport nevypisuje, se nekupuje vůbec.

## 4. Rozpočet The Odds API a vzorek

### 4.1 Ceny (dokumentace v4, ověřeno 28. 9.)

- `/historical/sports/{sport}/events` = **1 kredit** za volání (prázdné nic).
- `/historical/sports/{sport}/events/{id}/odds` = **10 × počet vrácených
  trhů × počet regionů**. Trh, který kniha nevrátila, se neplatí.
- Totéž změřila NBA na tomto účtu (10 kreditů na trh a zápas).

### 4.2 Vzorek — rovnoměrný přes sezónu, ne chronologicky

- Populace: základní část **2025-26** (1 312 zápasů). Sezóny 2023-24
  a 2024-25 slouží jen k odhadu konstant naivního modelu (sekce 6.2),
  kurzy se pro ně nekupují.
- Jednotka vzorku je **celý herní den** (zápasy dne sdílejí jeden snímek
  eventů a jednu vlnu zpráv; vybírat uvnitř dne nemáme proč).
- Pořadí dnů: zlatý řez (`spread_order` převzatý z NBA
  `scripts/backfill_props.py`) — jakýkoli začátek pořadí je rovnoměrný
  vzorek sezóny, takže přerušený nákup nenechá jen říjen.
- Dny se berou v tomto pořadí, dokud součet zápasů nedosáhne **330**.
  Deterministické: seznam dnů vypíše `--dry-run` a commitne se před
  nákupem.
- Region `us` (DraftKings, FanDuel, BetMGM, …). Pinnacle (`eu`) se ve
  fázi 0 nekupuje — v NBA kótoval propsy jen řídce.

### 4.3 Etapy a cena

| etapa | co | kdy | kredity (strop) |
|---|---|---|---|
| A | closing (výkop −10 min), jen trhy, které prošly **K1** (max. 3) | po K1 a po „jeď" | 330 × 3 × 10 = **9 900** |
| A | eventy dne (1 volání na herní den vzorku, ~44 dnů) | spolu s A | **~50** |
| B | ranní snímek (10:00 ET = 16:00 CZ, stejná kotva jako NBA), jen **finalisté** po K3–K5 (max. 2) | po reportu etapy A | 330 × 2 × 10 = **6 600** |
| B | eventy ranního snímku | spolu s B | **~50** |
| | **celkem nejvýš** | | **~16 600** |

Etapa B nerozhoduje o postupu (kritéria běží na closingu). Slouží k měření
pohybu lajny a CLV finalistů, jako ranní snímek u NBA doskoků.

**Kontext účtu:** klíč je sdílený (plán 100K/měsíc, reset 1. dne).
NBA živý provoz ~200/den ≈ 6 000/měsíc, NHL živý sběr ~1 500/měsíc
(sekce 8). Nákup proto proběhne **v říjnu z nové kvóty (od 1. 10.)**.
Skript se zastaví při zůstatku pod **15 000** kreditů, aby živé NBA a MLB
nikdy nezůstaly bez kreditů.

## 5. Zdroje dat (K2) — ověřeno 28. 9. 2026

| co | zdroj | stav |
|---|---|---|
| rozpis, výsledky, OT/SO | `api-web.nhle.com/v1/schedule/{datum}` (týden na volání) | ověřeno, zdarma, bez klíče |
| box score (TOI, SOG, bloky, hity, +/-, góly, asistence; brankáři: zásahy, střely proti, start) | `api-web.nhle.com/v1/gamecenter/{id}/boxscore` | ověřeno i pro 2023-24 |
| scratches | `api-web.nhle.com/v1/gamecenter/{id}/right-rail` (`gameInfo.*.scratches`) | ověřeno |
| **PP / EV / SH / OT TOI** | `api.nhle.com/stats/rest/en/skater/timeonice?isGame=true` (jeden herní den na volání) | ověřeno; box score PP TOI **nemá** |
| plná jména, pozice | `api-web.nhle.com/v1/player/{id}/landing`, stats REST | ověřeno |
| xG, střely podle situací | MoneyPuck (data.htm): zdarma **jen nekomerčně a s uvedením zdroje** | ověřeno; 2026-27 denně |
| **potvrzení brankáře** | DailyFaceoff `starting-goalies/{datum}`: archiv od 2021-22, stav „Confirmed" + čas zprávy | ověřeno; archiv drží jen **finální** stav + čas poslední zprávy, ne ranní snímek |
| sestavy, PP jednotky | DailyFaceoff `line-combinations` | ověřeno živě; historický archiv **nenalezen** |

Závěr K2: **splněno** pro všechny tři trhy. Omezení, které se nese dál:
historicky nevíme spolehlivě, co bylo potvrzené *ráno*. Pro fázi 0 to
nevadí (sekce 6.1), pro živý provoz se ranní stav musí od prvního dne
ukládat vlastním snímkem.

## 6. Co se vyhodnotí (a nic jiného)

### 6.1 Časová poctivost atributů

- Všechny atributy zápasu *g* se počítají jen ze zápasů **před** *g*
  (`shift(1)` uvnitř sezóny; prior z minulé sezóny).
- Closingový snímek je 10 min před výkopem — v té době je startující
  brankář známý (rozbruslení). Zásahy se vyhodnocují **jen u brankáře,
  který opravdu začal**; jinak je sázka podle pravidel knih **void**
  (FanDuel: „listed goalie must start"). Tím se neřeší informace, kterou
  by model neměl: podmínka je stejná, jakou vyhodnocuje trh.
- SOG a bloky na identitě brankáře soupeře v naivním modelu nezávisí.

### 6.2 Naivní modely — pevné teď, bez ladění

Společné: TOI_L10 = průměrný čas na ledě v posledních 10 odehraných
zápasech (scratch se nepočítá); ligové průměry a disperze se odhadují
**jen na 2023-24 + 2024-25**; sezóna 2025-26 se k odhadu ničeho nepoužije.
Hráč vstupuje, když má v sezóně před zápasem **≥ 10 odehraných zápasů**
(brankář **≥ 5 startů**) — stejný práh jako NBA.

- **Střely na branku:** μ = r × TOI_L10 × o. r = střely na 60 min
  v sezóně před zápasem, stažené k prioru o váze 3 hodin ledu (prior =
  hráčova minulá sezóna při ≥ 20 zápasech, jinak průměr pozice F/D).
  o = střely povolené soupeřem na zápas (L20) / ligový průměr, stažené
  k 1 s váhou 10 zápasů. Rozdělení: negativní binomické, disperze
  odhadnutá na tréninku.
- **Bloky:** stejný tvar, r = bloky na 60, o = střely soupeře na zápas
  (L20) / ligový průměr (náhrada za pokusy o střelu).
- **Zásahy:** střely proti SA ~ NB se středem 0,5 × (střely soupeře L20)
  + 0,5 × (střely povolené vlastním týmem L20), obojí stažené k lize
  s váhou 10 zápasů, krát podíl zápasu, který startér odchytá (konstanta
  z tréninku). Zásahy | SA ~ Binomial(SA, sv%), sv% = sezóna brankáře
  stažená k ligovému průměru s váhou 600 střel.

PP čas vstupuje přes celkové TOI; oddělené EV/PP rychlosti jsou práce
fáze 2, ne naivního modelu.

### 6.3 Brier proti trhu (K4a)

- Jedna řádka = (zápas, hráč, trh) na **hlavní lajně** = lajna, kterou
  kotuje nejvíc knih (při shodě nižší).
- p_trh = medián proporcionálně odšťavené P(over) přes knihy, které na té
  lajně kotují obě strany. p_model = P(X > lajna) z rozdělení.
- Brier obou nad týmiž řádkami, push (celočíselná lajna) mimo, void mimo.
  Rozdíl s bootstrap 95% CI (převzorkují se herní dny).

### 6.4 Filtr ROI (K4b, K5) — jediný

- Kandidát = (zápas, hráč, trh, lajna, strana, kniha) s oběma stranami
  kotovanými; p_trh = de-vig téže knihy.
- **Sázka, když p_model − p_trh ≥ 3 p.b.** (stejný práh jako NBA). Na
  (zápas, hráč, trh) nejvýš **jedna** sázka: strana s větší hranou, u ní
  nejlepší kurz.
- Vyhodnocení za closingový kurz, flat 1 jednotka, push vrací vklad
  a je mimo ROI, void mimo. Pravidla vypořádání jako u knih: OT se
  počítá, nájezdy ne; hráč bez času na ledě = void.
- ROI s bootstrap 95% CI: **10 000 opakování, seed 17, převzorkují se
  herní dny** (sázky jednoho dne nejsou nezávislé). K tomu hit %,
  break-even % při průměrném kurzu, sázky na herní den.

### 6.5 Simulace nulového efektu (povinná součást reportu)

Pro každý trh 2 000 simulací, ve kterých je **pravda = trh**: výsledek
každé řádky se losuje z p_trh (de-vig), p_model a výběr sázek zůstanou.
Reportuje se, v kolika procentech simulací by trh prošel K4b. Totéž pro
„aspoň jeden ze tří trhů". Bez tohoto čísla se výsledek K4b nečte.

### 6.6 Co se NEvyhodnotí

- Žádné řezy podle atributů (pozice, doma/venku, výška lajny, tým, b2b,
  PP role…). V NBA dalo 32 řezů „významný" výsledek v 56 % simulací bez
  efektu; zde se to neopakuje.
- Žádné jiné prahy hrany než 3 p.b., žádné kategorie podle p_model,
  žádné druhé modely. Kalibrační tabulka modelu (decily) je jen
  diagnostika a o postupu nerozhoduje.
- Trhy 4 a 5 se nekupují a nevyhodnocují.
- Když výsledek „skoro" projde, neprošel. Druhé kolo s jinými parametry
  se nekoná.

## 7. Kontrola Tipsportu (K1) — úkol pro uživatele

Ve **3 různých herních dnech** (ideálně 29. 9., 1. 10. a sobota 3. 10.,
kdy je 13 zápasů) screenshoty nabídky NHL v Tipsportu:

1. Seznam zápasů dne a u každého, jestli má hráčské sázky.
2. **Střely na branku hráče:** kolik hráčů na zápas, které lajny (0,5 /
   1,5 / 2,5 / 3,5…), obě strany (více/méně), nebo jen „více".
3. **Zásahy brankáře:** u kolika zápasů, jestli pro oba brankáře.
4. **Zblokované střely:** vypsané vůbec? U kolika hráčů?
5. **Čas:** kdy nabídka hráčských sázek naskočí (screenshot kolem 16:00
   a kolem 20:00 CZ téhož dne).
6. **Pravidla:** v pravidlech Tipsportu pro hokej, zda hráčské statistiky
   NHL počítají prodloužení a nájezdy, a co se stane, když brankář
   nenastoupí.
7. Kurzy obou stran u 2–3 hráčů (na odhad marže Tipsportu).

## 8. Živý sběr kurzů od prvního dne

Živá volání stojí **počet vrácených trhů × regiony** (bez násobku 10).
Tři kandidátní trhy, ranní + closingový snímek: ~6 kreditů na zápas,
**~50 na herní den, ~1 500 měsíčně**. Nerozhoduje o ničem ve fázi 0 —
jen dataset roste a fáze 2 bude mít živé lajny sezóny 2026-27. Ranní
snímek potvrzení brankářů se ukládá od prvního dne stejně (zdarma).

## 9. Harmonogram

| kdy | co |
|---|---|
| 28. 9. | tento plán commitnutý; kód pro rozpis a box score |
| 29. 9. – 3. 10. | uživatel: kontrola Tipsportu (K1); stažení box score 2023-24 až 2025-26 |
| od 1. 10., po „jeď" | etapa A (closing, jen trhy po K1) |
| do ~15. 10. | naivní modely, `docs/market_discovery_report.md` |
| po reportu | etapa B (ranní snímek finalistů), verdikt fáze 0 |
| listopad | fáze 1: data, atributy „k ránu", test úniku informací |
| listopad – prosinec | fáze 2: model, předregistrace, git tag |
| **od 1. 12. 2026, nejpozději 4. 1. 2027** | předregistrovaný dopředný test do 10. 4. 2027 |

**Kapacita sázkaře:** NBA už dává ~17 tiketů denně. Když NHL projde,
předregistrace fáze 2 smí zavést strop tipů na den nebo přísnější práh —
ale jen předem zapsaný, nikdy podle výsledků.

## 10. Známá omezení (zapsaná předem)

- Jedna sezóna kurzů (2025-26), 330 zápasů, jeden snímek pro kritéria.
- „Trh" = americké knihy v The Odds API; o marži a lajnách Tipsportu
  neříká nic — proto K1 a proto se v provozu hodnotí kurz z tiketu.
- Sázky jednoho zápasu jsou korelované (sdílené tempo); bootstrap po
  dnech to částečně pokrývá, ne úplně.
- Naivní model je schválně jednoduchý. Neprojde-li, neznamená to, že trh
  nejde porazit — jen že fáze 0 k tomu nedala důvod.

## 11. Dodatky

### D1 — vyhodnocení za kurz Tipsportu (29. 9. 2026, před schválením a před nákupem)

**Zjištění.** První screenshot Tipsportu (FLA@CAR, 29. 9.): „Počet střel
hráče na branku v zápasu" u 6 hráčů, obě strany, lajny 1,5 / 2,5. Marže
každé z šesti dvojic kurzů je **8,70–8,80 %** (např. 1,84 / 1,84 →
8,70 %). Týmové střely mají 7,5–7,6 %. Zásahy brankáře ani zblokované
střely v nabídce zápasu nebyly.

**Díra v plánu.** K4b a K5 (sekce 3, 6.4) vyhodnocují ROI za closingový
kurz amerických knih, jejichž marže je u propsů zhruba 4,5–7 %. Sázkař ale
sází za kurz Tipsportu. Trh by mohl K4b splnit a u Tipsportu prodělávat —
metrikou projektu je reálný zisk, ne zisk v knize, kde se nesází.

**Změna (jediná):**

- **Výběr sázek se nemění** (hrana ≥ 3 p.b. proti de-vig téže knihy,
  jedna sázka na (zápas, hráč, trh)) — stejně jako NBA, kde se hrana
  u Tipsportu přepočítává přes de-vig jeho dvou kurzů.
- **Výplata v K4b a K5 = simulovaný kurz Tipsportu:**
  kurz_T = 1 / (p_trh × (1 + m)), kde p_trh je de-vig closing téže strany
  a lajny (sekce 6.3) a m je marže Tipsportu.
- **m se zafixuje před nákupem** jako medián marže všech hráčských dvojic
  daného trhu ze screenshotů K1 (3 herní dny). Zapíše se sem jako číslo
  s datem. Do té doby platí odhad m = 0,087.
  **Zafixováno 10. 10. 2026 (dodatek D8): m = 0,0874** (medián 108 dvojic kurzů
  ze 4 herních dnů, rozsah 8,64–8,82 %; `docs/tipsport_k1_log.md`).
- ROI za kurz amerických knih se v reportu uvádí dál, ale jen jako
  **vedlejší** údaj; o postupu rozhoduje ROI za simulovaný kurz Tipsportu.
- Simulace nulového efektu (6.5) se počítá se stejnou výplatou.

**Co to znamená předem (nahlas).** Při m = 8,7 % a kurzu kolem 1,84 je
break-even 54,3 %. Sázka s hranou přesně 3 p.b. proti férové ceně je
u Tipsportu v průměru ztrátová (≈ −2,5 %); zisk dají jen sázky, kde je
skutečná hrana nad ~4,4 p.b. Práh 3 p.b. se přesto **nemění**: jeho
zvednutí by byl další parametr volený podle očekávaného výsledku. Je
pravděpodobnější, že fáze 0 skončí „nesázet". To je platný výsledek.

**Co D1 nezachytí.** Hodnotu z toho, že Tipsport přebírá lajny se
zpožděním (zastaralá lajna proti americkému konsensu). Historická data
Tipsportu nemáme, takže to fáze 0 změřit neumí; pokud trh projde, měří to
až dopředný test na kurzech z tiketů.

**Co D1 nemění.** Kandidátní trhy, prahy K1–K5, vzorek, rozpočet, naivní
modely, práh hrany, co se nevyhodnotí.

### D2 — objem (K5) podle počtu hráčů, které Tipsport vypisuje (29. 9. 2026, před schválením a před nákupem)

**Zjištění.** 29. 9. vypsal Tipsport střely hráče u všech 5 zápasů, vždy
**6 hráčů na zápas** (3 za tým, typicky 2 útočníci a 1 obránce;
`docs/tipsport_k1_log.md`). Americké knihy kotují víc hráčů na zápas,
takže K5 spočítaný z nich by nadsadil počet tipů, které lze u Tipsportu
podat.

**Změna (jediná):** K5 = sázky na herní den **× (6 / průměrný počet
hráčů na zápas s lajnou trhu v closingu vzorku)**. Číslo 6 se po
3 herních dnech K1 nahradí průměrem z `docs/tipsport_k1_log.md` a zapíše
se sem s datem, před nákupem.
**Zafixováno 10. 10. 2026 (dodatek D8): 6 hráčů na zápas** (22 zápasů z 22).

**Co D2 záměrně NEdělá.** Nevybírá „tipsportovou" podmnožinu hráčů pro
ROI (K4b). Historicky nevíme, které tři hráče by Tipsport vypsal, a
pravidlo typu „dva útočníci s nejvyšší lajnou + obránce" by byl filtr
vymyšlený teď bez možnosti ověření. ROI se proto měří na všech hráčích;
omezení: Tipsport vypisuje hlavně nejlepší hráče, u kterých byl v NBA
model nejvíc přeceněný (hvězdy: tvrdí 52 %, trefí 38 %) — pokud trh
projde, ukáže to až dopředný test.

**Co D2 nemění.** Nic dalšího; D1 platí.

### D3 — Tipsport vyhodnocuje hráčské střely za 60 minut (29. 9. 2026, před schválením a před nákupem)

**Zjištění.** Uživatel ověřil v pravidlech Tipsportu: „Počet střel hráče
na branku" se vyhodnocuje za **60 minut, bez prodloužení**. Americké
knihy počítají prodloužení (FanDuel: základní doba + OT, bez nájezdů).
Změřeno na našich datech: do prodloužení jde 20,7 / 20,7 / 24,8 %
zápasů (2023-24 / 2024-25 / 2025-26), v prodloužení padne 1,28 / 1,27 /
1,65 % všech střel na branku. U lajny 2,5 to posouvá P(více) řádově
o 1–2 p.b. — srovnatelně s prahem hrany 3 p.b. Bez opravy by fáze 0
mohla „najít hranu" na undrech jen z rozdílu pravidel.

**Změny:**

1. **Vypořádání v K4b a K5 (za kurz Tipsportu) = střely za 60 minut**
   (třetiny 1–3 z play-by-play, `player_game_logs.sog_reg`; nájezdy ani
   bloky spoluhráčem se nepočítají, každý zápas ověřen proti box score).
2. **Naivní model predikuje střely za 60 minut**: rychlost = střely za
   60 min / čas na ledě bez prodloužení (`toi_s − ot_toi_s`). Plné
   rozdělení (s prodloužením) se odvodí jako μ_plné = μ_60 × (1 + r),
   kde r = poměr střel v prodloužení ke střelám za 60 minut u hráčů téže
   pozice (útočník / obránce), odhadnutý jen na 2023-24 + 2024-25.
   μ_plné slouží jen pro K4a (Brier proti americkému trhu, který
   prodloužení počítá — vypořádání K4a zůstává plné, jako u trhu).
3. **Převod trhu na 60 minut (konzervativně):** z de-vig P(více) americké
   knihy se dopočte střední hodnota μ_trh tak, aby negativně binomické
   rozdělení (disperze z tréninku) dávalo tutéž P(více); pak
   μ_trh_60 = μ_trh / (1 + r) a p_trh_60 = P(více) při μ_trh_60. Výběr
   sázky: p_model_60 − p_trh_60 ≥ 3 p.b.; simulovaný kurz Tipsportu
   (D1) = 1 / (p_trh_60 × (1 + m)). Tím se předpokládá, že Tipsport
   naceňuje 60 minut správně — rozdíl pravidel tedy nedá žádnou „hranu
   zadarmo".
4. **Jestli Tipsport 60 minut opravdu naceňuje, nebo přebírá americké
   kurzy**, se měří až dopředu (živé americké snímky vs. screenshoty
   Tipsportu) a je to jen diagnostika — ve fázi 0 nic nemění.

**Co D3 nemění.** Kandidátní trhy, prahy K1–K5, vzorek, rozpočet, práh
hrany, D1, D2, co se nevyhodnotí.

### D4 — kurzy živé sezóny se kupují den poté z archivu (2. 10. 2026, před schválením a před nákupem)

**Zjištění.** Sekce 8 počítala s živými snímky (ranní 10:00 ET, closing
10 min před zápasem) za 1 kredit na trh. Obojí potřebuje spuštění v přesný
čas. Mac snímky ztrácí, když spí (30. 9.–2. 10. přišel o všechny closingy),
a GitHub Actions spouštěl plán „každých 10 minut" jen jednou za 3–6 hodin
(změřeno 29. 9.–2. 10., ~7 % běhů).

**Změna (rozhodl uživatel 2. 10., varianta C):** cloudový denní běh
kupuje snímky **včerejška z historického archivu The Odds API** přesně
v kotvách z plánu (10:00 ET; začátek zápasu −10 min), stejným kódem jako
vzorek 2025-26 (`src/nhl_tool/hist_odds.py`, `scripts/buy_snapshots.py`).
Okno 7 dní zpět, takže zmeškaný běh se dožene; zápas, který už má snímek
daného druhu (živý sběr Macu do 2. 10.), se nekupuje znovu.

**Cena (nahlas):** 10 kreditů za trh, který kniha opravdu vypíše.
Změřeno na živých datech: ranní snímek 1,12 trhu na zápas, closing 2,00
(střely + zásahy; bloky nevypisuje nikdo, neplatí se). **~31 kreditů na
zápas, ~227 na herní den, ~6 500 měsíčně, ~42 000 za základní část**
(1 344 zápasů). Kdyby po K1 vypadly zásahy brankáře, ~21 na zápas.
Jednorázově dohnat 29. 9.–1. 10.: odhad 279 kreditů.

**Spouští se až po „jeď"** (`odds.hist_daily_enabled`), samostatným
commitem.

**Co D4 nemění.** Nic z výběru trhu (K1–K5, vzorek 2025-26, modely, práh).
Živé snímky nikdy nerozhodovaly o fázi 0; jen se mění, jak a za kolik se
sbírají.

**D4, upřesnění 2. 10. 2026 — „jeď" jen pro střely hráčů.** Uživatel
schválil nákup s omezením na `player_shots_on_goal`
(`odds.hist_daily_markets`). Zásahy brankáře a bloky Tipsport ve 2 dnech
nevypsal; trh „střely týmu", který Tipsport vypisuje, The Odds API nemá.
Suchý běh před zapnutím: dohnat 29. 9.–1. 10. = 16 snímků, **163 kreditů**;
průběžně **~20 kreditů na zápas, ~145 na herní den, ~4 200 měsíčně,
~27 000 za základní část**.

### D5 — tipy v dashboardu od fáze 0 (2. 10. 2026, před kódem)

Na přání uživatele se tipy vypisují už teď (jako MLB/NBA; sázka je jen to,
co uživatel označí „vsazeno"). Plný plán: `docs/tips_plan.md`. Tipy
dává **naivní model ze sekce 6.2** se zamrazenými konstantami (odhad jen na
2023-24 + 2024-25, otisk před etapou A) a **pravidlo ze sekce 6.4**.
Živý snímek pro tipy (`snapshot_kind = 'live'`, ~200 kreditů měsíčně) je
mimo předregistrované snímky.

**Co D5 nemění:** verdikt fáze 0 se počítá jen z 2025-26 podle sekcí 3
a 6. Záznam živých tipů ho neovlivní a podle něj se nic neladí; vykazuje
se zvlášť.

### D6 — živé tipy od začátku sezóny (2. 10. 2026, před kódem)

**Na přání uživatele** se živé tipy (D5) nemají odkládat na konec října.
Pro **živé tipy** platí vstupní podmínka: hráč má v sezóně ≥ 10
odehraných zápasů **nebo** ≥ 20 zápasů v minulé sezóně. Model zůstává
přesně podle 6.2: rychlost střel se stahuje k prioru z minulé sezóny
(u hráče bez letošních zápasů je to prior sám), TOI_L10 je průměr posledních
10 odehraných zápasů i přes hranici sezón, faktor soupeře se stahuje k 1.

**Riziko, zapsané předem:** začátek sezóny je pro model nejslabší —
změny rolí po létě, přestupy, nové lajny; v NBA vyšel říjen jako měsíc
nejhorší shody s trhem (ROI brzké sezóny −7,3 %). Tipy jsou papír, dokud
je uživatel neoznačí „vsazeno"; doporučení zůstává: skutečné peníze až po
verdiktu fáze 0.

**Co D6 nemění:** vyhodnocení fáze 0 na 2025-26 (sekce 6) dál bere jen
hráče s ≥ 10 zápasy v sezóně. Pravidlo 6.4, konstanty modelu, zamrazení
před etapou A — beze změny.

### D7 — K1 se ověřuje na vylosovaných zápasech (10. 10. 2026, na žádost uživatele, před schválením a před nákupem)

**Proč.** K1 žádá trh u ≥ 75 % zápasů dne ve ≥ 3 dnech. V den se 14 zápasy
to znamená ručně projít 11 zápasů. Dosavadní kontroly přitom vyšly
pokaždé stejně: 29. 9., 2. 10. a 4. 10. všech 15 zápasů, 10. 10. první
zkontrolovaný — **16 zápasů z 16, vždy 6 hráčů**. Kdyby Tipsport trh
vypisoval jen u 75 % zápasů, vyšlo by 16 z 16 v 1 % případů.

**Změna (jen způsob ověření, ne práh).** Den se do K1 započte, když
uživatel **do 18:00 CZ** zkontroluje **5 zápasů dne vylosovaných předem**
(má-li den nejvýš 5 zápasů, všechny) a trh je vypsaný u všech z nich,
v průměru ≥ 4 hráči na zápas. Los: zápasy dne seřazené podle `game_id`,
`numpy.random.default_rng(RRRRMMDD).choice(n, 5, replace=False)` — pevné
pravidlo, aby výběr nezávisel na tom, které zápasy jsou zrovna po ruce
(pozdní zápasy mohou naskočit později). Stačí sdělení uživatele (počet
hráčů u každého z nich); screenshot není nutný a do protokolu se to tak
zapíše. Když u některého vylosovaného zápasu trh chybí, den se nepočítá
a platí původní pravidlo (≥ 75 % všech zápasů dne).

**Co D7 nemění.** Prahy K1 (75 %, ≥ 4 hráči, 18:00, 3 dny), ostatní
kritéria K2–K5, vzorek, rozpočet, model, práh hrany. K1 je kontrola
proveditelnosti („dá se to u Tipsportu vsadit?"), ne ziskovosti; žádný
výsledek o zisku se tím neovlivní.

### D8 — K1 uzavřeno na dosavadních kontrolách (10. 10. 2026, na žádost uživatele, před schválením a před nákupem)

**Stav kontrol Tipsportu (střely hráče):**

| den | zápasů dne | zkontrolováno | trh vypsaný | hráčů na zápas | čas kontroly |
|---|---|---|---|---|---|
| 29. 9. | 5 | 5 | 5 z 5 | 6 | ~20:00 CZ |
| 2. 10. | 5 | 5 | 5 z 5 | 6 | ~21:30 CZ |
| 4. 10. | 5 | 5 | 5 z 5 | 6 | 13:05–13:20 CZ |
| 10. 10. | 14 | 7 (5 vylosovaných podle D7 + 2) | 7 ze 7 | 6 | 15:55–16:15 CZ |

Pokrytí (≥ 75 % zápasů dne) a počet hráčů (≥ 4) jsou splněné ve **4 dnech**
(práh 3). Podmínka „nejpozději v 18:00 CZ" je ověřená ve **2 dnech**; v obou
byl trh vypsaný 2–5 hodin před 18:00, i u zápasů začínajících po půlnoci.

**Změna.** Třetí den s kontrolou do 18:00 se nevyžaduje; **K1 se pro střely
hráče považuje za splněné.** Důvod: další den by nepřinesl informaci —
kdyby Tipsport trh vypisoval jen u 75 % zápasů, vyšlo by 22 zápasů z 22
v 0,2 % případů.

**Co se tím vzdává (nahlas).** Jedna ze tří časových kontrol. K1 je kontrola
proveditelnosti („dá se to u Tipsportu vsadit?"), ne ziskovosti; žádný
výsledek o zisku se tím neovlivní. Kritéria K2–K5, vzorek, rozpočet, model
a práh hrany beze změny.

**Ostatní kandidátní trhy K1 nesplnily:** zásahy brankáře a zblokované
střely Tipsport nevypisuje (kontroly 29. 9. a 2. 10.). Kupují se proto jen
střely hráče (`player_shots_on_goal`), jeden trh: etapa A = 330 zápasů ×
1 trh × 10 + 42 volání seznamu zápasů = **nejvýš 3 342 kreditů**.

**Zafixováno před nákupem:** marže Tipsportu pro D1 **m = 0,0874**; počet
hráčů na zápas pro D2 **6**.

### Zamrazení naivního modelu střel (2. 10. 2026, před nákupem etapy A)

`models/naive_sog.json`, **SHA-256 `87b23226a866a86c82b42086d6a691a7d3da56c0e73e7e28852485f0d9fb08c2`**.
Kód `src/nhl_tool/naive_sog.py` (commit 4702a61, výklad předpisu
`docs/naive_model.md` commitnutý před prvním výpočtem), odhad
`scripts/fit_naive_sog.py` jen na 2023-24 + 2024-25 (77 910 řádků). Od teď
se nemění; jiný otisk = někdo model přepočítal. Test to hlídá.

Konstanty: tým 28,90 střel za 60 min na zápas; prior útočník 7,010 /
obránce 4,124 střel na 60 min ledu; podíl prodloužení F 1,37 % / D 1,08 %;
disperze k = 16,84 (věrohodnost NB −122 127,5 vs. Poisson −122 318,0).

**Známá vlastnost, zapsaná před pohledem na 2025-26:** v tréninku model
nadhodnocuje střely o 2,4 % (1,668 vs. 1,629 na zápas; zápasy 11–30
+3,3 %, 56+ +1,7 %). Čas na ledě sedí (poměr 0,9997); nadhodnocená je
rychlost střelby, protože liga mezi tréninkovými sezónami střílela méně
(79 463 → 74 179 střel, −6,7 %) a prior z minulé sezóny nese starší
úroveň. Mezi 2024-25 a 2025-26 byl pokles 1,6 %, takže na validaci se
čeká menší posun. **Neladí se** (6.2: „pevné teď, bez ladění"); posun
k overům se projeví ve výsledku fáze 0 a v reportu se uvede.

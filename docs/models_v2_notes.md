# Modely v2 — výklad zadání (před prvním odhadem)

Plán: `docs/models_v2_plan.md` (schválen 10. 10. 2026). Tento soubor převádí
plán na přesné vzorce a pevně volí vše, co plán nechává otevřené. **Zapsáno
a commitnuto před prvním odhadem a před jakýmkoli pohledem na výsledek
verze 2 na sezóně 2025-26.** Po odhadu se nemění; opravy jen jako datované
dodatky na konci.

## 1. Společné

- Trénink 2023-24 + 2024-25, ověření 2025-26. Všechno, co předpověď zápasu
  používá, pochází ze zápasů **s dřívějším datem**.
- Z verze 1 se **nepřeodhaduje** nic: L_t, forma, w, c, h u týmů
  (`models/naive_team.json`); váha 3 hodiny ledu, okna 10 a 20 zápasů,
  podíl střel v prodloužení u hráčů (`models/naive_sog.json`). Verze 2
  odhaduje jen nové koeficienty a nový rozptyl k.
- **Odhad:** maximální věrohodnost negativně binomického rozdělení
  s logaritmickou vazbou, ln μ = ln μ_základ + X·β (bez volného členu —
  úroveň drží základ). β Newtonovou metodou, k zlatým řezem, střídavě do
  ustálení. Koeficienty vstupující nelineárně (α, π) z pevné mřížky:
  vybere se bod s nejvyšší věrohodností.
- **Pokusy o střelu a rozdělení podle počtu hráčů** z tabulky
  `player_shot_splits`. „Přesilovka" = střílející tým má víc hráčů v poli
  a oba brankáři jsou v brance; vše ostatní (plný počet, oslabení, hra bez
  brankáře) je „mimo přesilovku".
- **Druhý den po sobě (b2b):** tým hrál zápas základní části předchozí
  kalendářní den (`game_date` − 1). Přípravné zápasy a play-off se
  nepočítají (v databázi nejsou úplné).
- **Očekávané přesilovky týmu T proti soupeři S** — z faktorů zamrazeného
  modelu trestů verze 1 (w = 30, c = 0,6): E = faulování_S × vynucování_T,
  kde faulování_S je faktor „útok" soupeře (jeho vlastní dvouminutové
  tresty proti lize) a vynucování_T faktor „obrana" týmu (tresty soupeřů
  týmu T proti lize). Bez domácího faktoru. E = 1 je ligový průměr.

## 2. Týmy, blok A

    μ_A = μ_základ(α) × exp(γ·D + φ₁·F₁ + φ₂·F₂ + β₁·B_tým + β₂·B_soupeř)

- **μ_základ** = vzorec verze 1 (L_t × útok × obrana soupeře × h^±1)
  s konstantami verze 1.
- **(1) pokusy, jen S-T:** forma útoku i obrany před vstupem do faktoru
  = (1 − α) × forma ze střel + α × forma z pokusů × (L_t střel / L_t
  pokusů); obě L_t jsou klouzavé ligové průměry jako ve verzi 1 (400
  řádků; při méně než 100 průměr tréninku). Loňský výchozí bod zůstává ze
  střel. α z mřížky 0; 0,1; …; 1. U T-T je μ_základ = verze 1.
- **(2) přesilovky:** D = L_t trestů × (E − 1), tedy odchylka očekávaného
  počtu přesilovek týmu od ligy v kusech. Stejný vzorec pro S-T i T-T
  (u T-T říká, kolik fauluje soupeř a kolik tým fauly vynucuje — to ve
  verzi 1 není).
- **(5) fáze sezóny:** F₁ = 1 pro 1.–10. zápas týmu v sezóně, F₂ = 1 pro
  11.–20.; od 21. obě 0.
- **(6) odpočinek:** B_tým, B_soupeř = 1, když tým / soupeř hraje druhý
  den po sobě.
- **Rozptyl:** S-T negativně binomické, nové k. T-T: pravděpodobnost „více
  než 3,5 / 4,5" logistickou kalibrací na ln μ_A (stejný postup jako
  dodatek T-4, odhad na tréninku).
- Trénovací řádky: všechny týmové řádky tréninkových sezón, u kterých jsou
  úplné střely, pokusy i tresty (stejné řádky pro v1 i v2).

## 3. Rozhodčí, blok R (jen T-T)

    μ_R = μ_A × exp(ρ·R)

- Pro rozhodčího j a zápas s datem t: n_j = počet jeho dřívějších zápasů
  základní části v databázi (od 2023-24, přes hranice sezón), odchylka
  zápasu = součet dvouminutových trestů obou týmů (pravidlo T-1) − 2 × L_t
  toho zápasu. d_j = součet odchylek / (n_j + 30).
- R = průměr d_j přes hlavní rozhodčí zápasu (dva; je-li uveden jeden,
  ten jeden). Čároví se nepoužívají.
- ρ se odhadne při pevných koeficientech bloku A; kalibrace 3,5 / 4,5
  znovu na ln μ_R. Blok R se teď počítá nad blokem A; kdyby blok B nahradil
  A, přepočítá se nad B.
- Vykazuje se rozdíl ztrát A − R na 2025-26 s intervalem. Je to popis
  (v historii jsou rozhodčí známi vždy), o nasazení nerozhoduje.

## 4. Vyhodnocení týmů na 2025-26

- **S-T:** ztráta řádku = −ln P(skutečný počet). Verze 1: μ a k verze 1.
  Verze 2: μ_A a nové k.
- **T-T:** ztráta = −ln P(co nastalo) na lajnách 3,5 a 4,5, obě lajny
  pod sebou (jako report T-4). Verze 1: μ verze 1 + zamrazená kalibrace
  T-4. Verze 2: μ_A + nová kalibrace.
- Rozdíl ztrát v1 − v2, průměr přes řádky, bootstrap 95 % (seed 17,
  10 000, herní dny). **A nahradí v1, když je celý interval nad nulou** —
  pro každý trh zvlášť.
- **Síla a nulový efekt** (500 simulací, stejná bootstrap losování):
  (a) *pravdou je v1* — počty se losují z rozdělení verze 1; podíl
  simulací, kde by v2 „nahradila" (falešný poplach); (b) *pravdou je v2*
  — počty z rozdělení verze 2; podíl, kde by nahradila (síla testu).
  U T-T se losuje výsledek ze tří pásem (≤ 3, právě 4, ≥ 5) podle
  kalibrovaných pravděpodobností dané verze.
- Popis: kalibrace v pěti pásmech; průměr předpověď × skutečnost zvlášť
  pro říjen, listopad a zbytek sezóny; koeficienty s jejich významem.
- Nic se podle výsledku neupravuje. „Skoro" znamená ne.

## 5. Hráči, blok A

    μ₆₀ = (r_mimo × t_mimo × o_mimo + r_přes × t_přes × E^π × o_osl)
          × exp(β₁·B_tým + β₂·B_soupeř)

Index „mimo" = mimo přesilovku, „přes" = v přesilovce.

- **Časy:** t_přes = čas v přesilovce (`pp_toi_s`, nejvýš čas za 60
  minut), t_mimo = čas za 60 minut − t_přes. Do modelu průměr posledních
  10 odehraných zápasů (přes hranici sezón), každý zvlášť. (Čas
  v přesilovce z NHL zahrnuje vzácné přesilovky v prodloužení — zanedbáno.)
- **Střelba za sekundu** v situaci x: ze střel r^S_x a z pokusů r^A_x,
  každá = (počet v sezóně před zápasem + výchozí × W_x) / (čas v sezóně
  před zápasem + W_x). W_x = 3 hodiny × podíl situace x na čase ledu
  v tréninku (stejné stažení v zápasech jako verze 1).
- **Výchozí rychlost:** hráč s ≥ 20 zápasy v předchozí sezóně: (loňský
  počet + rychlost pozice × W_x) / (loňský čas + W_x); jinak rychlost
  pozice (útočník / obránce) z tréninku. (Verze 1 brala loňskou rychlost
  syrovou; v přesilovce je loňský čas krátký, proto stažení.)
- **r_x** = (1 − α) × r^S_x + α × r^A_x × q_x, kde q_x = střely / pokusy
  dané pozice a situace v tréninku. α z mřížky 0; 0,1; …; 1 (jedno pro obě
  situace).
- **E^π:** E jako v sekci 1; π z mřížky 0; 0,25; …; 2.
- **Soupeř:** o_mimo = střely, které soupeř povolil mimo svá oslabení, na
  zápas za posledních ≤ 20 zápasů sezóny / ligový průměr tréninku, stažené
  k 1 vahou 10 zápasů (jako verze 1). o_osl = střely povolené v oslabení
  na jeden vlastní dvouminutový trest (pravidlo T-1) za stejné okno /
  ligový poměr tréninku, stažené k 1 vahou 10 zápasů; bez trestu v okně
  = 1.
- **Odpočinek:** jako u týmů, vlastní koeficienty.
- **Rozptyl:** negativně binomické, nové k. Odhad na řádcích tréninku se
  vstupem fáze 0 (≥ 10 zápasů hráče v sezóně), jako verze 1.
- Celý zápas (pro srovnání s americkým trhem): μ_celý = μ₆₀ × (1 + podíl
  střel v prodloužení) z verze 1.

## 6. Vyhodnocení hráčů

- Jen na **330 zápasech** s nakoupenými kurzy; zbylých ~980 zápasů
  2025-26 se u hráčů neotvírá vůbec (ani výsledky), aby zůstaly čisté pro
  případné potvrzení.
- Stejný kód a kritéria jako fáze 0 (`src/nhl_tool/phase0.py`): K4a
  (Brier proti trhu, hlavní lajna, celý zápas, mez 0,010), K4b (hrana
  ≥ 3 p. b., simulovaný kurz Tipsportu s m = 0,0874, 60 minut, ROI
  s intervalem), K5, simulace „pravdou je trh". Přepočet trhu na 60 minut
  používá k hodnoceného modelu, jako ve fázi 0.
- Navíc: rozdíl Brier v1 − v2 na stejných řádcích s intervalem; simulace
  „pravdou je model v2" (výsledky sázek losované z pravděpodobností
  modelu) jako odhad síly K4b; verze 1 se přepočítá vedle pro kontrolu,
  že sedí s `docs/phase0_report.md`.
- **Verdikt podle plánu:** K4b splněno = ROI > 0 (jako fáze 0). Nesplní-li
  ho blok A ani blok B, hráčský model končí.

## 7. Zamrazení

Koeficienty do `models/team_v2.json` a `models/player_v2.json`; otisk
SHA-256 do dodatku plánu **před** spuštěním reportů na 2025-26. Skripty
odmítnou zamrazený soubor přepsat.

## Dodatky

**N-1 (10. 10. 2026, před prvním odhadem a před jakýmkoli výsledkem na
skutečných datech): volný člen.** Sekce 1 říkala „bez volného členu". Test
na umělých datech s podstrčeným efektem (`tests/test_player_v2.py`) ukázal,
že bez něj se efekt neodhadne správně: základ verze 1 už obsahuje průměr
přes odpočaté i unavené zápasy, takže koeficient „druhý den po sobě" vyjde
menší a zbytek se přelije do ostatních koeficientů. Proto má blok A u týmů
i hráčů navíc volný člen c₀ (sloupec jedniček):

    ln μ = ln μ_základ + c₀ + X·β

Blok R (ρ) volný člen nepřidává — odhaduje se nad pevným blokem A a R má
průměr u nuly. Nic jiného se nemění.

**N-2 (10. 10. 2026, před nákupem hlavních kurzů): přesná podoba atributu
(4) a bloku B.**

- Data: tabulka `main_odds`, snímek archivu v 15:00 UTC herního dne.
  Použijí se jen zápasy, které v čase snímku ještě nezačaly, a jen knihy
  kotující obě strany.
- **Pravděpodobnost výhry** týmu: u každé knihy poměrné odstranění marže ze
  dvou kurzů na vítěze zápasu (včetně prodloužení); medián přes knihy.
- **Čekaný počet gólů** zápasu G: u každé knihy lajna počtu gólů
  a P(více) bez marže → střední hodnota Poissonova rozdělení, při které
  P(více než lajna) vyjde stejně (u celé lajny se remíza s lajnou
  vynechává); medián přes knihy.
- Obojí jen při **alespoň 3 knihách**; jinak zápas atribut nemá a blok B
  se pro něj rovná bloku A.
- g = G − průměr G v trénovacích sezónách (jedna konstanta v modelu).
- **Blok B** = pevný blok A × exp(δ₀ + δ₁ × (p_výhry − 0,5) + δ₂ × g),
  δ odhadnuté nad pevnými koeficienty bloku A (jako ρ u bloku R) jen na
  trénovacích řádcích s kurzy, nové k; u T-T nová kalibrace na ln μ_B.
  Stejně u hráčů (p_výhry týmu hráče), vlastní δ.
- Vyhodnocení B proti A stejnou ztrátou a pravidlem jako A proti v1;
  u hráčů znovu kritéria fáze 0.

**N-3 (11. 10. 2026, před kódem): opravy statistik NHL po zápase.**

- **Nález (10. 10. 2026).** Kontrola kroku 0 (střely na branku za 60 minut
  z pokusů = uložené `sog_reg`) neprošla u 9 ze 70 zápasů sezóny 2026-27
  (2026020010, 027, 028, 035, 037, 050, 052, 068, 069), vždy o 1 střelu
  u 1–2 hráčů. Všech 3 936 zápasů tří historických sezón prošlo. NHL
  statistiky po zápase opravuje, kdežto box score a play-by-play živé
  sezóny se stáhly jednou a už nikdy znovu. Zápasy z 9. 10. stažené
  10. 10. ve 13:46 UTC se ve 20:53 UTC lišily ve 2 ze 4, tedy oprava
  přišla zhruba 10–19 hodin po konci zápasu. Následek: těch 9 zápasů nemá
  řádky v `player_shot_splits` a `with_attempts` (`team_v2.py`) je
  vynechává z formy pokusů obou týmů. Hodnoty `mu_v2` zapsané do obnovy
  je neviděly (zapisují se jednou a nepřepisují se).
- **Kontrola se neuvolňuje** (žádná tolerance). Opravené zápasy se místo
  toho stáhnou znovu.
- **Kontrola oprav** = nový krok denního běhu před stažením box score.
  Zápas základní části živé sezóny s hotovým box score se stáhne znovu
  (box score a play-by-play, bez cache), nejvýš jednou za den UTC a ne
  v den, kdy se jeho box score stahovalo:
  (a) když je mu 1 až 10 dní (datum běhu UTC − `game_date`);
  (b) bez ohledu na stáří, když má krok `pbp`, `penalties` nebo
  `attempts` ve stavu `error`.
  Porovná se vše, co se z těchto dvou zdrojů ukládá: box score hráčů,
  brankářů a týmů a skóre zápasu; střely, bloky, střely na brankáře
  a zákroky za 60 minut; pokusy o střelu a rozdělení podle přesilovek
  a tresty po událostech, pokud jsou uložené. Časy na ledě podle situací
  (jiný zdroj, stahují se po herních dnech) se neporovnávají, při obnově
  se ale stáhnou znovu.
- **Obnova.** Liší-li se cokoli a čerstvá data NHL sedí sama se sebou
  (stejné kontroly jako dosud: střely a bloky z play-by-play = box score,
  trestné minuty = box score, střely za 60 minut z pokusů = z
  play-by-play), stav zápasu u kroků `boxscore`, `pbp`, `penalties`
  a `attempts` a stav jeho herního dne u `toi` se přepíše na `stale`
  a smažou se jeho soubory v cache. Zbytek téhož denního běhu ho stáhne
  znovu stávajícími kroky se všemi jejich kontrolami. Nesedí-li čerstvá
  data sama se sebou (oprava je rozpracovaná), nic se nemění a zkusí se
  to další den.
- **Záznam.** Každá kontrola = řádek v `stat_checks` (stáří ve dnech,
  výsledek), každá hodnota změněná při obnově = řádek v
  `stat_corrections` (staré → nové).
- **Okno 10 dní je zvolené bez měření**: porovnání po 2, 5 a 10 dnech
  nešlo udělat, protože NHL API ani databáze nejsou z prostředí, kde se
  to psalo, dostupné. Po nejméně 3 týdnech (~300 zápasů) se ze
  `stat_checks` vykáže podíl zápasů s opravou podle stáří. Okno se změní
  jen dalším datovaným dodatkem.
- **Vyhodnocení (rozhodnutí uživatele 11. 10. 2026):** vyhodnocené tipy
  a tikety drží číslo známé při vyhodnocení, opravená čísla jdou jen do
  vstupů modelů. Tipsport vyhodnocuje krátce po zápase a pozdější opravy
  obvykle nebere (předpoklad, v pravidlech Tipsportu neověřený); naše
  první stažení je jeho číslu nejblíž. Tipy
  (`tips.actual_60`) a týmové predikce (`team_predictions.actual_60`) to
  dělají už teď (vyhodnocení jen doplňuje prázdné). Hráčské tikety
  v dashboardu, které číslo čtou živě z `player_game_logs`, vezmou
  nejstarší původní `sog_reg` ze `stat_corrections`, a není-li tam,
  uložené číslo. Omezení: opravu, kterou NHL udělá dřív, než zápas poprvé
  stáhneme, nevidíme.
- Zamrazené modely, kritéria a vyhodnocení se nemění. Vstupy modelů
  (forma, pokusy o střelu) berou opravená čísla, stejně jako historické
  sezóny stažené až po opravách.

<!-- konec dodatku N-3 -->

Otisk dodatku N-3 (text od jeho nadpisu po značku konce): **SHA-256
`6f5fdd759146b7c3f61961bdf1e49ccc1c3f908b6242882f8aae22df29ed5605`**. Hlídá
ho `tests/test_corrections.py`.

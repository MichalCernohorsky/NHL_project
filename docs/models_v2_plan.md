# Modely v2 — nové atributy pro týmy, tresty a hráče

Stav: **SCHVÁLENO uživatelem 10. 10. 2026.** Sepsáno před stažením nových
dat a před jakýmkoli výpočtem. Znění je zamrazené otiskem SHA-256 (oddíl
na konci); změny jen jako datované dodatky. Pravidla sázení, prahy a běžící
papírové testy se tímto plánem nemění.

## 1. Co se zkouší a co čekat

Uživatel chce vyzkoušet atributy, které modelům chybí: (1) pokusy o střelu,
(2) přesilovky, (4) očekávaný průběh zápasu z hlavních kurzů, (5) fázi
sezóny u trestů, (6) odpočinek, (7) rozhodčí. Sestavy před zápasem (3)
se nezkouší — není pro ně ověřený zdroj.

Očekávání předem, nahlas:

- **Týmy a tresty:** tady má lepší model smysl, protože jiné měřítko než
  vlastní model není. Čeká se zlepšení předpovědi; jestli stačí na marži
  Tipsportu (~7,8 %), ukáže až papírový test.
- **Hráči:** americký trh většinu těchto informací v ceně má. Verze 1 byla
  o 0,0032 (Brier) za trhem a na zisk u Tipsportu by musela trh porážet
  zhruba o 4 procentní body. Pravděpodobnější výsledek je „nestačí".

## 2. Nová data (krok 0)

Všechno za 60 minut, z play-by-play NHL API, zdarma (jedno nové stažení
~4 000 zápasů, asi 35 minut):

- **Pokusy o střelu** týmu a hráče = střely na branku + střely mimo +
  zblokované střely (bez nájezdů; zblokovaná se počítá střelci).
- **Rozdělení podle počtu hráčů na ledě** (`situationCode`): hra v plném
  počtu × přesilovka — střely a pokusy hráče i týmu zvlášť.
- Každý zápas se ověří proti box score (součet střel na branku musí sedět).

Už v databázi: tresty po událostech (kdo fauloval, kdo faul vynutil),
rozhodčí odehraných zápasů, rozpis (odpočinek), čas hráče v přesilovce.

**Hlavní kurzy (atribut 4)** — moneyline a počet gólů z The Odds API,
jeden snímek na herní den v 15:00 UTC (před sázením): historie tří sezón
≈ 505 dnů × 20 kreditů = **~10 100 kreditů**, živě 2 kredity denně.
Kupuje se až po „jeď" (etapa B).

## 3. Týmové modely v2 (střely týmu S-T, tresty týmu T-T)

Verze 1: μ = L_t × útok × obrana × doma. Verze 2 přidává násobitele,
každý s jedním až dvěma koeficienty odhadnutými **jen na 2023-24 +
2024-25** maximální věrohodností (rozdělení jako u verze 1):

| atribut | jak vstupuje | koeficientů |
|---|---|---|
| (1) pokusy o střelu | forma útoku i obrany = (1 − α) × forma ze střel + α × forma z pokusů (přepočtená ligovým poměrem střel na pokus); jen S-T | 1 (α) |
| (2) přesilovky | exp(γ × odchylka očekávaného počtu přesilovek od ligy), očekávání = jak často tým fauly vynucuje × jak často soupeř fauluje (forma, stažená k lize) | 1 (γ) |
| (5) fáze sezóny | násobitel podle pořadí zápasu týmu v sezóně: 1.–10., 11.–20., 21. a dál (= 1) | 2 |
| (6) odpočinek | exp(β₁ × tým hraje druhý den po sobě + β₂ × soupeř hraje druhý den po sobě) | 2 |
| (4) průběh zápasu *(etapa B)* | exp(δ₁ × (pravděpodobnost výhry − 0,5) + δ₂ × (čekaný počet gólů − ligový průměr)), obojí z kurzů bez marže | 2 |
| (7) rozhodčí *(jen T-T, blok R)* | exp(ρ × průměrná odchylka obou rozhodčích od ligy v počtu dvouminutových trestů na zápas, z jejich dřívějších zápasů, stažená k nule vahou 30 zápasů) | 1 (ρ) |

Pro T-T se pravděpodobnost „více než 3,5 / 4,5" počítá kalibrací jako
v dodatku T-4, nově odhadnutou na μ verze 2. Pozastavení trestů do 1. 11.
(dodatek T-6) platí, dokud verze 2 neprojde.

## 4. Hráčský model v2 (střely hráče)

Verze 1: μ = rychlost střelby × čas na ledě × soupeř. Verze 2:

    μ = (r_plný × čas_plný + r_přes × čas_přes × P) × soupeř × odpočinek [× průběh]

- r_plný, r_přes — střelba na 60 minut ledu zvlášť v plném počtu
  a v přesilovce, každá = (1 − α) × ze střel + α × z pokusů, stažená
  k loňsku / pozici jako ve verzi 1.
- čas_plný, čas_přes — průměr posledních 10 zápasů, zvlášť.
- P — očekávaný počet přesilovek týmu proti lize (jako u týmů).
- soupeř — střely povolené soupeřem, zvlášť v plném počtu a v oslabení.
- odpočinek a průběh zápasu jako u týmů.

Koeficienty (α, P, odpočinek, průběh) a rozptyl jen z 2023-24 + 2024-25.

## 5. Vyhodnocení (pevné teď)

Bloky se přidávají v pevném pořadí; žádné jiné kombinace se nezkoušejí:
**A** = (1) + (2) + (5) + (6), zdarma. **B** = A + (4), po nákupu kurzů.
**R** = nejlepší z A/B + (7), jen tresty.

**Týmy a tresty, sezóna 2025-26** (použita už pro verzi 1 — druhý pohled,
přiznaně):

- Ztráta jako u verze 1 (S-T: logaritmická ztráta počtu; T-T: ztráta
  výsledku více / méně na 3,5 a 4,5). Rozdíl ztrát v1 − v2, bootstrap 95%
  interval (seed 17, 10 000, herní dny).
- **Blok A nahradí verzi 1**, když je celý interval nad nulou. **Blok B
  nahradí A** za stejné podmínky proti A. Jinak zůstává předchozí verze.
- Kalibrace v pěti pásmech a po částech sezóny (říjen / listopad / zbytek)
  jako popis.
- **Potvrzení dopředu:** od zamrazení se predikce v1 i v2 ukládají vedle
  sebe; po 300 zápasech sezóny 2026-27 se porovnají stejnou ztrátou. To
  je jediný test na datech, která žádná verze neviděla.

**Rozhodčí (blok R):** vykáže se, o kolik by znalost rozhodčích zlepšila
tresty (v historii jsou známi vždy). O použití v provozu se rozhodne
zvlášť — viz sekce 6.

**Hráči, vzorek 330 zápasů 2025-26** (použit už pro verzi 1 — druhý
model na stejných kurzech, přiznaně): stejná kritéria jako fáze 0 (K4a,
K4b za simulovaný kurz Tipsportu, m = 0,0874), pro blok A a po nákupu pro
blok B. **Když žádný blok K4b nesplní, hráčský model končí.** Když splní,
není to ještě důkaz (dva až tři modely na jednom vzorku): následuje
potvrzení na **novém** vzorku — closing zbylých ~980 zápasů 2025-26,
**~9 820 kreditů**, až po „jeď". Teprve to by otevřelo cestu k sázení.

## 6. Rozhodčí — kdy jsou známi

NHL API je před zápasem neukazuje (376 kontrol, vždy až při začátku). Web
Scouting the Refs je ale zveřejňuje v den zápasu: příspěvky 7.–10. 10.
2026 vyšly v 18:35, 18:30, 18:00 a 16:15 UTC, tedy **kolem 20:00–20:35
našeho času** (v sobotu s odpoledními zápasy 18:15) — zhruba 4,5 hodiny
před večerními zápasy. Pro tikety psané po tomto čase jsou tedy rozhodčí
použitelní.

Postup: nejdřív blok R ukáže, jestli rozhodčí vůbec stojí za to. Když ano,
ověří se podmínky webu pro automatické čtení; bez nich zbývá ruční zápis
dvou jmen na zápas. Do té doby se nic nestahuje.

## 7. Náklady

| | kredity | kdy |
|---|---|---|
| krok 0, blok A (týmy, tresty, hráči), blok R | 0 | po schválení |
| hlavní kurzy pro blok B | ~10 100 | po „jeď" |
| potvrzovací vzorek pro hráče | ~9 820 | jen když hráčský model projde, po „jeď" |

Zůstatek 95 216 kreditů (sdílený s NBA a MLB).

## 8. Co se nedělá

- Žádné ladění na sezóně 2025-26, žádné jiné kombinace atributů než bloky
  A, B, R, žádné řezy podle týmu, hráče, lajny nebo strany.
- Žádná změna prahu hrany, pravidla tiketů ani běžících papírových testů.
- Sestavy před zápasem se nezkoušejí.

## 9. Pořadí

1. Schválení plánu.
2. Krok 0: stažení pokusů o střelu a rozdělení podle přesilovek.
3. Blok A pro týmy a tresty → report. Blok R → report.
4. Blok A pro hráče na 330 zápasech → report.
5. „Jeď" k hlavním kurzům → blok B pro všechny tři → report.
6. Podle výsledků: nasazení v2 do dashboardu (týmy, tresty), případně
   potvrzovací nákup pro hráče.
<!-- konec schváleného znění -->

## Schválení a dodatky

Schváleno uživatelem 10. 10. 2026 („schvaluji, pusť se do bloku zdarma
a klidně jdi i do bodu za kredity"). Otisk schváleného znění (vše nad
značkou konce schváleného znění): **SHA-256 `91c11d3b96563fcce4e414a463fb4a2d36093e42ad0203a75f21b15faae3ca07`**. Hlídá ho
`tests/test_models_v2_plan.py`.

**Souhlas s nákupem hlavních kurzů (blok B) dal uživatel předem** ve stejné
zprávě. Platí pro nákup popsaný v sekci 2 (moneyline + počet gólů, jeden
snímek na herní den, tři sezóny) se stropem **10 500 kreditů**; před
nákupem proběhne suchý běh a kdyby vyšel nad strop, nákup se nespustí
a rozhodne uživatel znovu. Potvrzovací vzorek pro hráče (~9 820 kreditů)
tímto souhlasem krytý není.

**Suchý běh a „jeď" k hlavním kurzům (10. 10. 2026).** Suchý běh
(`scripts/buy_main_lines.py`) vyšel na 528 herních dnů × 20 = **10 560
kreditů**, o 60 nad stropem 10 500 — nákup se proto nespustil a uživatel
rozhodl znovu: „jeď, 10 560 je ok". Nový strop nákupu je 10 560 kreditů.
Nákup se zastaví sám, kdyby po 3 dnech nenašel žádný zápas s kurzy nebo po
25 dnech pokrýval méně než 80 % zápasů.

**Zamrazení týmových modelů v2, bloky A a R (10. 10. 2026).** Odhad jen na
2023-24 + 2024-25 (5 248 týmových řádků), před jakýmkoli pohledem na
verzi 2 na sezóně 2025-26. Soubor `models/team_v2.json`, **SHA-256
`d63a0c4600d0420daf1c833514fcabbd3a7e4325b3de45ffe7f3bf271849d189`**. Hlídá ho `tests/test_models_v2_plan.py`; skript
`scripts/fit_team_v2.py` ho odmítne přepsat.

| koeficient | střely týmu | tresty týmu |
|---|---|---|
| úroveň c₀ | -0.0037 | -0.0255 |
| přesilovky γ (na jednu očekávanou navíc) | -0.0015 | +0.0273 |
| 1.–10. zápas φ₁ | +0.0100 | +0.0570 |
| 11.–20. zápas φ₂ | -0.0167 | -0.0398 |
| tým druhý den po sobě β₁ | -0.0306 | +0.0062 |
| soupeř druhý den po sobě β₂ | +0.0253 | +0.0001 |
| váha pokusů α | 0.4 | — |
| rozptyl k | 100.13 | Poisson (mez 5000) |
| rozhodčí ρ (blok R) | — | +0.1244 |

Zisk věrohodnosti v tréninku proti verzi 1: střely +27.0,
tresty +10.0, rozhodčí nad blokem A +6.1
(v tréninku — o ničem nerozhoduje).

**Zamrazení hráčského modelu v2, blok A (10. 10. 2026).** Odhad jen na
2023-24 + 2024-25 (77910 řádků se vstupem fáze 0), před jakýmkoli
pohledem na verzi 2 na kurzech nebo na sezóně 2025-26. Soubor
`models/player_v2.json`, **SHA-256
`eb44ce13bb8218c181885db05bfe134e5e5dd27befea28a856725f9805e32c29`**. Hlídá ho `tests/test_models_v2_plan.py`; skript
`scripts/fit_player_v2.py` ho odmítne přepsat.

Koeficienty: α = 0.7 (váha pokusů o střelu), π = 0.25 (mocnina
očekávaných přesilovek), úroveň -0.0152, tým druhý den po sobě
-0.0345, soupeř druhý den po sobě +0.0343, rozptyl k =
17.92. Zisk věrohodnosti v tréninku proti verzi 1 na stejných
řádcích: +253.1 (v tréninku — o ničem nerozhoduje).

**Nákup hlavních kurzů proběhl (10. 10. 2026).** 528 herních dnů, utraceno
přesně **10 560 kreditů**, zůstatek 84 656. Kurzy má 3 933 z 3 936 zápasů
(3 zápasy začaly před snímkem v 15:00 UTC; jeden herní den měl jen takový
zápas, takže jeho 20 kreditů nepřineslo nic). Všechny snímky jsou z 14:55
UTC.

**Zamrazení bloku B týmových modelů (10. 10. 2026).** Odhad jen na 2023-24
+ 2024-25 nad pevným blokem A (5244 z 5248 řádků má kurzy
aspoň 3 knih), před jakýmkoli pohledem na blok B na sezóně 2025-26. Soubor
`models/team_v2b.json`, **SHA-256
`c36944cbdf7f38019c3b1fcf78cd1d15c922f954d6f1b6c7c69b4ed6e1b7d2a6`**. Hlídá ho `tests/test_models_v2_plan.py`.

| koeficient | střely týmu | tresty týmu |
|---|---|---|
| úroveň δ₀ | -0.0008 | -0.0002 |
| pravděpodobnost výhry δ₁ | +0.1414 | -0.0875 |
| čekaný počet gólů δ₂ | +0.0017 | +0.0043 |

Zisk věrohodnosti v tréninku proti bloku A: střely +16.8, tresty
+1.0 (v tréninku — o ničem nerozhoduje).

**Zamrazení bloku B hráčského modelu (10. 10. 2026).** Odhad jen na 2023-24
+ 2024-25 nad pevným blokem A (77882 z 77910 řádků má kurzy), před
jakýmkoli pohledem na blok B na vzorku s kurzy. Soubor
`models/player_v2b.json`, **SHA-256
`1957f3541bd1fe4ed66370e4149edad8155e04735f87f9cbcf1aa822a06795a5`**. Hlídá ho `tests/test_models_v2_plan.py`. Koeficienty: úroveň
-0.0011, pravděpodobnost výhry +0.1500, čekaný počet gólů -0.0025, k =
18.01; zisk věrohodnosti v tréninku proti bloku A +18.5.

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

# Naivní týmové modely — výklad zadání (před prvním odhadem)

Plán: `docs/team_markets_plan.md`, sekce 4 a 5, dodatek T-1. Tento soubor
převádí zadání na přesné vzorce a pevně volí vše, co zadání nechává
otevřené. **Zapsáno a commitnuto před prvním odhadem a před jakýmkoli
pohledem na výsledek na sezóně 2025-26.** Po odhadu se nemění.

## Data

- Zápasy základní části, u kterých jsou pro oba týmy úplné počty za
  60 minut. Trénink 2023-24 + 2024-25, ověření 2025-26.
- **Střely týmu** = součet střel hráčů v poli za 60 minut (`sog_reg`).
  Střela brankáře na branku (pár za sezónu) v součtu chybí.
- **Dvouminutové tresty týmu** podle dodatku T-1: `period_type = 'REG'`,
  `type_code` MIN nebo BEN, počet = `duration / 2`.
- Každý zápas dává dva řádky (tým, soupeř, doma/venku, počet týmu, počet
  soupeře). Vše, co model o zápasu ví, pochází ze zápasů **s dřívějším
  datem** (zápasy téhož dne se nepoužijí).

## Model týmu (trhy S-T a T-T; stejná stavba, vlastní konstanty)

    μ = L_t × útok_T × obrana_S × h^(±1)

- **L_t** — ligový průměr na tým a zápas z posledních 400 týmových řádků
  (200 zápasů) před datem zápasu, přes hranici sezón. Je-li jich méně než
  100 (první dny 2023-24), použije se průměr trénovacích sezón. Důvod pro
  klouzavý průměr místo pevného čísla: mezi 2023-25 a 2025-26 klesl počet
  střel v lize o 6,7 % (známo z modelu střel hráčů); pevné L by model
  vychýlilo.
- **Forma týmu** z posledních n = min(20, odehrané zápasy sezóny) zápasů
  aktuální sezóny: r_útok = průměr vlastního počtu / L_t, r_obrana = průměr
  počtu soupeřů v těch zápasech / L_t. (U trestů je „útok" faulování týmu
  a „obrana" tresty, které tým přivodí soupeřům.)
- **Výchozí bod z loňska:** p = 1 + c × (F_loni − 1), kde F_loni = loňský
  průměr týmu / loňský průměr ligy. Bez loňské sezóny v databázi (2023-24)
  je F_loni = 1.
- **Faktor** = (n × r + w × p) / (n + w), pro útok i obranu zvlášť, se
  společnými konstantami w (váha výchozího bodu v zápasech) a c (kolik
  z loňské odchylky přežije). Jedna dvojice (w, c) na rodinu trhů
  (střely, tresty).
- **h** — domácí faktor: h = √(průměr domácích / průměr hostů)
  v trénovacích sezónách; domácí tým × h, hosté ÷ h.
- **Rozdělení:** negativně binomické, jeden rozptyl k na trh.

## Model zápasu (trhy S-Z a T-Z)

μ_Z = μ_domácí + μ_hosté, negativně binomické s vlastním k_Z odhadnutým
na součtech v trénovacích sezónách.

## Odhad (jen 2023-24 + 2024-25)

- h přímo ze vzorce.
- (w, c) z mřížky w ∈ {1, 2, 3, 5, 8, 12, 16, 20, 30, 40, 60, 80, 120},
  c ∈ {0; 0,1; …; 1}: vybere se dvojice s nejvyšší věrohodností počtů
  týmů (k se pro každou dvojici dopočítá maximální věrohodností).
- k_Z maximální věrohodností na součtech při vybraném (w, c).
- Konstanty do `models/naive_team.json`; soubor se zamrazí otiskem
  SHA-256 zapsaným do plánu (oddíl dodatků) a skript ho odmítne přepsat.

## Základy pro kritérium T1

- **Z0:** μ = L_t (pro součet 2 × L_t), bez domácího faktoru.
- **Z1:** průměr týmu v aktuální sezóně před datem zápasu; pro součet
  průměr součtů v zápasech obou týmů. Bez odehraného zápasu = Z0.
- Oba negativně binomické s vlastním k odhadnutým na trénovacích sezónách
  (aby základ neprohrával jen kvůli špatnému rozptylu).

## Vyhodnocení na 2025-26 (jednou, po zamrazení)

- Ztráta = −log pravděpodobnosti skutečného počtu. Rozdíl ztrát
  (základ − model), průměr přes řádky, bootstrap 95% interval: seed 17,
  10 000 opakování, převzorkují se herní dny. **T1 splněno**, když je
  interval nad nulou proti Z0 **i** Z1.
- Kalibrace: P(více než lajna) pro S-T 22.5–30.5, S-Z 48.5–59.5,
  T-Z 5.5–8.5, T-T 3.5 a 4.5; všechny lajny dohromady, pět stejně
  velkých pásem podle předpovědi, předpověď × skutečná četnost.
- **Simulace nulového efektu**, 500 opakování, stejná bootstrap losování:
  (a) *promíchaní soupeři* — faktor soupeře se nahradí faktorem náhodného
  týmu z téhož zápasového řádku jiného zápasu (model zná tým, ne soupeře);
  (b) *promíchané předpovědi* — předpovědi μ se náhodně přeházejí mezi
  řádky (model nezná nic). U obou podíl opakování, která by splnila T1.
- Vykazují se všechny čtyři trhy, i ty, které T1 nesplní. Nic se podle
  výsledku neupravuje.

# Naivní model střel — výklad předpisu (2. 10. 2026, před prvním výpočtem)

Předpis: `docs/market_discovery_plan.md`, sekce 6.2 a dodatky D3 a D6.
Tady jsou zapsaná místa, která předpis nechává otevřená, a jak se čtou.
Zapsáno a commitnuto **před** prvním výpočtem na skutečných datech; po
výpočtu se nemění (oprava jen jako datovaný dodatek níže).

Kód: `src/nhl_tool/naive_sog.py`, odhad konstant `scripts/fit_naive_sog.py`,
zamrazený výsledek `models/naive_sog.json` (otisk SHA-256 v plánu).

## Výklad

| # | místo v předpisu | výklad |
|---|---|---|
| 1 | „střely na 60 min" (6.2) a D3 | střely **v základní době** (`sog_reg`) děleno časem na ledě **bez prodloužení** (`toi_s − ot_toi_s`); cílem modelu jsou střely za 60 minut |
| 2 | „TOI_L10" | průměr času na ledě bez prodloužení v posledních 10 odehraných zápasech **před** zápasem; přes hranici sezón (D6). U vyhodnocení fáze 0 (≥ 10 zápasů v sezóně) je to vždy uvnitř sezóny |
| 3 | „odehraný zápas" | řádek v box score s časem na ledě > 0 |
| 4 | „stažené k prioru o váze 3 hodin ledu" | r = (S + r_prior · W) / (T + W); S, T = střely a čas (bez OT) v sezóně před zápasem, W = 3 h |
| 5 | „prior = minulá sezóna při ≥ 20 zápasech" | surová rychlost hráče v minulé sezóně (všechny týmy). Pro 2023-24 minulá sezóna v datech není → prior pozice |
| 6 | „průměr pozice F/D" | rychlost útočníků (C, L, R) / obránců (D) v trénovacích sezónách 2023-24 + 2024-25 |
| 7 | „střely povolené soupeřem na zápas (L20)" | střely, které **soupeř** pustil (součet `sog_reg` hráčů, kteří proti němu hráli), v jeho posledních ≤ 20 zápasech **téže sezóny** před tímto zápasem; n = počet těch zápasů |
| 8 | „/ ligový průměr, stažené k 1 s váhou 10 zápasů" | o = (n · průměr/liga + 10 · 1) / (n + 10); ligový průměr = střely týmu za 60 min na zápas v trénovacích sezónách; bez zápasu o = 1 |
| 9 | „disperze odhadnutá na tréninku" | jedno k negativně binomického rozdělení (var = μ + μ²/k), maximum věrohodnosti na trénovacích řádcích se vstupem fáze 0 (≥ 10 zápasů v sezóně); hledá se v intervalu [0,5; 1000] (horní mez ≈ Poisson) |
| 10 | „r" v D3 (podíl prodloužení) | pro pozici F/D: Σ(střely − střely za 60) / Σ střely za 60 v trénovacích sezónách |
| 11 | zásahy, bloky (6.2) | **nestaví se**, dokud trh neprojde K1 (Tipsport je zatím nevypisuje; nákup jen střel, D4) |

## Co se nedělá

- Žádné další atributy (přesilovkový čas zvlášť, lajny, doma/venku, únava,
  brankář soupeře) — to je fáze 2.
- Sezóna 2025-26 se k odhadu ničeho nepoužije; konstanty se odhadnou jednou,
  zamrazí a nemění. Kontroly správnosti kódu před zamrazením běží jen na
  trénovacích sezónách.

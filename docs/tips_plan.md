# Tipy v dashboardu a „vsazeno" — plán (2. 10. 2026, před kódem)

**Zadání uživatele (2. 10.):** jako v MLB a NBA — tipy se vypisují každý
den; skutečná sázka je jen to, co uživatel označí **✅ Vsazeno** a zapíše
z tiketu. Co označené není, je papír.

Převzato: tok a zámek z NBA (`decisions.py`: rozhodnutí po začátku zápasu
odmítne kód, ne jen tlačítko; ramena MODEL / UŽIVATEL), formulář tiketu
a stránka *Moje sázky* z MLB (lajna, kurz, vklad, sázkovka; měkké smazání
překlepu), kontrola hrany u Tipsportu z NBA (`rule_at_book`).

## 1. Co je tip

- **Model:** naivní model z plánu fáze 0 (sekce 6.2), **střely hráče za
  60 minut** — tak vyhodnocuje Tipsport (dodatek D3). Konstanty se odhadnou
  jen na 2023-24 + 2024-25 a **zamrazí otiskem SHA-256 před nákupem kurzů
  2025-26 (etapa A)**. Pak se nemění. Až fáze 2 dodá produkční model,
  tipy na něj přejdou jako nová éra (vyhodnocení se řeže po érách).
- **Pravidlo:** plán 6.4 — hrana p_model − p_trh ≥ 3 p.b. proti de-vig
  trhu, na (zápas, hráč) nejvýš jedna strana. Vstup (dodatek D6): hráč má
  v sezóně ≥ 10 odehraných zápasů **nebo** ≥ 20 zápasů v minulé sezóně →
  tipy od chvíle, kdy je model hotový (původně by první tipy přišly až
  19.–29. 10.).
- **Trh při tipu:** jeden živý snímek amerických knih denně (`snapshot_kind
  = 'live'`, jen střely hráčů, ~1 kredit na zápas, ~200 měsíčně) v cloudovém
  denním běhu. Čas určuje GitHub (typicky 12:30–19:30 CZ); zápas, který do
  té doby začal, tip nemá. Předregistrované ranní a closingové snímky se
  dál kupují den poté z archivu (D4) — o nich tenhle snímek nerozhoduje.
- **Kontrola u Tipsportu:** pro lajnu a kurz z tiketu stránka přepočítá
  pravidlo (p_model při té lajně vs. 1/kurz, případně de-vig s kurzem druhé
  strany) a ukáže **minimální kurz**, od kterého tip dává smysl.

## 2. Co uvidíš

- Stránka **Tipy dne**: karty zápasů, u tipu hráč, lajna, strana, p_model,
  p_trh, hrana, minimální kurz u Tipsportu a štítek
  **NAIVNÍ MODEL — BEZ OVĚŘENÉ HRANY**, dokud fáze 0 neřekne jinak.
  Tlačítka **✅ Vsazeno** (formulář: lajna a kurz z tiketu, vklad v Kč,
  sázkovka, předvyplněno Tipsport) a **❌ Ne**. Po začátku zápasu zamčeno.
- Stránka **Moje sázky**: vsazené tikety, vyhodnocení, bilance; oprava
  překlepu měkkým smazáním.
- Bilance dvou ramen: **MODEL** (všechny tipy, papír, 1 jednotka, za
  simulovaný kurz Tipsportu podle D1) a **UŽIVATEL** (jen vsazené, skutečné
  kurzy a vklady). Obojí s bootstrap 95% intervalem.

## 3. Vyhodnocení

Druhý den v cloudu: střely za 60 minut (D3); hráč bez času na ledě =
void; push vrací vklad. Vsazený tiket se vyhodnocuje za **svou** lajnu
a kurz, ne za lajnu tipu. Všechny tipy se ukládají a vyhodnocují, i nevsazené.

## 4. Kde jsou data

- Tipy: `nhl.db` (cloud, soukromé `NHL_project-data`).
- Rozhodnutí a tikety: append-only soubory v **soukromém**
  `NHL_project-data` (GitHub Contents API, token `nhl-data`) — **nikdy**
  ve veřejném repozitáři kódu. Dashboard na Macu zapisuje, cloud je čte
  při vyhodnocení. Později volitelně dashboard v cloudu s heslem (mobil).

## 5. Poctivost (zapsaná předem)

- Naivní model **nemá ověřenou hranu**. Marže Tipsportu ~8,7 % znamená
  break-even ~54 % při kurzu 1,84. Poctivé očekávání je kolem nuly nebo pod.
  Doporučení: skutečné peníze až po verdiktu fáze 0. Rozhodnutí je
  uživatelovo.
- Živý záznam tipů **neovlivní verdikt fáze 0** (ten se počítá jen
  z 2025-26 podle plánu) ani žádný práh. Vykazuje se zvlášť a nic se
  podle něj neladí.

## 6. Harmonogram

| do | co |
|---|---|
| ~6. 10. | naivní model + zamrazení (potřeba i pro fázi 0, před etapou A) |
| ~10. 10. | denní predikce, živý snímek, tipy, stránka Tipy dne |
| ~14. 10. | Vsazeno / Moje sázky / vyhodnocení / ramena |

## 7. Varování a kontext u tipu (2. 10. 2026, před prvním vyhodnoceným tipem)

**Zkouška výpočtu** na ranním snímku 2. 10. (5 zápasů, 64 hráčů s lajnou
amerických knih): hrana ≥ 3 p.b. u 45 hráčů, tipů podle pravidla 43,
z toho 11 s hranou nad 10 p.b.; skoro všechno „méně". Příčina (ověřeno
na datech, není to chyba kódu): na začátku sezóny stojí naivní model jen
na minulé sezóně, takže hráč s loňským propadem (Seguin: zranění, 1,07
střely/zápas proti 2,30 předloni) dostane nízké číslo, kterému trh nevěří.

Dvě doplnění **zobrazení**, ne pravidla (rozhodnuto bez pohledu na
jakýkoli výsledek tipu):

- **⚠ Velká neshoda s trhem** u tipu s hranou > 10 p.b. Důvod z NBA
  (`edge_categories`, closing 2025-26): v pásmu hrany > 10 p.b. model
  tvrdil 51,7 %, trefil 38,6 %. U NHL se to měří zvlášť (tipy s varováním
  vs. bez), nefiltruje se.
- **Kontext:** u tipu střely za 60 minut na zápas v minulé a předminulé
  sezóně, aby byl vidět případ „loni zraněný".

Kapacita: tipů bývá víc, než lze vsadit; Tipsport ale vypisuje jen
6 hráčů na zápas a „minimální kurz" vyřadí sázky, kde marže sní hranu.
Strop počtu tipů se nezavádí (byl by to další nevalidovaný filtr).

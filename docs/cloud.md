# Provoz v cloudu (GitHub Actions) — Mac může být vypnutý

Stejné schéma jako MLB a NBA: úlohy běží na serverech GitHubu, databáze
je příloha jednoho vydání v **soukromém** repozitáři. Kód je **veřejný**
(neomezené minuty GitHub Actions); klíče a data v něm nikdy nejsou.

| repozitář | viditelnost | co v něm je |
|---|---|---|
| `MichalCernohorsky/NHL_project` | **veřejný** | kód, dokumentace, testy, úlohy (historie prověřena 2. 10. 2026: 15 commitů, 0 tajemství) |
| `MichalCernohorsky/NHL_project-data` | **soukromý** | jen vydání `db-latest` s `nhl.db.gz` |

Proč data zvlášť: příloha vydání veřejného repozitáře je stažitelná pro
kohokoli, a databáze obsahuje placené kurzy (redistribuce zakázaná)
a později tvoje sázky. `scripts/db_release.py` odmítne nahrávat do
repozitáře kódu.

## Úlohy

| soubor | kdy (čas CZ) | co |
|---|---|---|
| `.github/workflows/daily.yml` | každou hodinu 13:30–19:30 CEST (GitHub spouští se zpožděním 3–7 h, 5.–9. 10. první běh dne až ~19:00; víc spouštění = větší šance, že tipy jsou do 18:00) | denní běh dat (jako `make daily`; od 4. 10. i tresty, rozhodčí a záznam, zda jsou rozhodčí dnešních zápasů už známí; od 9. 10. i predikce týmových trhů) + nákup včerejších snímků kurzů z archivu (`scripts/buy_snapshots.py`, dodatek D4 plánu) |
| `.github/workflows/odds.yml` | jen ručně | bezplatná kontrola klíče The Odds API |
| `.github/workflows/props.yml` | jen ručně | nákup historických kurzů etapy A (střely hráče, 330 zápasů 2025-26). Bez vstupu `confirm = jed` proběhne jen suchý běh; nákup až po uživatelově souhlasu („jeď“) |
| `.github/workflows/tests.yml` | každý push | testy |

**Proč ne živé snímky (2. 10. 2026):** GitHub spouštěl plán „každých 10
minut" jen jednou za 3–6 hodin a Mac snímky ztrácí, když spí. Archiv The
Odds API drží každou lajnu po 5 minutách, takže den poté se koupí přesně
v kotvách z plánu (10:00 ET; začátek −10 min). Desetinásobná cena:
~31 kreditů na zápas, ~6 500 měsíčně. Na časech GitHubu tím nezáleží —
denní běh smí doběhnout s hodinovým zpožděním a okno 7 dní dožene
i vynechaný den. Nákup je vypnutý, dokud uživatel neřekne „jeď"
(`odds.hist_daily_enabled` v `config/config.yaml`).

**Ruční spuštění denního běhu (4. 10. 2026):** ne dřív než ~11:30 UTC
(7:30 ET). Živý snímek pro tipy se bere u každého zápasu jen jednou za den
a ⭐ TOP se zapisuje při prvním sestavení tipů (docs/tips_plan.md, sekce 8)
— běh ve 4–5 hodin ráno ET by tipy postavil na pár knihách a TOP vybral
z neúplné nabídky. Zápas, který kurzy ještě nemá, se zkusí znovu při dalším
běhu (prázdná odpověď nestojí kredit). Plánované běhy chodí se zpožděním:
3. 10. dorazil běh z 10:30 UTC až ve 14:48 UTC.

Hostovaný dashboard (Streamlit, od 4. 10. 2026): `docs/streamlit.md`.

## Nastavení (jednorázově, ~20 minut, dělá uživatel)

Pořadí je důležité: **zveřejnění první.** Úlohy jsou na GitHubu od 29. 9.
a v soukromém repozitáři spotřebovávají minuty Actions sdílené s MLB
(a bez nastavení selhávají). Historie prověřena 2. 10. 2026: 15 commitů,
0 tajemství.

1. **Zveřejnit `NHL_project`:** Settings → úplně dole *Danger Zone* →
   *Change repository visibility* → *Change visibility* → *Make public* →
   potvrdit (GitHub chce opsat název repozitáře).
2. **Datový repozitář:** vpravo nahoře **+** → *New repository* → název
   `NHL_project-data` → **Private** → zaškrtnout **Add a README file**
   (vydání potřebuje aspoň jeden commit) → *Create repository*.
3. **Token jen pro data:** fotka vpravo nahoře → *Settings* → úplně dole
   *Developer settings* → *Personal access tokens* → *Fine-grained tokens*
   → *Generate new token*:
   - Token name `nhl-data`, Expiration *Custom* → za rok
   - Repository access: **Only select repositories** → `NHL_project-data`
   - Permissions → Repository permissions → **Contents: Read and write**
     (*Metadata: Read-only* se přidá samo, to je v pořádku). Nic jiného.
   - *Generate token* → zkopírovat (ukáže se jen jednou). Nechat okno
     otevřené do konce kroku 5.
4. **Secrets v `NHL_project`:** Settings → *Secrets and variables* →
   *Actions* → *New repository secret*:
   - Name `NHL_DATA_TOKEN`, Secret = token z kroku 3 → *Add secret*
   - Name `ODDS_API_KEY`, Secret = klíč The Odds API. Do schránky ho
     dostaneš bez zobrazení: `grep '^ODDS_API_KEY=' ~/NHL_project/.env | cut -d= -f2- | tr -d '\n' | pbcopy`,
     pak Cmd+V do pole → *Add secret*
5. **Token na Macu:** `open -e ~/.zshrc`, na konec souboru dva nové řádky
   (bez uvozovek; token je jeden kus bez mezer), Cmd+S:
   ```
   export NHL_DATA_TOKEN=sem_vloz_token_z_kroku_3
   export NHL_DB_RELEASE_REPO=MichalCernohorsky/NHL_project-data
   ```
   Ověření v novém okně Terminálu (vypíše jen `ok`):
   `[ -n "$NHL_DATA_TOKEN" ] && echo ok || echo chybi`
6. **První nahrání databáze z Macu:** `cd ~/NHL_project`,
   `source .venv/bin/activate`, `make db-up`.
7. **Zkušební běh:** `NHL_project` → *Actions* → *Denni beh* → *Run
   workflow*. Ověří, že NHL API z GitHubu funguje (NBA ho z cloudu
   blokuje, NHL by nemělo — ověřuje se tady).
   Klíč The Odds API se ověří zdarma: *Actions* → *Kurzy (rano + closing)*
   → *Run workflow* → mode **check** (volá bezplatný dotaz, žádný kredit).
   Ověřeno 2. 10. 2026: denní běh i klíč v cloudu zelené.
8. **Vypnutí Macu jako sběrače:** hotovo 2. 10. 2026
   (`make automation-uninstall`). Do databáze od té doby zapisuje jen cloud.

## Dashboard na Macu

Pravda je od kroku 8 v cloudu. Před prohlížením dashboardu stáhni čerstvou
databázi: `make db-down` (odmítne přepsat, kdyby lokální byla v něčem
novější), pak `make dashboard`.

## Známá omezení

- GitHub vypne plánované úlohy ve veřejném repozitáři po 60 dnech bez
  commitu. Při běžném vývoji to nehrozí; kdyby Actions ukázaly žlutý
  pruh „disabled", stačí je znovu povolit tlačítkem.
- Token z kroku 2 vyprší za rok — úlohy pak skončí chybou 401; vygeneruj
  nový a vyměň ho v kroku 3 a 4.

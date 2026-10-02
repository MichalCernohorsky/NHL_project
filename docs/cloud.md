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
| `.github/workflows/daily.yml` | 12:30, záloha 15:30 a 19:30 | denní běh dat (jako `make daily`) |
| `.github/workflows/odds.yml` | každých 10 min, 15:00–07:50 | brána → ranní snímek (10:00–11:59 ET) nebo closing (zápas do 30 min) |
| `.github/workflows/tests.yml` | každý push | testy |

**Rozdíl proti Macu (nahlas):** GitHub plánované úlohy zpožďuje
(MLB: až 40 min, jednou vynechal den). Ranní snímek proto proběhne mezi
10:00 a 11:59 ET a closing je **poslední snímek před začátkem zápasu**
(oceňuje se opakovaně od 30 min před zápasem, nikdy po začátku). Skutečný
čas každého snímku je v `odds.snapshot_time`. Ve fázi 0 je closing jen
diagnostika; historická data (plán, sekce 4) mají pevné časy a tohle se
jich netýká.

Kredity: ~3 za zápas a snímek; closing se opakuje až 3× → ~50–70 za
herní den, ~2 000 měsíčně. Pod 2 000 na účtu se sběr zastaví.

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
8. **Vypnutí Macu jako sběrače** až po zeleném kroku 7 a prvním zeleném
   běhu *Kurzy*: `make automation-uninstall`. Jinak by se kurzy stahovaly
   dvakrát a platily dvakrát kredity.

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

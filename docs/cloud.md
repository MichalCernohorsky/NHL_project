# Provoz v cloudu (GitHub Actions) — Mac může být vypnutý

Stejné schéma jako MLB a NBA: úlohy běží na serverech GitHubu, databáze
je příloha jednoho vydání v **soukromém** repozitáři. Kód je **veřejný**
(neomezené minuty GitHub Actions); klíče a data v něm nikdy nejsou.

| repozitář | viditelnost | co v něm je |
|---|---|---|
| `MichalCernohorsky/NHL_project` | **veřejný** | kód, dokumentace, testy, úlohy (historie prověřena 29. 9. 2026: 11 commitů, 0 tajemství) |
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

## Nastavení (jednorázově, ~15 minut, dělá uživatel)

1. **Datový repozitář:** github.com → New repository → název
   `NHL_project-data`, **Private**, zaškrtni *Add a README file* (vydání
   potřebuje aspoň jeden commit) → Create.
2. **Token jen pro data:** Settings → Developer settings → Personal access
   tokens → **Fine-grained tokens** → Generate new token:
   - Token name `nhl-data`, Expiration 1 rok
   - Repository access: **Only select repositories** → `NHL_project-data`
   - Repository permissions → **Contents: Read and write**. Nic jiného.
   - Zkopíruj ho (ukáže se jednou). Nikam ho nevkládej kromě kroků 3 a 4.
3. **Secrets v `NHL_project`:** repozitář → Settings → Secrets and
   variables → Actions → New repository secret, dvakrát:
   - `NHL_DATA_TOKEN` = token z kroku 2
   - `ODDS_API_KEY` = klíč The Odds API (stejný jako v `.env`)
4. **Token na Macu** (pro `make db-up` / `make db-down`), v Terminálu:
   `open -e ~/.zshrc`, na konec přidej dva řádky a ulož:
   ```
   export NHL_DATA_TOKEN="sem_vloz_token"
   export NHL_DB_RELEASE_REPO="MichalCernohorsky/NHL_project-data"
   ```
5. **Zveřejnění kódu:** `NHL_project` → Settings → dole *Danger Zone* →
   Change visibility → **Public**.
6. **První nahrání databáze z Macu** (až doběhne stahování play-by-play),
   v novém okně Terminálu: `cd ~/NHL_project`, `source .venv/bin/activate`,
   `make db-up`.
7. **Zkušební běh:** `NHL_project` → Actions → *Denni beh* → Run workflow.
   Ověří, že NHL API z GitHubu funguje (NBA ho z cloudu blokuje, NHL by
   nemělo — ověřuje se tady).
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

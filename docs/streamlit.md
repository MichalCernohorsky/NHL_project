# Dashboard na Streamlit Community Cloud

Cíl: dashboard na adrese, která jde otevřít z mobilu, bez zapnutého Macu.
Tipy, Rozbor zápasu i zápis tiketů fungují stejně jako lokálně.

## Jak to drží pohromadě

| co | kde | poznámka |
|---|---|---|
| kód | veřejný `MichalCernohorsky/NHL_project` | Streamlit ho bere přímo z GitHubu, každý push = nové nasazení |
| databáze | soukromý `NHL_project-data`, vydání `db-latest` | aplikace si ji stáhne při startu a pak každých 15 minut zkontroluje, jestli cloud nenahrál novější; nikdy do ní nezapisuje |
| tikety a rozhodnutí | soukromý `NHL_project-data`, složka `bets/` | každý zápis jde hned na GitHub; disk Streamlitu se při restartu maže, takže pravda je na GitHubu |
| heslo | `APP_PASSWORD` v nastavení aplikace (Secrets) | bez hesla se nevykreslí nic |

Proč heslo: repozitář kódu je veřejný, takže adresu aplikace může otevřít
kdokoli. Databáze přitom obsahuje koupené kurzy (The Odds API zakazuje
šířit je dál) a stránky umí zapisovat tikety.

Zámek je „zavřený, dokud se neprokáže opak" (`src/dashboard/cloud.py`):
heslo se přeskočí jen s `NHL_DASHBOARD_LOCAL=1`, které nastavuje
`make dashboard` na Macu. Hostovaná aplikace bez `APP_PASSWORD` (nebo
s heslem kratším než 8 znaků) zůstane zamčená. Heslo se porovnává
v konstantním čase, po špatném pokusu je vteřina prodleva a po pěti
pokusech se musí stránka načíst znovu. Klíč The Odds API na Streamlit
**nepatří** — dashboard kurzy nekupuje.

## Nastavení (jednorázově, ~10 minut, dělá uživatel)

1. Otevřít <https://share.streamlit.io> → *Continue with GitHub* →
   přihlásit se účtem `MichalCernohorsky` (stejný jako u MLB).
2. Vpravo nahoře **Create app** → *Deploy a public app from GitHub*:
   - Repository: `MichalCernohorsky/NHL_project`
   - Branch: `claude/nhl-phase0-market-discovery`
   - Main file path: `dashboard/app.py`
   - App URL: libovolný název, např. `nhl-props-michal`
3. Ještě před *Deploy* rozkliknout **Advanced settings**:
   - Python version: **3.12**
   - do pole **Secrets** vložit tři řádky (uvozovky nechat):
     ```
     APP_PASSWORD = "sem-vymysli-vlastni-heslo"
     NHL_DATA_TOKEN = "sem-token"
     NHL_DB_RELEASE_REPO = "MichalCernohorsky/NHL_project-data"
     ```
   - heslo si vymysli sám (aspoň 8 znaků, raději delší větu) a nikam
     jinam ho nepiš;
   - token je ten z `docs/cloud.md`, krok 3. Do schránky ho dostaneš bez
     zobrazení příkazem v Terminálu, pak Cmd+V mezi uvozovky:
     ```
     printf '%s' "$NHL_DATA_TOKEN" | pbcopy
     ```
4. **Save** → **Deploy**. První start trvá 2–3 minuty (instalace
   knihoven, stažení databáze).
5. Otevřít adresu aplikace, zadat heslo. Vlevo dole má být
   „databáze stará N h" (stáří posledního nahrání z cloudu) a „tikety se
   zálohují na GitHub".

Kontrola, že je všechno v pořádku:

- bez hesla není vidět nic kromě pole *Heslo*;
- *Tipy dne* ukazují dnešní zápasy;
- zkušební ✅ na tipu a jeho vrácení ❌ se objeví v `NHL_project-data`
  ve složce `bets/` (soubor `decisions.jsonl`).

## Co když

- **„Dashboard je zamčený: chybí APP_PASSWORD"** — v aplikaci na
  share.streamlit.io → ⋮ → *Settings* → *Secrets* doplnit heslo.
- **„Databázi se nepodařilo stáhnout"** — špatný nebo prošlý token
  v Secrets (hláška říká, co je s ním špatně, token sám nikdy neukáže).
- **Stará databáze** — denní běh v GitHub Actions nedoběhl; viz
  `docs/cloud.md`.
- **Změna hesla** — přepsat `APP_PASSWORD` v Secrets; aplikace se sama
  restartuje.

## Lokálně na Macu

Beze změny: `make db-down` a `make dashboard`. Heslo se neptá.
Spuštění přímo přes `streamlit run dashboard/app.py` (bez `make`) se
chová jako hostovaná aplikace, tedy zamčeně.

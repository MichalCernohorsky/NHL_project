# Zdroje dat a ověřená fakta (stav 28. 9. 2026)

Co bylo ověřeno živým voláním nebo v dokumentaci, s odkazem. „Neověřeno"
znamená, že to nešlo potvrdit — ne že to neplatí.

## Kalendář NHL 2026-27

- Preseason 19.–26. 9. 2026, 65 zápasů —
  https://www.nhl.com/news/2026-2027-preseason-nhl-schedule-to-begin-september-19-2026
- Základní část **29. 9. 2026 – 10. 4. 2027**, 84 zápasů na tým, 1 344
  celkem — https://www.nhl.com/news/nhl-announces-2026-27-regular-season-schedule
  a `https://api-web.nhle.com/v1/schedule/2026-09-29`
  (`regularSeasonStartDate`, `regularSeasonEndDate`).
- Global Series: CAR–SEA Helsinky 12. a 14. 11.; CHI–OTT Düsseldorf 18.
  a 20. 12. Heritage Classic 25. 10., Winter Classic 31. 12., Stadium
  Series 20. 2. 2027. All-Star 6. 2. 2027 (UBS Arena).
- Dny bez zápasů: 20. 11., 26. 11., 23.–25. 12., 4.–7. 2. 2027. Žádná
  olympijská pauza.
- Uzávěrka přestupů 1. 3. 2027 — **jen média** (The Athletic, SI), NHL
  nepotvrdila.

## The Odds API (the-odds-api.com, ne theoddsapi.com)

- Sport: `icehockey_nhl` (a `icehockey_nhl_preseason`) —
  https://the-odds-api.com/sports-odds-data/sports-apis.html
- Hráčské trhy NHL: `player_points`, `player_power_play_points`,
  `player_assists`, `player_blocked_shots`, `player_shots_on_goal`,
  `player_goals`, `player_total_saves`, `player_goal_scorer_first`,
  `player_goal_scorer_last`, `player_goal_scorer_anytime`; alternativy
  `*_alternate` u points, assists, power_play_points, goals,
  shots_on_goal, blocked_shots, total_saves —
  https://the-odds-api.com/sports-odds-data/betting-markets.html
- Týmové: `h2h`, `spreads`, `totals`, `alternate_spreads`,
  `alternate_totals`, `team_totals`, `alternate_team_totals`, `h2h_3_way`
  a periody `*_p1`, `*_p2`, `*_p3`.
- Historie: od 6. 6. 2020 (po 10 min, od 9/2022 po 5 min); **hráčské
  propsy a další trhy od 2023-05-03T05:30:00Z** —
  https://the-odds-api.com/liveapi/guides/v4/
- Ceny: historické eventy 1 kredit; historické odds eventu **10 × vrácené
  trhy × regiony**; živé odds eventu vrácené trhy × regiony; prázdná
  odpověď nic.
- Propsy hlavně u amerických knih (region `us`: DraftKings, FanDuel,
  BetMGM, BetRivers, Bovada…). Které knihy kotují NHL propsy, dokumentace
  neuvádí — ukáže až první nákup.

## Pravidla vypořádání (OT / nájezdy)

- FanDuel (US hockey house rules): hráčské propsy = základní hrací doba
  + prodloužení, **nájezdy se nepočítají**; hráč bez času na ledě = void;
  zásahy platí, jen když uvedený brankář začne zápas. Moneyline, puck
  line a totaly počítají OT i nájezdy.
- DraftKings: **neověřeno** (stránka pravidel vrátila 403).
- Tipsport: **ověří uživatel** (plán fáze 0, sekce 7, bod 6).

## NHL API (zdarma, bez klíče)

Neoficiální dokumentace: https://github.com/Zmalski/NHL-API-Reference

| endpoint | co dává |
|---|---|
| `api-web.nhle.com/v1/schedule/{YYYY-MM-DD}` | týden zápasů, `gameOutcome.lastPeriodType` (REG/OT/SO), hranice sezóny |
| `api-web.nhle.com/v1/gamecenter/{id}/boxscore` | hráči: goals, assists, points, plusMinus, pim, hits, powerPlayGoals, sog, faceoffWinningPctg, toi „MM:SS", blockedShots, shifts, giveaways, takeaways; brankáři: saves, shotsAgainst, rozpad podle situací, toi, `starter`, decision. **Bez PP TOI a PP asistencí.** Jména zkrácená („J. Gibson"). |
| `api-web.nhle.com/v1/gamecenter/{id}/right-rail` | `gameInfo.{home,away}Team.scratches` (id + plné jméno) |
| `api.nhle.com/stats/rest/en/skater/timeonice?isAggregate=false&isGame=true&limit=-1&cayenneExp=gameDate="YYYY-MM-DD" and gameTypeId=2` | EV / PP / SH / OT TOI v sekundách, plné jméno; jeden herní den na volání (~500 řádků) |
| `api.nhle.com/stats/rest/en/goalie/summary?isGame=true…` | starty, zásahy, plné jméno brankáře |
| `api-web.nhle.com/v1/player/{id}/landing` | jméno, pozice, držení hole, datum narození |

Pozor: stats REST vrací nejvýš 10 000 řádků na dotaz — proto dotaz po
herních dnech, ne po sezóně.

## Ostatní

- **MoneyPuck** (https://moneypuck.com/data.htm): sezónní i zápasové CSV
  (hráči, brankáři, lajny, týmy), střely s xG od 2007. **Zdarma jen pro
  nekomerční účely s uvedením MoneyPuck.com**; neschválený scraping je
  blokovaný — stahovat jen nabízené soubory.
- **DailyFaceoff — startující brankáři**:
  `dailyfaceoff.com/starting-goalies/YYYY-MM-DD`, archiv nejméně od
  2021-22, stav („Confirmed"…) + zdroj + čas zprávy. Drží jen **finální**
  stav, ne ranní snímek. robots.txt zakazuje jen /api/ a /cms/; podmínky
  užití nenalezeny. Stahovat šetrně (1–2 dotazy denně).
- **DailyFaceoff — sestavy a PP jednotky**: `/teams/{slug}/line-combinations`;
  historický archiv nenalezen → ukládat vlastní denní snímek.
- LeftWingLock: brankáři/sestavy za předplatné; nepoužívá se.
- Natural Stat Trick: automatizovaný přístup jen přes
  `data.naturalstattrick.com` s klíčem na vyžádání; zatím nepoužívá se.

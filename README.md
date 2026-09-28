# NHL_project — výzkum hráčských sázek NHL (sezóna 2026-27)

Sesterský projekt `NBA_tool` a `MLB_project`: stejná disciplína
(předregistrace před výsledkem, zamrazení na sezónu, dodatky jen datované
a otisknuté SHA-256, plán commitnutý před kódem a výsledkem).

**Stav 28. 9. 2026: fáze 0 — výběr trhu.** Plán je v
[`docs/market_discovery_plan.md`](docs/market_discovery_plan.md), vzorek
dnů v [`docs/market_discovery_sample.md`](docs/market_discovery_sample.md),
ověřené zdroje v [`docs/sources.md`](docs/sources.md). Nic se nesází.

## Požadavky

- Python 3.11+ (na Macu je 3.12 — stačí)
- Domácí připojení; NHL API je veřejné a bez klíče
- Klíč The Odds API jen v souboru `.env` (viz `.env.example`), nikdy
  v URL, logu, commitu ani chatu

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Příkazy

| # | příkaz | co dělá | stojí |
|---|---|---|---|
| 1 | `python scripts/migrate.py` | založí / aktualizuje databázi `data/nhl.db` | nic |
| 2 | `python scripts/backfill_schedule.py` | rozpis 2023-24 až 2026-27 (týden na request) | ~120 requestů NHL API |
| 3 | `python scripts/backfill_boxscores.py` | box score + scratches odehraných zápasů | 2 requesty na zápas, ~1 h na sezónu |
| 4 | `python scripts/backfill_toi.py` | EV / PP / SH / OT čas na ledě + plná jména | 1 request na herní den |
| 5 | `python scripts/backfill_players.py` | jména, která zbyla (brankáři) | 1 request na hráče |
| 6 | `python scripts/report.py` | co je v databázi | nic |
| — | `make data` | kroky 2–5 najednou | |
| — | `python scripts/backfill_props.py --dry-run` | vzorek a cena nákupu kurzů | nic (bez klíče) |
| — | `make odds-morning` / `make odds-closing` | živé snímky kurzů dne | ~3 kredity na zápas a snímek |

Všechny stahovací kroky jsou **resumable**: přerušení (Ctrl+C) nic
neztratí, další spuštění pokračuje. Stažené JSON odehraných zápasů se
ukládají do `data/raw_cache/` a znovu se nestahují.

## Struktura

```
config/config.yaml   # sezóny, NHL API, kurzy (trhy, snímky, rezervy kreditů)
migrations/          # verzované SQL (0001 jádro, 0002 kurzy)
scripts/             # spustitelné kroky
src/nhl_tool/        # parsování, klienti, párování jmen, vzorek
tests/               # pytest, offline (python -m pytest)
docs/                # plán, vzorek, zdroje
data/                # nhl.db + cache (NIKDY do gitu)
```

## Pravidla, která se nemění

- Každé čtení tabulky `odds` jmenuje snímek (`snapshot_kind`); hlídá to
  `tests/test_snapshot_isolation.py`.
- Všechno v `*_game_logs` a `scratches` je stav **po zápase**. Ranní
  informace (potvrzený brankář, sestavy) dostanou vlastní tabulky s časem.
- Kurzy se nekupují bez suchého běhu a uživatelova „jeď".

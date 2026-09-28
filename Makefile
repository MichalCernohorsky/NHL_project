.PHONY: migrate data report test props-dry-run odds-morning odds-closing odds-status

migrate:
	python scripts/migrate.py

# Historical data (no key, no credits): schedule -> box scores -> TOI split
# -> missing names. Resumable: stop it any time, run again to continue.
data:
	python scripts/backfill_schedule.py
	python scripts/backfill_boxscores.py
	python scripts/backfill_toi.py
	python scripts/backfill_players.py

report:
	python scripts/report.py

test:
	python -m pytest

# --- odds (The Odds API, key in .env) -------------------------------------
# Phase 0 purchase preview: sample days + cost, spends nothing, no key.
props-dry-run:
	python scripts/backfill_props.py --dry-run

# Live snapshots of today's games. Morning = 16:00 CZ (10:00 ET); closing
# watcher = evening, keeps the Mac awake until the last puck drop.
odds-morning:
	python scripts/collect_odds.py morning

odds-closing:
	caffeinate -i python scripts/collect_odds.py closing --watch

odds-status:
	python scripts/collect_odds.py status

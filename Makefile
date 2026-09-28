.PHONY: migrate data report test

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

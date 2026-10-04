.PHONY: migrate data daily report test dashboard db-up db-down db-status props-dry-run odds-morning odds-closing odds-status \
        automation-install automation-status automation-uninstall

migrate:
	python scripts/migrate.py

# Historical data (no key, no credits): schedule -> box scores -> TOI split
# -> missing names -> 60-minute counts from play-by-play.
# Resumable: stop it any time, run again to continue.
data:
	python scripts/backfill_schedule.py
	python scripts/backfill_boxscores.py
	python scripts/backfill_toi.py
	python scripts/backfill_players.py
	python scripts/backfill_pbp.py

# Live season, every morning (launchd 12:30 CZ): only what is new.
daily:
	python scripts/daily_collect.py

# Dashboard on the Mac. NHL_DASHBOARD_LOCAL=1 skips the password gate that
# the hosted app enforces (docs/streamlit.md).
dashboard:
	NHL_DASHBOARD_LOCAL=1 streamlit run dashboard/app.py

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

# --- automation (macOS launchd; docs/automation.md) -----------------------
# daily 12:30, odds-morning 16:00, odds-closing 17:00 (local Mac time).
# Never decides a bet.
automation-install:
	scripts/install_automation.sh

# Shows what is loaded AND the newest log line per job. Read the log dates,
# not the exit code: launchd reports 0 for a job that has never run.
automation-status:
	scripts/install_automation.sh --status

automation-uninstall:
	scripts/install_automation.sh --uninstall

# --- database transfer (docs/cloud.md) -------------------------------------
# data/nhl.db lives in ONE release of the PRIVATE repo NHL_project-data.
# Needs NHL_DATA_TOKEN and NHL_DB_RELEASE_REPO in the environment (~/.zshrc).
db-up:
	python scripts/db_release.py up

db-down:
	python scripts/db_release.py down

db-status:
	python scripts/db_release.py status

"""The cloud jobs: gate logic, and the workflows never send the database
to the public code repository or expose secrets."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from odds_due import decide

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def _utc(h, m=0, day=1):
    return datetime(2026, 10, day, h, m, tzinfo=timezone.utc)


def test_gate():
    start = _utc(23)                                   # 19:00 EDT
    assert decide(_utc(22, 35), [start]) == "closing"  # 25 min ahead
    assert decide(_utc(22, 20), [start]) == "none"     # 40 min ahead
    assert decide(_utc(14, 5), [start]) == "morning"   # 10:05 EDT
    assert decide(_utc(23, 0), [start]) == "none"      # puck drop: never after
    assert decide(_utc(14, 5), []) == "none"           # no games today
    # a matinee at 12:30 ET: closing wins inside the morning window
    assert decide(_utc(16, 10), [_utc(16, 30)]) == "closing"


def test_workflows_target_the_private_data_repo_and_use_secrets():
    for name in ("daily.yml", "odds.yml"):
        text = (WF / name).read_text()
        wf = yaml.safe_load(text)
        assert wf["env"]["NHL_DB_RELEASE_REPO"] == "MichalCernohorsky/NHL_project-data"
        assert wf["concurrency"]["group"] == "nhl-db"
        assert "${{ secrets.NHL_DATA_TOKEN }}" in text
        assert "echo" not in text.lower() or "secrets" not in text.split("echo")[1][:80]


def test_odds_job_spends_nothing_when_the_gate_says_none():
    wf = yaml.safe_load((WF / "odds.yml").read_text())
    steps = wf["jobs"]["odds"]["steps"]
    for s in steps:
        if "ODDS_API_KEY" in str(s.get("env", "")):
            assert "steps.gate.outputs.due ==" in s["if"]
    assert "--repeat" in str(steps) and "--early-minutes 20" in str(steps)

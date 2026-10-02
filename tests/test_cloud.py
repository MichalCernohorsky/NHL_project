"""The cloud jobs: gate logic, and the workflows never send the database
to the public code repository or expose secrets."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def test_workflows_target_the_private_data_repo_and_use_secrets():
    for name in ("daily.yml",):
        text = (WF / name).read_text()
        wf = yaml.safe_load(text)
        assert wf["env"]["NHL_DB_RELEASE_REPO"] == "MichalCernohorsky/NHL_project-data"
        assert wf["concurrency"]["group"] == "nhl-db"
        assert "${{ secrets.NHL_DATA_TOKEN }}" in text
        assert "echo" not in text.lower() or "secrets" not in text.split("echo")[1][:80]


def test_daily_never_uploads_after_a_failed_download():
    wf = yaml.safe_load((WF / "daily.yml").read_text())
    steps = {s.get("name"): s for s in wf["jobs"]["daily"]["steps"]}
    assert steps["Stazeni databaze"]["id"] == "down"
    assert "steps.down.outcome == 'success'" in steps["Ulozeni databaze"]["if"]


def test_key_check_is_manual_only_and_free():
    wf = yaml.safe_load((WF / "odds.yml").read_text())
    trig = wf[True] if True in wf else wf["on"]          # yaml reads 'on' as True
    assert set(trig) == {"workflow_dispatch"}            # no schedule: no live buying
    run = " ".join(s.get("run", "") for s in wf["jobs"]["check"]["steps"])
    assert "collect_odds.py check" in run and "db_release" not in run


def test_daily_job_buys_yesterday_after_the_data_and_before_upload():
    wf = yaml.safe_load((WF / "daily.yml").read_text())
    names = [s.get("name") for s in wf["jobs"]["daily"]["steps"]]
    i_data, i_buy, i_up = (names.index("Denni beh"), names.index("Nakup vcerejsich snimku kurzu"),
                           names.index("Ulozeni databaze"))
    assert i_data < i_buy < i_up

"""GitHub disables the scheduled workflows of a public repository after 60
days without a commit. The keepalive job must commit well before that,
change no file, and need nothing but the repository's own token."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "keepalive.yml"


def test_weekly_check_commits_long_before_60_days():
    wf = yaml.safe_load(WF.read_text())
    trig = wf[True] if True in wf else wf["on"]
    crons = [c["cron"] for c in trig["schedule"]]
    assert crons == ["17 6 * * 1"]                    # weekly: worst gap = threshold + 7 days
    run = wf["jobs"]["keepalive"]["steps"][-1]["run"]
    threshold = int(run.split('-lt ')[1].split(' ')[0].strip('"];'))
    assert threshold + 7 < 60
    assert wf["permissions"] == {"contents": "write"}


def test_it_changes_no_file_and_uses_no_secret():
    text = WF.read_text()
    run = yaml.safe_load(text)["jobs"]["keepalive"]["steps"][-1]["run"]
    assert "--allow-empty" in run and "git add" not in run and "git push" in run
    assert "secrets." not in text

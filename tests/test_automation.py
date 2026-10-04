"""The launchd jobs call make targets that exist, at the times the docs
promise, through the wrapper - and the daily run covers every data step."""
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"daily": (12, 30), "odds-morning": (16, 0), "odds-closing": (17, 0)}


def _plists():
    return {p.stem.replace("com.nhltool.", ""): plistlib.loads(p.read_bytes())
            for p in (ROOT / "automation").glob("*.plist")}


def test_jobs_times_and_targets():
    plists = _plists()
    assert set(plists) == set(EXPECTED)
    makefile = (ROOT / "Makefile").read_text()
    for job, (h, m) in EXPECTED.items():
        p = plists[job]
        assert p["Label"] == f"com.nhltool.{job}"
        assert (p["StartCalendarInterval"]["Hour"], p["StartCalendarInterval"]["Minute"]) == (h, m)
        args = p["ProgramArguments"]
        assert args[1].endswith("scripts/daily_wrapper.sh") and args[2] == job
        assert args[3] == "make" and re.search(rf"^{args[4]}:", makefile, re.M)
        assert p["RunAtLoad"] is False


def test_morning_job_matches_the_pre_registered_anchor():
    """16:00 CZ is the 10:00 ET anchor written in the phase 0 plan."""
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
    assert cfg["odds"]["morning_et"] == "10:00"
    assert EXPECTED["odds-morning"] == (16, 0)


def test_docs_list_the_same_times():
    doc = (ROOT / "docs" / "automation.md").read_text()
    for job, (h, m) in EXPECTED.items():
        assert f"| {h:02d}:{m:02d} |" in doc and f"com.nhltool.{job}" in doc


def test_daily_run_covers_every_data_step_with_the_live_season():
    from daily_collect import STEPS, commands
    names = [s[0] for s in STEPS]
    assert names == ["schedule", "rosters", "boxscores", "toi", "players", "pbp",
                     "penalties", "officials", "refprobe", "rematch"]
    for name, cmd in commands("2026-27"):
        if name not in ("players", "refprobe", "rematch"):
            assert cmd[-2:] == ["--season", "2026-27"]

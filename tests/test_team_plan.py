"""The team markets plan is frozen at the user's approval (4. 10. 2026):
the text above the end marker must keep the fingerprint written below it;
changes go below the marker as dated amendments."""
import hashlib
import re
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "docs" / "team_markets_plan.md"
MARK = "<!-- konec schváleného znění -->"


def test_approved_text_keeps_its_fingerprint():
    text = PLAN.read_text()
    assert text.count(MARK) == 1
    approved, tail = text.split(MARK)
    m = re.search(r"\*\*SHA-256 `([0-9a-f]{64})`\*\*", tail)
    assert m, "fingerprint missing below the marker"
    assert hashlib.sha256(approved.encode()).hexdigest() == m.group(1)
    assert "schváleno uživatelem 4. 10. 2026" in approved


def test_team_model_file_matches_the_fingerprint_in_the_plan():
    import json
    root = PLAN.parents[1]
    tail = PLAN.read_text().split(MARK)[1]
    m = re.search(r"`models/naive_team\.json`, \*\*SHA-256 `([0-9a-f]{64})`\*\*", tail)
    assert m, "freeze note (amendment T-2) missing from the plan"
    model = root / "models" / "naive_team.json"
    assert hashlib.sha256(model.read_bytes()).hexdigest() == m.group(1)
    assert json.loads(model.read_text())["trained_on"] == ["2023-24", "2024-25"]


def test_team_fit_script_refuses_to_overwrite(monkeypatch, capsys):
    import pytest

    import fit_naive_team
    monkeypatch.setattr("sys.argv", ["fit_naive_team.py"])
    with pytest.raises(SystemExit):
        fit_naive_team.main()
    assert "zamrazeny" in capsys.readouterr().out

"""The models v2 plan is frozen at the user's approval (10. 10. 2026)."""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
PLAN = ROOT / "docs" / "models_v2_plan.md"
MARK = "<!-- konec schváleného znění -->"


def test_approved_text_keeps_its_fingerprint():
    text = PLAN.read_text()
    assert text.count(MARK) == 1
    approved, tail = text.split(MARK)
    m = re.search(r"\*\*SHA-256 `([0-9a-f]{64})`\*\*", tail)
    assert m, "fingerprint missing below the marker"
    assert hashlib.sha256(approved.encode()).hexdigest() == m.group(1)
    assert "SCHVÁLENO uživatelem 10. 10. 2026" in approved
    assert "10 500 kreditů" in tail                      # the cap of the pre-approved purchase


def _frozen(name: str) -> dict:
    tail = PLAN.read_text().split(MARK)[1]
    m = re.search(rf"`models/{re.escape(name)}`, \*\*SHA-256\s+`([0-9a-f]{{64}})`\*\*", tail)
    assert m, f"freeze note of {name} missing from the plan"
    path = ROOT / "models" / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == m.group(1)
    return json.loads(path.read_text())


def test_team_v2_is_frozen_and_built_on_the_frozen_v1(monkeypatch, capsys):
    body = _frozen("team_v2.json")
    assert body["trained_on"] == ["2023-24", "2024-25"]
    v1 = ROOT / "models" / "naive_team.json"
    assert body["builds_on"]["naive_team.json"] == hashlib.sha256(v1.read_bytes()).hexdigest()
    assert set(body["penalties"]["cal"]) == {"3.5", "4.5"} == set(body["referees"]["cal"])
    import fit_team_v2
    monkeypatch.setattr("sys.argv", ["fit_team_v2.py"])
    with pytest.raises(SystemExit):
        fit_team_v2.main()
    assert "zamrazeny" in capsys.readouterr().out


def test_player_v2_is_frozen_and_built_on_the_frozen_models(monkeypatch, capsys):
    body = _frozen("player_v2.json")
    assert body["trained_on"] == ["2023-24", "2024-25"]
    for name in ("naive_sog.json", "naive_team.json"):
        assert body["builds_on"][name] == hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest()
    assert 0 <= body["alpha"] <= 1 and 0 <= body["pi"] <= 2 and set(body["coef"]) == {"c0", "B_team", "B_opp"}
    import fit_player_v2
    monkeypatch.setattr("sys.argv", ["fit_player_v2.py"])
    with pytest.raises(SystemExit):
        fit_player_v2.main()
    assert "zamrazeny" in capsys.readouterr().out


def test_team_v2b_is_frozen_on_top_of_the_frozen_block_a():
    body = _frozen("team_v2b.json")
    assert body["trained_on"] == ["2023-24", "2024-25"] and body["min_books"] == 3
    for name in ("naive_team.json", "team_v2.json"):
        assert body["builds_on"][name] == hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest()
    assert set(body["shots"]["coef"]) == {"S0", "S1", "S2"} == set(body["penalties"]["coef"])


def test_player_v2b_is_frozen_on_top_of_the_frozen_block_a():
    body = _frozen("player_v2b.json")
    assert body["trained_on"] == ["2023-24", "2024-25"] and body["min_books"] == 3
    for name in ("naive_team.json", "player_v2.json"):
        assert body["builds_on"][name] == hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest()
    assert set(body["coef"]) == {"S0", "S1", "S2"}

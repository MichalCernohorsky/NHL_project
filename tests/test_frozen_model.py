"""The naive shots model is frozen (plan, 'Zamrazení naivního modelu'):
its file must keep the fingerprint written in the plan, and the fit
script must refuse to overwrite it."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "naive_sog.json"


def test_model_file_matches_the_fingerprint_in_the_plan():
    plan = (ROOT / "docs" / "market_discovery_plan.md").read_text()
    m = re.search(r"`models/naive_sog\.json`, \*\*SHA-256 `([0-9a-f]{64})`\*\*", plan)
    assert m, "freeze note missing from the plan"
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == m.group(1)


def test_model_was_trained_on_training_seasons_only():
    model = json.loads(MODEL.read_text())
    assert model["trained_on"] == ["2023-24", "2024-25"]
    assert "2025-26" not in json.dumps(model["trained_on"])


def test_fit_script_refuses_to_overwrite(monkeypatch, capsys):
    import pytest

    import fit_naive_sog
    monkeypatch.setattr("sys.argv", ["fit_naive_sog.py"])
    with pytest.raises(SystemExit):
        fit_naive_sog.main()
    assert "zamrazeny" in capsys.readouterr().out

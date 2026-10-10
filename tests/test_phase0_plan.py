"""The phase 0 plan is frozen at the user's approval (10. 10. 2026, before
the stage A purchase): the text above the end marker must keep the
fingerprint written below it; changes go below the marker, dated."""
import hashlib
import re
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "docs" / "market_discovery_plan.md"
MARK = "<!-- konec schváleného znění -->"


def test_approved_text_keeps_its_fingerprint():
    text = PLAN.read_text()
    assert text.count(MARK) == 1
    approved, tail = text.split(MARK)
    m = re.search(r"\*\*SHA-256 `([0-9a-f]{64})`\*\*", tail)
    assert m, "fingerprint missing below the marker"
    assert hashlib.sha256(approved.encode()).hexdigest() == m.group(1)
    assert "SCHVÁLENO uživatelem 10. 10. 2026" in approved


def test_what_was_fixed_before_the_purchase():
    approved = PLAN.read_text().split(MARK)[0]
    assert "m = 0,0874" in approved and "6 hráčů na zápas" in approved          # D1, D2 via D8
    assert "nejvýš 3 342 kreditů" in approved                                   # one market, stage A
    assert "`models/naive_sog.json`, **SHA-256 `" in approved                   # the model was frozen first

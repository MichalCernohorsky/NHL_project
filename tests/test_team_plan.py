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

"""The market-as-model plan is frozen at the user's approval (10. 10. 2026):
the text above the end marker keeps the fingerprint written below it."""
import hashlib
import re
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "docs" / "topdown_plan.md"
MARK = "<!-- konec schváleného znění -->"


def test_approved_text_keeps_its_fingerprint():
    text = PLAN.read_text()
    assert text.count(MARK) == 1
    approved, tail = text.split(MARK)
    m = re.search(r"\*\*SHA-256 `([0-9a-f]{64})`\*\*", tail)
    assert m, "fingerprint missing below the marker"
    assert hashlib.sha256(approved.encode()).hexdigest() == m.group(1)
    assert "SCHVÁLENO uživatelem 10. 10. 2026" in approved
    assert "1,03 / p" in approved and "aspoň 3 knihy" in approved          # the fixed rule

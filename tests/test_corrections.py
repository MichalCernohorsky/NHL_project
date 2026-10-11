"""NHL corrections after a game (docs/models_v2_notes.md, amendment N-3):
games of the live season are checked again for 10 days and re-downloaded
when the NHL changed them; settled numbers stay."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs" / "models_v2_notes.md"


def test_amendment_n3_keeps_its_fingerprint():
    text = NOTES.read_text()
    start = text.index("**N-3 (11. 10. 2026")
    end = text.index("<!-- konec dodatku N-3 -->")
    m = re.search(r"Otisk dodatku N-3 .*?\*\*SHA-256\s+`([0-9a-f]{64})`\*\*", text[end:], re.S)
    assert m, "fingerprint of N-3 missing below its end marker"
    assert hashlib.sha256(text[start:end].encode()).hexdigest() == m.group(1)

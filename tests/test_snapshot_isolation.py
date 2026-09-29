"""Every reader of the odds table must say WHICH snapshot it reads.

Lesson carried over from NBA (tests/test_snapshot_isolation.py there): once
morning and closing rows share a table, a query that does not name the
snapshot silently picks the better of the two prices - a best-of-two no
bettor ever gets - and inflates every ROI built on it. The NHL table holds
both kinds from its first row, so the rule applies from the first reader.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files allowed to read across every snapshot kind, each for a stated reason.
ALL_KINDS_ALLOWED = {
    # status line / coverage counts per kind; no analysis
    "scripts/report.py",
    # release manifest: newest snapshot time and row count, a freshness
    # check of the file - no analysis
    "scripts/db_release.py",
}

PINNED = re.compile(r"snapshot_kind\s*(=|IN|IS)|snapshot_time\s*=\s*\?", re.I)


def _odds_queries(source: str):
    for m in re.finditer(r"FROM\s+odds\b", source):
        end = source.find('"""', m.end())
        if end == -1 or end - m.end() > 900:
            end = min(len(source), m.end() + 400)
        yield source[m.start():end]


def test_every_odds_reader_names_its_snapshot():
    offenders = []
    for path in sorted(list((ROOT / "scripts").glob("*.py"))
                       + list((ROOT / "src").rglob("*.py"))):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALL_KINDS_ALLOWED:
            continue
        for sql in _odds_queries(path.read_text()):
            if not PINNED.search(sql):
                offenders.append(f"{rel}: {sql.splitlines()[0].strip()}")
    assert not offenders, (
        "these queries read odds without choosing a snapshot:\n  "
        + "\n  ".join(offenders))


def test_allowlist_is_not_stale():
    for rel in ALL_KINDS_ALLOWED:
        assert (ROOT / rel).exists(), rel

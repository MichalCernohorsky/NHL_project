"""The Tipsport log is evidence for a pre-registered criterion: every margin
must follow from its two prices, and the summary line must follow from the
rows. (2. 10.: a regex took a price column for the margin and the log
briefly said 'median 1.72 %'.)"""
import re
import statistics
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "docs" / "tipsport_k1_log.md"
ROW = re.compile(r"^\| \d{1,2}\. \d{1,2}\. \| [A-Z]{3}@[A-Z]{3} \|")


def _rows():
    out = []
    for line in LOG.read_text().splitlines():
        if ROW.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append((float(cells[4]), float(cells[5]), float(cells[6])))
    return out


def test_every_margin_follows_from_its_prices():
    rows = _rows()
    assert rows
    for over, under, margin in rows:
        assert abs((1 / over + 1 / under - 1) * 100 - margin) < 0.01


def test_summary_line_matches_the_rows():
    margins = [m for _, _, m in _rows()]
    m = re.search(r"Průběžně \((\d+) dvojic.*?medián marže \*\*([\d.]+) %\*\*, rozsah\s+"
                  r"([\d.]+)–([\d.]+) %", LOG.read_text(), re.S)
    assert m, "summary line missing"
    n, med, lo, hi = int(m[1]), float(m[2]), float(m[3]), float(m[4])
    assert n == len(margins)
    assert abs(med - statistics.median(margins)) < 0.005
    assert (lo, hi) == (min(margins), max(margins))

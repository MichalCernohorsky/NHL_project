"""Secrets never reach git: the key lives only in .env, which is ignored,
and nothing tracked looks like a key or a database."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_IN_URL = re.compile(r"apiKey=(?!\*\*\*)[A-Za-z0-9]{16,}")
KEY_ASSIGNED = re.compile(r"ODDS_API_KEY\s*=\s*['\"]?[A-Za-z0-9]{16,}")


def _tracked_or_all() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others",
                              "--exclude-standard"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
        return [ROOT / p for p in out]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and "data" not in p.parts]


def test_env_and_data_are_gitignored():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in lines
    assert "data/*" in lines


def test_env_example_holds_no_key():
    text = (ROOT / ".env.example").read_text()
    assert re.search(r"^ODDS_API_KEY=\s*$", text, re.M)


def test_no_key_and_no_database_in_files_git_would_see():
    offenders = []
    for path in _tracked_or_all():
        if not path.is_file():
            continue
        if path.suffix in (".db", ".sqlite") or path.name == ".env":
            offenders.append(f"{path.name}: must never be committed")
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if KEY_IN_URL.search(text) or KEY_ASSIGNED.search(text):
            offenders.append(f"{path.relative_to(ROOT)}: looks like an API key")
    assert not offenders, offenders

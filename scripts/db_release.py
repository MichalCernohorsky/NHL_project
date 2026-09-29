#!/usr/bin/env python3
"""Keep data/nhl.db in ONE rolling GitHub release of the PRIVATE data repo.

    python scripts/db_release.py up        # data/nhl.db -> release "db-latest"
    python scripts/db_release.py down      # release -> data/nhl.db
    python scripts/db_release.py status    # manifest only, no download

Same scheme as NBA_tool (scripts/db_release.py): the database never goes
through git; it is one attachment (nhl.db.gz) of one release that is
replaced on every upload. The code repository is PUBLIC, so the target
repository must be given explicitly (NHL_DB_RELEASE_REPO) and is refused
when it is the code repository itself - a release there would be
downloadable by anyone (the database holds purchased odds and, later, the
user's bets).

Safety nets:
- The release body carries a JSON manifest (newest finished game with a box
  score, newest odds snapshot, row counts). `up` refuses to replace remote
  data that is NEWER than the local file, `down` refuses to overwrite a
  local file that is newer than the remote one. --force overrides, loudly.
- The new asset is uploaded under a temporary name first and renamed only
  after the old one is gone, so a failed upload never leaves the release
  empty. `down` checks the SHA-256 from the manifest and swaps the file
  atomically.

Security: the token comes only from the environment (NHL_DATA_TOKEN, or
GITHUB_TOKEN in Actions), travels only in the Authorization header, and is
scrubbed from every message this script prints.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "nhl.db"
CODE_REPO = "MichalCernohorsky/NHL_project"
TAG = "db-latest"
ASSET = "nhl.db.gz"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
TIMEOUT = 120
MANIFEST_RE = re.compile(r"<!-- nhl-db-manifest\s*(\{.*?\})\s*-->", re.S)


class ReleaseError(Exception):
    pass


def token() -> str:
    t = os.environ.get("NHL_DATA_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        raise ReleaseError("chybi token: nastav NHL_DATA_TOKEN (docs/cloud.md, krok 3)")
    return t


def scrub(text: str) -> str:
    t = os.environ.get("NHL_DATA_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return text.replace(t, "***TOKEN***") if t else text


def target_repo() -> str:
    repo = os.environ.get("NHL_DB_RELEASE_REPO", "").strip()
    if not repo:
        raise ReleaseError("NHL_DB_RELEASE_REPO neni nastavene (ma byt "
                           "MichalCernohorsky/NHL_project-data)")
    if repo.lower() == CODE_REPO.lower():
        raise ReleaseError("NHL_DB_RELEASE_REPO ukazuje na VEREJNY repozitar kodu - "
                           "databaze tam nesmi. Ma byt NHL_project-data.")
    return repo


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    h.update(extra or {})
    return h


def _call(method: str, url: str, **kw) -> requests.Response:
    try:
        r = requests.request(method, url, timeout=TIMEOUT, **kw)
    except requests.RequestException as exc:
        raise ReleaseError(scrub(f"sit: {method} {url}: {exc}")) from None
    if r.status_code >= 400 and r.status_code != 404:
        raise ReleaseError(scrub(f"HTTP {r.status_code} {method} {url}: {r.text[:300]}"))
    return r


# ------------------------------------------------------------ manifest

def manifest_of(db: Path) -> dict:
    """What is IN the database (not the file's mtime, which any touch bumps)."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "last_game_with_box": one(
                "SELECT MAX(g.game_date) FROM games g WHERE EXISTS "
                "(SELECT 1 FROM team_game_logs t WHERE t.game_id = g.game_id)"),
            # reads every kind on purpose: freshness of the file, no analysis
            "last_odds_snapshot": one("SELECT MAX(snapshot_time) FROM odds"),
            "player_game_rows": one("SELECT COUNT(*) FROM player_game_logs"),
            "odds_rows": one("SELECT COUNT(*) FROM odds"),
            "state_rows": one("SELECT COUNT(*) FROM backfill_state"),
        }
    finally:
        conn.close()


def behind_anywhere(local: dict, remote: dict) -> list[str]:
    """Axes on which local is OLDER than remote (replacing remote would lose them)."""
    out = []
    for k in ("last_game_with_box", "last_odds_snapshot", "player_game_rows",
              "odds_rows", "state_rows"):
        x, y = local.get(k), remote.get(k)
        if y is not None and (x is None or x < y):
            out.append(f"{k}: lokalne {x}, na GitHubu {y}")
    return out


def body_with(manifest: dict) -> str:
    return ("Databaze NHL_project (data/nhl.db). Spravuje scripts/db_release.py - "
            "nic rucne.\n\n<!-- nhl-db-manifest\n" + json.dumps(manifest, indent=1)
            + "\n-->\n")


def parse_manifest(body: str | None) -> dict | None:
    m = MANIFEST_RE.search(body or "")
    return json.loads(m.group(1)) if m else None


# ------------------------------------------------------------ release

def get_release(repo: str) -> dict | None:
    r = _call("GET", f"{API}/repos/{repo}/releases/tags/{TAG}", headers=_headers())
    return None if r.status_code == 404 else r.json()


def create_release(repo: str) -> dict:
    r = _call("POST", f"{API}/repos/{repo}/releases", headers=_headers(),
              json={"tag_name": TAG, "name": "Databaze (posledni stav)",
                    "body": body_with({}), "prerelease": True})
    if r.status_code == 404:
        raise ReleaseError(f"repozitar {repo} neexistuje nebo k nemu token nema pristup")
    return r.json()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def up(force: bool = False) -> None:
    repo = target_repo()
    if not DB.exists():
        raise ReleaseError(f"{DB} neexistuje")
    local = manifest_of(DB)
    rel = get_release(repo) or create_release(repo)
    remote = parse_manifest(rel.get("body")) or {}
    lost = behind_anywhere(local, remote)
    if lost and not force:
        raise ReleaseError("ODMITNUTO: na GitHubu jsou novejsi data, nahrani by je "
                           "prepsalo:\n  " + "\n  ".join(lost)
                           + "\nNejdriv 'down', nebo --force, pokud vis, co delas.")
    if lost:
        print("POZOR --force: prepisuji novejsi data na GitHubu:\n  " + "\n  ".join(lost))
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "nhl.db"
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(snap)
        src.backup(dst)                 # consistent copy even while jobs write
        src.close()
        dst.close()
        gz = Path(tmp) / ASSET
        with open(snap, "rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        local["sha256_gz"] = sha256(gz)
        local["uploaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tmp_name = f"{ASSET}.new"
        for a in rel.get("assets", []):
            if a["name"] == tmp_name:   # leftover of an interrupted upload
                _call("DELETE", f"{API}/repos/{repo}/releases/assets/{a['id']}",
                      headers=_headers())
        with open(gz, "rb") as f:
            new = _call("POST", f"{UPLOADS}/repos/{repo}/releases/{rel['id']}/assets",
                        params={"name": tmp_name}, data=f,
                        headers=_headers({"Content-Type": "application/gzip"})).json()
    for a in rel.get("assets", []):
        if a["name"] == ASSET:
            _call("DELETE", f"{API}/repos/{repo}/releases/assets/{a['id']}", headers=_headers())
    _call("PATCH", f"{API}/repos/{repo}/releases/assets/{new['id']}", headers=_headers(),
          json={"name": ASSET})
    _call("PATCH", f"{API}/repos/{repo}/releases/{rel['id']}", headers=_headers(),
          json={"body": body_with(local)})
    print(f"nahrano: {repo} {TAG}/{ASSET} | posledni zapas {local['last_game_with_box']}"
          f" | posledni kurz {local['last_odds_snapshot']} | kurzu {local['odds_rows']}")


def down(force: bool = False) -> None:
    repo = target_repo()
    rel = get_release(repo)
    if rel is None:
        raise ReleaseError(f"v {repo} zatim neni vydani {TAG} - nejdriv 'up'")
    remote = parse_manifest(rel.get("body")) or {}
    asset = next((a for a in rel.get("assets", []) if a["name"] == ASSET), None)
    if asset is None:
        raise ReleaseError(f"vydani {TAG} nema prilohu {ASSET}")
    if DB.exists() and not force:
        lost = behind_anywhere(remote, manifest_of(DB))
        if lost:
            raise ReleaseError("ODMITNUTO: lokalni databaze je v necem novejsi nez GitHub, "
                               "stazeni by ji prepsalo:\n  " + "\n  ".join(lost)
                               + "\nNejdriv 'up', nebo --force.")
    DB.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=DB.parent) as tmp:
        gz = Path(tmp) / ASSET
        r = _call("GET", f"{API}/repos/{repo}/releases/assets/{asset['id']}",
                  headers=_headers({"Accept": "application/octet-stream"}), stream=True)
        with open(gz, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        if remote.get("sha256_gz") and sha256(gz) != remote["sha256_gz"]:
            raise ReleaseError("stazeny soubor nesedi s otiskem v manifestu - nic neprepsano")
        out = Path(tmp) / "nhl.db"
        with gzip.open(gz, "rb") as fi, open(out, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        for side in ("-wal", "-shm"):
            Path(str(DB) + side).unlink(missing_ok=True)
        os.replace(out, DB)
    print(f"stazeno: posledni zapas {remote.get('last_game_with_box')} | posledni kurz "
          f"{remote.get('last_odds_snapshot')} | nahrano {remote.get('uploaded_at')}")


def status() -> None:
    repo = target_repo()
    rel = get_release(repo)
    print(json.dumps(parse_manifest(rel.get("body")) if rel else None, indent=1))
    if DB.exists():
        print("lokalne:", json.dumps(manifest_of(DB)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("up", "down", "status"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    try:
        {"up": lambda: up(args.force), "down": lambda: down(args.force),
         "status": status}[args.action]()
    except ReleaseError as exc:
        print(f"CHYBA: {scrub(str(exc))}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

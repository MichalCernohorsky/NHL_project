"""db_release against an in-memory fake of the GitHub API: the database
never goes to the public code repository, newer data is never overwritten
in either direction, the token never appears in output."""
import gzip
import json
import sqlite3

import pytest

import db_release as dr


class FakeGitHub:
    """Just enough of the releases API: one repo, one release, assets."""

    def __init__(self):
        self.release = None
        self.assets = {}          # id -> {"name", "data"}
        self.next_id = 1

    def call(self, method, url, **kw):
        resp = FakeResponse()
        if url.endswith(f"/releases/tags/{dr.TAG}") and method == "GET":
            if self.release is None:
                resp.status_code = 404
            else:
                resp.payload = self._rel()
        elif url.endswith("/releases") and method == "POST":
            self.release = {"id": 7, "body": kw["json"]["body"]}
            resp.payload = self._rel()
        elif "/releases/7/assets" in url and method == "POST":
            aid = self.next_id
            self.next_id += 1
            self.assets[aid] = {"name": kw["params"]["name"], "data": kw["data"].read()}
            resp.payload = {"id": aid}
        elif "/releases/assets/" in url:
            aid = int(url.rsplit("/", 1)[1])
            if method == "DELETE":
                del self.assets[aid]
            elif method == "PATCH":
                self.assets[aid]["name"] = kw["json"]["name"]
            elif method == "GET":
                resp.content_bytes = self.assets[aid]["data"]
        elif url.endswith("/releases/7") and method == "PATCH":
            self.release["body"] = kw["json"]["body"]
        else:
            raise AssertionError(f"unexpected {method} {url}")
        return resp

    def _rel(self):
        return {"id": 7, "body": self.release["body"],
                "assets": [{"id": i, "name": a["name"]} for i, a in self.assets.items()]}


class FakeResponse:
    status_code = 200
    payload = None
    content_bytes = b""
    text = ""

    def json(self):
        return self.payload

    def iter_content(self, n):
        yield self.content_bytes


def _db(path, games=1, odds=0):
    from migrate import apply_migrations, ensure_migrations_table
    conn = sqlite3.connect(path)
    ensure_migrations_table(conn)
    apply_migrations(conn)
    conn.execute("INSERT INTO teams VALUES (1,'AAA','A'),(2,'BBB','B')")
    for i in range(games):
        conn.execute("INSERT INTO games (game_id, season, season_type, game_date,"
                     " home_team_id, away_team_id) VALUES (?, '2025-26', 'regular', ?, 1, 2)",
                     (i + 1, f"2025-10-{i + 1:02d}"))
        conn.execute("INSERT INTO team_game_logs (game_id, team_id, is_home) VALUES (?, 1, 1)",
                     (i + 1,))
    for i in range(odds):
        conn.execute("INSERT INTO odds (event_id, market, side, line, price, bookmaker,"
                     " snapshot_time, snapshot_kind, player_name_raw) VALUES"
                     " ('e', 'm', 'over', ?, 1.9, 'b', '2025-10-01T00:00:00Z', 'closing', 'p')",
                     (i + 0.5,))
    conn.commit()
    conn.close()


@pytest.fixture
def gh(tmp_path, monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(dr, "_call", fake.call)
    monkeypatch.setattr(dr, "DB", tmp_path / "nhl.db")
    monkeypatch.setenv("NHL_DATA_TOKEN", "tok_secret_123")
    monkeypatch.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project-data")
    return fake


def test_public_code_repo_is_refused(monkeypatch):
    monkeypatch.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project")
    with pytest.raises(dr.ReleaseError, match="VEREJNY"):
        dr.target_repo()
    monkeypatch.delenv("NHL_DB_RELEASE_REPO")
    with pytest.raises(dr.ReleaseError):
        dr.target_repo()


def test_up_then_down_roundtrip(gh):
    _db(dr.DB, games=3, odds=2)
    dr.up()
    names = [a["name"] for a in gh.assets.values()]
    assert names == [dr.ASSET]                      # temp name renamed, nothing left over
    manifest = dr.parse_manifest(gh.release["body"])
    assert manifest["odds_rows"] == 2 and manifest["last_game_with_box"] == "2025-10-03"
    assert json.loads(json.dumps(manifest))["sha256_gz"]
    dr.DB.unlink()
    dr.down()
    conn = sqlite3.connect(dr.DB)
    assert conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0] == 2


def test_up_refuses_to_overwrite_newer_remote(gh, tmp_path):
    _db(dr.DB, games=3)
    dr.up()
    dr.DB.unlink()
    _db(dr.DB, games=2)                             # an older machine's copy
    with pytest.raises(dr.ReleaseError, match="ODMITNUTO"):
        dr.up()
    dr.up(force=True)                               # explicit override works


def test_down_refuses_to_overwrite_newer_local(gh):
    _db(dr.DB, games=2)
    dr.up()
    dr.DB.unlink()
    _db(dr.DB, games=3, odds=1)                     # local has more
    with pytest.raises(dr.ReleaseError, match="ODMITNUTO"):
        dr.down()


def test_corrupt_download_never_replaces_the_file(gh):
    _db(dr.DB, games=2)
    dr.up()
    for a in gh.assets.values():
        a["data"] = gzip.compress(b"garbage")
    before = dr.DB.read_bytes()
    with pytest.raises(dr.ReleaseError, match="nesedi"):
        dr.down(force=True)
    assert dr.DB.read_bytes() == before


def test_token_is_scrubbed(gh):
    assert "tok_secret_123" not in dr.scrub("HTTP 401 with tok_secret_123 inside")

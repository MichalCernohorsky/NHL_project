"""Hosted dashboard (docs/streamlit.md): the password gate is fail-closed
and the database comes from the private release, never the other way."""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest  # noqa: E402

from dashboard import cloud  # noqa: E402

APP = str(ROOT / "dashboard" / "app.py")
PASSWORD = "dlouhe-zkusebni-heslo"


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    """The app as Streamlit Cloud runs it: no local flag, an empty database."""
    from migrate import apply_migrations, ensure_migrations_table
    path = tmp_path / "nhl.db"
    conn = sqlite3.connect(path)
    ensure_migrations_table(conn)
    apply_migrations(conn)
    conn.close()
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    monkeypatch.delenv("NHL_DASHBOARD_LOCAL", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    cloud.ensure_db.clear()
    yield monkeypatch
    cloud.ensure_db.clear()


def _texts(at) -> str:
    return " ".join(str(e.value) for e in list(at.markdown) + list(at.error))


def test_hosted_app_without_password_is_locked(hosted):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "zamčený" in _texts(at)
    assert not at.text_input and not at.sidebar.markdown   # nothing else rendered


def test_short_password_keeps_it_locked(hosted):
    hosted.setenv("APP_PASSWORD", "kratke")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert "zamčený" in _texts(at) and not at.text_input


def test_wrong_password_shows_nothing(hosted):
    hosted.setenv("APP_PASSWORD", PASSWORD)
    hosted.setattr(cloud.time, "sleep", lambda s: None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert len(at.text_input) == 1 and not at.sidebar.markdown
    at.text_input[0].input("neco jineho")
    at.button[0].click().run()
    assert "Špatné heslo" in _texts(at)
    assert cloud.AUTH_FLAG not in at.session_state
    assert not at.sidebar.markdown
    assert PASSWORD not in _texts(at)


def test_too_many_tries_lock_the_session(hosted):
    hosted.setenv("APP_PASSWORD", PASSWORD)
    hosted.setattr(cloud.time, "sleep", lambda s: None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    for _ in range(cloud.MAX_TRIES):
        at.text_input[0].input("spatne")
        at.button[0].click().run()
    at.run()
    assert "Příliš mnoho pokusů" in _texts(at) and not at.text_input


def test_right_password_opens_the_dashboard(hosted):
    hosted.setenv("APP_PASSWORD", PASSWORD)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input(PASSWORD)
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[cloud.AUTH_FLAG] is True
    assert at.sidebar.markdown                       # the router rendered


def test_local_flag_skips_the_gate(hosted):
    hosted.setenv("NHL_DASHBOARD_LOCAL", "1")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.sidebar.markdown and "Heslo" not in [t.label for t in at.text_input]


def test_password_compare():
    assert cloud.password_ok("abc", "abc")
    assert not cloud.password_ok("abc", "abd")
    assert not cloud.password_ok("", "abc")
    assert cloud.password_ok("žluťoučký", "žluťoučký")


# ------------------------------------------------------------ database

class FakeRelease:
    """Stand-in for scripts/db_release.py: counts downloads, no network."""

    class ReleaseError(Exception):
        pass

    def __init__(self, tmp_path, sha="aaa", repo_error=None):
        self.DB = tmp_path / "data" / "nhl.db"
        self.DB.parent.mkdir(parents=True)
        self.sha, self.repo_error, self.downloads = sha, repo_error, 0

    def target_repo(self):
        if self.repo_error:
            raise self.ReleaseError(self.repo_error)
        return "MichalCernohorsky/NHL_project-data"

    def get_release(self, repo):
        return {"body": "manifest"}

    def parse_manifest(self, body):
        return {"sha256_gz": self.sha, "uploaded_at": "2026-10-04T10:31:00+00:00"}

    def down(self, force=False):
        assert force
        self.downloads += 1
        self.DB.write_text("db")

    def scrub(self, text):
        return text.replace("github_pat_SECRET", "***TOKEN***")


@pytest.fixture
def not_local(monkeypatch):
    monkeypatch.delenv("NHL_DASHBOARD_LOCAL", raising=False)
    monkeypatch.delenv("NHL_DASHBOARD_DB", raising=False)
    return monkeypatch


def test_fetch_downloads_once_and_again_only_for_a_newer_upload(tmp_path, not_local):
    rel = FakeRelease(tmp_path)
    assert cloud.fetch_db(rel)["state"] == "downloaded"
    out = cloud.fetch_db(rel)
    assert out == {"state": "fresh", "uploaded_at": "2026-10-04T10:31:00+00:00"}
    assert rel.downloads == 1
    rel.sha = "bbb"                                  # the cloud run uploaded a new one
    assert cloud.fetch_db(rel)["state"] == "downloaded" and rel.downloads == 2


def test_fetch_downloads_again_after_the_disk_was_wiped(tmp_path, not_local):
    rel = FakeRelease(tmp_path)
    cloud.fetch_db(rel)
    rel.DB.unlink()
    assert cloud.fetch_db(rel)["state"] == "downloaded" and rel.downloads == 2


def test_fetch_error_is_scrubbed_and_does_not_raise(tmp_path, not_local):
    rel = FakeRelease(tmp_path, repo_error="HTTP 401 github_pat_SECRET")
    out = cloud.fetch_db(rel)
    assert out["state"] == "error" and "SECRET" not in out["error"]
    assert rel.downloads == 0


def test_fetch_never_runs_on_the_mac_or_over_an_explicit_file(tmp_path, monkeypatch):
    rel = FakeRelease(tmp_path)
    monkeypatch.setenv("NHL_DASHBOARD_LOCAL", "1")
    assert cloud.fetch_db(rel) == {"state": "local"}
    monkeypatch.delenv("NHL_DASHBOARD_LOCAL")
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(tmp_path / "other.db"))
    assert cloud.fetch_db(rel) == {"state": "custom"}
    assert rel.downloads == 0


def test_release_script_loads_and_refuses_the_public_repo(not_local):
    rel = cloud._release()
    not_local.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project")
    with pytest.raises(rel.ReleaseError):
        rel.target_repo()


def test_secrets_file_is_ignored_and_make_sets_the_local_flag():
    assert ".streamlit/secrets.toml" in (ROOT / ".gitignore").read_text()
    assert "NHL_DASHBOARD_LOCAL=1 streamlit run" in (ROOT / "Makefile").read_text()


# --------------------------------------------- start the daily job from the page

class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise cloud.requests.HTTPError(f"HTTP {self.status_code}")


def _github(monkeypatch, runs=(), dispatch_status=204, fail=None):
    calls = []

    def request(method, url, **kw):
        calls.append((method, url, kw))
        if fail:
            raise cloud.requests.ConnectionError(fail)
        if url.endswith("/runs"):
            return _Resp(body={"workflow_runs": [{"status": s} for s in runs]})
        if url.endswith("/dispatches"):
            return _Resp(dispatch_status)
        return _Resp(body={"default_branch": "hlavni-vetev"})

    monkeypatch.setattr(cloud.requests, "request", request)
    return calls


NOON = cloud.datetime(2026, 10, 10, 12, 0, tzinfo=cloud.timezone.utc)
TOKEN = "github_pat_ACTIONSSECRET"


def test_dispatch_needs_a_token_and_never_runs_too_early(monkeypatch):
    calls = _github(monkeypatch)
    assert cloud.dispatch_daily(NOON)[0] is False and calls == []          # no token
    monkeypatch.setenv("NHL_ACTIONS_TOKEN", TOKEN)
    early = cloud.datetime(2026, 10, 10, 11, 29, tzinfo=cloud.timezone.utc)
    ok, msg = cloud.dispatch_daily(early)
    assert ok is False and "11:30" in msg and calls == []
    assert not cloud.too_early(cloud.datetime(2026, 10, 10, 11, 30, tzinfo=cloud.timezone.utc))


def test_dispatch_starts_the_daily_workflow_on_the_default_branch(monkeypatch):
    monkeypatch.setenv("NHL_ACTIONS_TOKEN", TOKEN)
    calls = _github(monkeypatch, runs=("completed", "completed"))
    ok, msg = cloud.dispatch_daily(NOON)
    assert ok is True and "spuštěn" in msg
    method, url, kw = calls[-1]
    assert method == "POST" and url.endswith(
        "/repos/MichalCernohorsky/NHL_project/actions/workflows/daily.yml/dispatches")
    assert kw["json"] == {"ref": "hlavni-vetev"}
    assert all(c[2]["headers"]["Authorization"] == f"Bearer {TOKEN}" for c in calls)
    assert all(TOKEN not in c[1] for c in calls)                            # never in a URL


def test_dispatch_does_not_stack_runs_and_hides_the_token_in_errors(monkeypatch):
    monkeypatch.setenv("NHL_ACTIONS_TOKEN", TOKEN)
    calls = _github(monkeypatch, runs=("in_progress",))
    ok, msg = cloud.dispatch_daily(NOON)
    assert ok is False and "už běží" in msg and not any(c[0] == "POST" for c in calls)
    _github(monkeypatch, dispatch_status=403)
    assert cloud.dispatch_daily(NOON) == (False, "GitHub běh nespustil (HTTP 403). Zkontroluj oprávnění tokenu.")
    _github(monkeypatch, fail=f"cannot reach host with {TOKEN}")
    ok, msg = cloud.dispatch_daily(NOON)
    assert ok is False and TOKEN not in msg and "***TOKEN***" in msg


def test_sidebar_offers_the_run_button_only_with_a_token(hosted):
    hosted.setenv("NHL_DASHBOARD_LOCAL", "1")
    at = AppTest.from_file(APP, default_timeout=30).run()
    labels = [b.label for b in at.sidebar.button]
    assert "▶ Spustit denní běh" not in labels and "↻ Obnovit data" not in labels   # local, no token
    hosted.setenv("NHL_ACTIONS_TOKEN", TOKEN)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert "▶ Spustit denní běh" in [b.label for b in at.sidebar.button]


def test_no_test_can_dispatch_for_real():
    import os
    assert "NHL_ACTIONS_TOKEN" not in os.environ          # conftest removes it for every test

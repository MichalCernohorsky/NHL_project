"""Hosting on Streamlit Community Cloud (docs/streamlit.md).

The code repository is public, so the hosted app is reachable by anyone who
has its address, while the database holds purchased odds (redistribution
forbidden) and the pages can write tickets. Two things follow:

- gate(): nothing renders before the password. Fail-closed: only
  NHL_DASHBOARD_LOCAL=1 (set by `make dashboard` on the Mac) skips it; a
  hosted app with no APP_PASSWORD stays locked instead of opening.
- ensure_db(): the hosted disk starts empty and is wiped on every restart.
  The database comes from the release of the PRIVATE data repository
  (scripts/db_release.py) and is fetched again once the cloud run has
  uploaded a newer one. The dashboard never writes it (mode=ro).

Security: password and token come from the environment or st.secrets, are
never rendered, logged or put into a URL; the password is compared in
constant time.
"""
from __future__ import annotations

import hmac
import importlib.util
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
AUTH_FLAG = "_nhl_auth"
TRIES = "_nhl_auth_tries"
MAX_TRIES = 5
MIN_PASSWORD = 8
CHECK_EVERY_S = 900          # how often a running app asks GitHub for a newer database
MARKER = ".release_sha"
SECRETS = ("NHL_DATA_TOKEN", "NHL_DB_RELEASE_REPO")
# "Spustit denní běh" (docs/streamlit.md): GitHub starts scheduled runs hours
# late, so the user can start the daily job from the dashboard. Needs its own
# token (NHL_ACTIONS_TOKEN: Actions read/write on the code repository only).
CODE_REPO = "MichalCernohorsky/NHL_project"
WORKFLOW = "daily.yml"
GH_API = "https://api.github.com"
EARLIEST_UTC = (11, 30)      # docs/cloud.md: an earlier snapshot is too thin for tips
BUSY = ("queued", "in_progress", "requested", "waiting", "pending")


def is_local() -> bool:
    return os.environ.get("NHL_DASHBOARD_LOCAL") == "1"


def setting(name: str) -> str | None:
    """Environment first, then Streamlit secrets; None when neither has it."""
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:  # noqa: BLE001 - no secrets file outside Streamlit Cloud
        return None
    return None


def password_ok(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


# ------------------------------------------------------------------ gate

def gate() -> None:
    """Stop the run unless this session has entered the password."""
    if is_local() or st.session_state.get(AUTH_FLAG):
        return
    expected = setting("APP_PASSWORD")
    if not expected or len(expected) < MIN_PASSWORD:
        st.error("Dashboard je zamčený: v nastavení aplikace na Streamlitu chybí "
                 f"APP_PASSWORD (aspoň {MIN_PASSWORD} znaků). Postup: docs/streamlit.md.")
        st.stop()
    tries = st.session_state.get(TRIES, 0)
    st.markdown("### 🏒 NHL Props")
    if tries >= MAX_TRIES:
        st.error("Příliš mnoho pokusů. Načti stránku znovu.")
        st.stop()
    with st.form("gate"):
        given = st.text_input("Heslo", type="password")
        sent = st.form_submit_button("Vstoupit")
    if sent:
        if password_ok(given, expected):
            st.session_state[AUTH_FLAG] = True
            st.rerun()
        st.session_state[TRIES] = tries + 1
        time.sleep(1.0)      # slows down guessing
        st.error("Špatné heslo.")
    st.stop()


# -------------------------------------------------------------- database

def _release():
    """scripts/db_release.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("db_release",
                                                  ROOT / "scripts" / "db_release.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch_db(rel=None) -> dict:
    """Make data/nhl.db the newest uploaded database.
    -> {"state": local|custom|fresh|downloaded|error, "uploaded_at", "error"}"""
    if is_local():
        return {"state": "local"}
    if os.environ.get("NHL_DASHBOARD_DB"):
        return {"state": "custom"}          # an explicit file: never replaced
    for name in SECRETS:                    # db_release.py reads the environment
        value = setting(name)
        if value and not os.environ.get(name):
            os.environ[name] = value
    rel = rel or _release()
    try:
        release = rel.get_release(rel.target_repo())
        remote = rel.parse_manifest(release.get("body")) if release else None
        if not remote or not remote.get("sha256_gz"):
            raise rel.ReleaseError("v datovém repozitáři zatím není nahraná databáze")
        marker = rel.DB.parent / MARKER
        if rel.DB.exists() and marker.exists() and marker.read_text() == remote["sha256_gz"]:
            return {"state": "fresh", "uploaded_at": remote.get("uploaded_at")}
        rel.down(force=True)                # this copy is read-only, nothing to lose
        marker.write_text(remote["sha256_gz"])
        return {"state": "downloaded", "uploaded_at": remote.get("uploaded_at")}
    except rel.ReleaseError as exc:
        return {"state": "error", "error": rel.scrub(str(exc))}


@st.cache_resource(ttl=CHECK_EVERY_S, show_spinner="Stahuji databázi…")
def ensure_db() -> dict:
    """fetch_db once per CHECK_EVERY_S for the whole app, not per click."""
    return fetch_db()


def hosted_setup() -> None:
    """Things only the hosted app needs, before any page runs."""
    if is_local():
        return
    # ~ may not be writable there; data/ is (the database lands in it too)
    os.environ.setdefault("NHL_BETS_DIR", str(ROOT / "data" / "bets_store"))


# ------------------------------------------------------ start the daily job

def dispatch_token() -> str | None:
    return setting("NHL_ACTIONS_TOKEN")


def too_early(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return (now.hour, now.minute) < EARLIEST_UTC


def _gh(method: str, path: str, token: str, **kw):
    return requests.request(method, f"{GH_API}{path}", timeout=20,
                            headers={"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json"}, **kw)


def daily_run_state(token: str) -> str | None:
    """The status of a daily run that is waiting or running, else None."""
    r = _gh("GET", f"/repos/{CODE_REPO}/actions/workflows/{WORKFLOW}/runs", token,
            params={"per_page": 5})
    r.raise_for_status()
    for run in r.json().get("workflow_runs", []):
        if run.get("status") in BUSY:
            return run["status"]
    return None


def dispatch_daily(now: datetime | None = None) -> tuple[bool, str]:
    """Start the daily cloud job. -> (started, message for the user). The job
    is idempotent: a second run the same day buys and snapshots nothing again."""
    token = dispatch_token()
    if not token:
        return False, "Chybí NHL_ACTIONS_TOKEN (postup: docs/streamlit.md)."
    if too_early(now):
        return False, ("Denní běh jde spustit nejdřív v 11:30 UTC (13:30 letního, 12:30 zimního "
                       "času) — dřív by tipy stály na neúplných kurzech.")
    try:
        if daily_run_state(token):
            return False, "Denní běh už běží nebo čeká ve frontě. Za pár minut dej Obnovit data."
        repo = _gh("GET", f"/repos/{CODE_REPO}", token)
        repo.raise_for_status()
        r = _gh("POST", f"/repos/{CODE_REPO}/actions/workflows/{WORKFLOW}/dispatches", token,
                json={"ref": repo.json()["default_branch"]})
        if r.status_code != 204:
            return False, f"GitHub běh nespustil (HTTP {r.status_code}). Zkontroluj oprávnění tokenu."
        return True, "Denní běh spuštěn. Hotovo bývá za 2–3 minuty, pak dej Obnovit data."
    except (requests.RequestException, KeyError, ValueError) as exc:
        return False, "GitHub neodpověděl: " + str(exc).replace(token, "***TOKEN***")[:200]

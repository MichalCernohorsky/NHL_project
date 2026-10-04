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
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
AUTH_FLAG = "_nhl_auth"
TRIES = "_nhl_auth_tries"
MAX_TRIES = 5
MIN_PASSWORD = 8
CHECK_EVERY_S = 900          # how often a running app asks GitHub for a newer database
MARKER = ".release_sha"
SECRETS = ("NHL_DATA_TOKEN", "NHL_DB_RELEASE_REPO")


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

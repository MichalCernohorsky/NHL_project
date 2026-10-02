"""Client for the-odds-api.com (api.the-odds-api.com, v4) - historical and live odds.

Security rules (hard):
- The API key comes exclusively from .env (ODDS_API_KEY), which is
  gitignored. The key is injected into requests here and NEVER appears in
  URLs we log, in exceptions, in cache filenames or in any output.
- Every response's x-requests-remaining/-used headers are appended to
  data/odds_quota.log and returned to the caller for budget enforcement.

Vendor note: this is the-odds-api.com. The similarly named theoddsapi.com
is a DIFFERENT service and must not be used.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://api.the-odds-api.com/v4"
QUOTA_LOG = ROOT / "data" / "odds_quota.log"
MIN_INTERVAL_S = 0.4


class OddsApiError(Exception):
    """API error with the key scrubbed from the message."""


def load_api_key(env_path: Path | None = None) -> str:
    # GitHub Actions passes the key as an encrypted secret in the process
    # environment; on the Mac it lives in .env. Never in a file in git.
    import os
    if os.environ.get("ODDS_API_KEY", "").strip():
        key = os.environ["ODDS_API_KEY"].strip()
        if not key.isascii() or not key.isalnum():
            raise OddsApiError(
                f"ODDS_API_KEY ma spatny tvar (delka {len(key)}, nepovolenych znaku "
                f"{sum(not (c.isascii() and c.isalnum()) for c in key)}) - vloz do "
                "secretu jen samotny klic")
        return key
    env_path = env_path or ROOT / ".env"
    if not env_path.exists():
        raise OddsApiError(".env file not found - create it with ODDS_API_KEY=...")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("ODDS_API_KEY"):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise OddsApiError("ODDS_API_KEY not found in .env")


def _scrub(text: str, key: str) -> str:
    text = text.replace(key, "***KEY***")
    return re.sub(r"apiKey=[^&\s\"']+", "apiKey=***KEY***", text)


class OddsClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or load_api_key()
        self.last_remaining: float | None = None
        self.last_used: float | None = None
        self._last_call = 0.0

    def _log_quota(self, path: str, resp: requests.Response):
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        self.last_remaining = float(remaining) if remaining else self.last_remaining
        self.last_used = float(used) if used else self.last_used
        QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(QUOTA_LOG, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
                    f" {path} status={resp.status_code}"
                    f" remaining={remaining} used={used}\n")

    def get(self, path: str, **params) -> tuple[object, dict]:
        """GET {BASE}{path}; returns (json, {'remaining':..,'used':..}).

        Raises OddsApiError with a scrubbed message on any non-200.
        """
        wait = self._last_call + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

        try:
            resp = requests.get(f"{BASE}{path}",
                                params={**params, "apiKey": self.api_key},
                                timeout=30)
        except requests.RequestException as exc:
            raise OddsApiError(_scrub(f"network error on {path}: {exc}",
                                      self.api_key)) from None
        self._log_quota(path, resp)
        if resp.status_code != 200:
            raise OddsApiError(_scrub(
                f"HTTP {resp.status_code} on {path}: {resp.text[:300]}",
                self.api_key))
        return resp.json(), {"remaining": self.last_remaining,
                             "used": self.last_used}


def cache_response(subdir: str, name: str, payload) -> Path:
    """Raw JSON cache under data/raw_cache/odds/ (never contains the key)."""
    path = ROOT / "data" / "raw_cache" / "odds" / subdir / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f)
    return path

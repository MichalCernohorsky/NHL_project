"""Shared HTTP plumbing: throttling, retries with exponential backoff,
and a JSON disk cache so no successful download ever happens twice."""
import json
import random
import time
from json import JSONDecodeError
from pathlib import Path

import requests


class NotFoundError(Exception):
    """Resource does not exist upstream (HTTP 404) - a data gap, not an error."""


class Throttle:
    """Enforces a minimum interval + random jitter between requests."""

    def __init__(self, min_interval_s: float, jitter_s: tuple[float, float]):
        self.min_interval_s = min_interval_s
        self.jitter_s = tuple(jitter_s)
        self._last = 0.0

    def wait(self):
        target = self._last + self.min_interval_s + random.uniform(*self.jitter_s)
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


def cache_get(path: Path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def cache_put(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f)
    tmp.replace(path)  # atomic: an interrupted write never leaves a broken cache file


def with_retries(fn, *, max_retries: int, backoff_base_s: float, what: str = ""):
    """Run fn() with exponential backoff on transient failures.

    NotFoundError propagates immediately (404 is a fact, not a hiccup).
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except NotFoundError:
            raise
        except Exception as exc:  # timeouts, connection resets, 5xx, JSON decode
            last_exc = exc
            # An unparseable body twice in a row is a permanently broken
            # upstream payload, not a transient hiccup - fail fast so the
            # caller can mark the work unit and move on.
            attempts_allowed = 1 if isinstance(exc, JSONDecodeError) else max_retries
            if attempt >= attempts_allowed:
                break
            delay = backoff_base_s * (2 ** attempt) + random.uniform(0, 1)
            print(f"  retry {attempt + 1}/{attempts_allowed} after {delay:.1f}s"
                  f" ({what or 'request'}: {type(exc).__name__}: {exc})")
            time.sleep(delay)
    raise last_exc


def get_json(url: str, *, headers: dict, timeout: float, session: requests.Session | None = None):
    sess = session or requests
    resp = sess.get(url, headers=headers, timeout=timeout)
    if resp.status_code in (403, 404):
        # The NHL API answers 404 for games that do not exist (yet); 403 is kept
        # as absent too, as in the NBA client.
        raise NotFoundError(f"{resp.status_code} {url}")
    resp.raise_for_status()
    return resp.json()

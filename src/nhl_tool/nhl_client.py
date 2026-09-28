"""Client for the public NHL APIs (api-web.nhle.com, api.nhle.com/stats).

No key, no account. One request at a time with a throttle, retries with
backoff, and a JSON disk cache: a successful download of something that can
no longer change (a finished game's box score) never happens twice.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

import requests

from .http_client import Throttle, cache_get, cache_put, get_json, with_retries

HEADERS = {"User-Agent": "nhl-tool research (personal, non-commercial)"}


class NhlClient:
    def __init__(self, cfg: dict, cache_dir: Path):
        api = cfg["nhl_api"]
        self.web_base = api["web_base"].rstrip("/")
        self.stats_base = api["stats_base"].rstrip("/")
        self.timeout = api["timeout_s"]
        self.max_retries = api["max_retries"]
        self.backoff = api["backoff_base_s"]
        self.throttle = Throttle(api["min_interval_s"], api["jitter_s"])
        self.cache_dir = Path(cache_dir) / "nhl"
        self.session = requests.Session()
        self.requests_made = 0

    def _fetch(self, url: str):
        def call():
            self.throttle.wait()
            self.requests_made += 1
            return get_json(url, headers=HEADERS, timeout=self.timeout,
                            session=self.session)
        return with_retries(call, max_retries=self.max_retries,
                            backoff_base_s=self.backoff, what=url)

    def _cached(self, url: str, cache_key: str | None, keep):
        """Serve from cache when present; otherwise fetch and store the
        payload only if keep(payload) says it can no longer change."""
        path = self.cache_dir / f"{cache_key}.json" if cache_key else None
        if path is not None:
            hit = cache_get(path)
            if hit is not None:
                return hit
        payload = self._fetch(url)
        if path is not None and keep(payload):
            cache_put(path, payload)
        return payload

    def web(self, path: str, cache_key: str | None = None, keep=lambda p: True):
        return self._cached(f"{self.web_base}/{path.lstrip('/')}", cache_key, keep)

    def stats(self, report: str, params: dict, cache_key: str | None = None,
              keep=lambda p: True):
        url = f"{self.stats_base}/{report.lstrip('/')}?{urlencode(params)}"
        return self._cached(url, cache_key, keep)


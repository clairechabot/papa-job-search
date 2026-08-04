"""Hardened HTTP fetch, adapted from the Curated Canopy newsletter engine
(itself ported from the Ellipsis Athena scrapers).

Browser User-Agent + retries with backoff + timeout + raise_for_status, with a
read-through proxy fallback for sites that 403 datacenter IPs (job boards are
notorious for this from GitHub Actions runners)."""
from __future__ import annotations

import time

import requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9,fr-CA;q=0.8",
}

# Public read-through relays, tried in order when a direct fetch is bot-blocked.
_PROXY_RELAYS = [
    "https://api.codetabs.com/v1/proxy?quest={url}",
    "https://api.allorigins.win/raw?url={url}",
]

_BLOCKED_STATUSES = {403, 429, 503}


def fetch(url: str, *, headers: dict | None = None, timeout: int = 45,
          retries: int = 3, retry_delay: int = 4, **kwargs) -> requests.Response:
    """GET `url` with a real browser UA and retry/backoff."""
    hdrs = {**BROWSER_HEADERS, **(headers or {})}
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=hdrs, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_err = e
            if attempt < retries:
                time.sleep(retry_delay)
    raise last_err


def fetch_with_proxy_fallback(url: str, **kwargs) -> requests.Response:
    """Fetch directly first; on a bot-wall status, retry through public relays.

    Non-blocked sites always take the fast direct path."""
    from urllib.parse import quote

    try:
        return fetch(url, retries=2, **kwargs)
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status not in _BLOCKED_STATUSES:
            raise
    last_err = None
    for relay in _PROXY_RELAYS:
        try:
            return fetch(relay.format(url=quote(url, safe="")), retries=1, **kwargs)
        except requests.RequestException as e:
            last_err = e
    raise last_err

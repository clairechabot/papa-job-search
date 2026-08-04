"""CareerBeacon (careerbeacon.com) — the Atlantic Canada job board.

Bot-walled (403) from datacenter IPs; goes through the proxy-relay fallback.
If the relays are down too, the source degrades gracefully (fetch.py catches).
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch_with_proxy_fallback  # noqa: E402

BASE = "https://www.careerbeacon.com"

SEARCHES = [
    f"{BASE}/en/search?keywords=chief+financial+officer&prov=NS",
    f"{BASE}/en/search?keywords=director+finance&prov=NS",
    f"{BASE}/en/search?keywords=controller&prov=NS",
]


def fetch_jobs() -> list[dict]:
    jobs, seen = [], set()
    for url in SEARCHES:
        resp = fetch_with_proxy_fallback(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Posting links carry /job-posting/ or /en/job/ path segments.
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/job" not in href or href in seen:
                continue
            title = " ".join(a.stripped_strings)
            if not title or len(title) < 4:
                continue
            seen.add(href)
            jobs.append({
                "source": "CareerBeacon",
                "title": title,
                "company": "",
                "location": "Nova Scotia",
                "url": urljoin(BASE, href),
                "date_posted": "",
                "salary": "",
                "snippet": "",
            })
    return jobs

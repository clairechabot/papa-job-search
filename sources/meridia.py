"""Meridia Recruitment (meridiarecruitment.ca) — KBRS's recruitment arm,
Halifax-based, the main Atlantic-Canada professional recruiter. Senior finance
roles in NS very often go through them rather than public boards.

Listing page anchors look like:
    <a href="/Career/<id>" hreflang="en">Manager, Financial Reporting</a>
"""
from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch_with_proxy_fallback  # noqa: E402

BASE = "https://meridiarecruitment.ca"
LISTING = f"{BASE}/career-opportunities/careers"


def fetch_jobs() -> list[dict]:
    resp = fetch_with_proxy_fallback(LISTING)
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.select('a[href^="/Career/"]'):
        title = " ".join(a.stripped_strings)
        href = a.get("href", "")
        if not title or href in seen:
            continue
        seen.add(href)
        # Location/company usually sit in sibling elements; keep it simple and
        # let the curation step read the title. Meridia is Atlantic-Canada
        # focused, so tag the region.
        jobs.append({
            "source": "Meridia Recruitment (KBRS)",
            "title": title,
            "company": "via Meridia Recruitment",
            "location": "Atlantic Canada",
            "url": f"{BASE}{href}",
            "date_posted": "",
            "salary": "",
            "snippet": "",
        })
    return jobs

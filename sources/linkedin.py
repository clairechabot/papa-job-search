"""LinkedIn Jobs via the guest (unauthenticated) search endpoint.

Verified working from datacenter IPs 2026-08 (the endpoint powers LinkedIn's
logged-out job search). Occasional 429s go through the proxy fallback. The
richer, authenticated layer (hiring-team contacts, better relevance) lives in
linkedin_authenticated.py and runs on the self-hosted VM runner - this guest
layer always runs so LinkedIn coverage never depends on the VM being up.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch_with_proxy_fallback  # noqa: E402

GUEST_API = ("https://www.linkedin.com/jobs-guest/jobs/api/"
             "seeMoreJobPostings/search")

# (keywords, location, f_WT) - f_WT=2 filters to Remote. Past week only.
SEARCHES = [
    ("chief financial officer OR \"VP finance\"", "Nova Scotia, Canada", None),
    ("\"head of finance\" OR \"director of finance\"", "Nova Scotia, Canada", None),
    ("chief financial officer", "New Brunswick, Canada", None),
    ("chief financial officer OR \"VP finance\"", "Quebec, Canada", None),
    ("chief financial officer OR \"VP finance\"", "Canada", "2"),
    ("chief financial officer OR \"VP finance\"", "United States", "2"),
    ("\"portfolio company\" CFO private equity", "United States", None),
    ("chief financial officer manufacturing", "Boston, Massachusetts", None),
    ("\"interim CFO\" OR \"fractional CFO\"", "Canada", None),
]


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def fetch_jobs() -> list[dict]:
    jobs, seen = [], set()
    for keywords, location, f_wt in SEARCHES:
        params = {"keywords": keywords, "location": location,
                  "f_TPR": "r604800", "start": 0}
        if f_wt:
            params["f_WT"] = f_wt
        resp = fetch_with_proxy_fallback(f"{GUEST_API}?{urlencode(params)}")
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("div.base-search-card, li"):
            title = card.select_one(".base-search-card__title")
            link = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            if not title or not link:
                continue
            url = link.get("href", "").split("?")[0]
            if not url or url in seen:
                continue
            seen.add(url)
            company = card.select_one(".base-search-card__subtitle")
            loc = card.select_one(".job-search-card__location")
            salary = card.select_one(".job-search-card__salary-info")
            jobs.append({
                "source": "LinkedIn",
                "title": _clean(title.get_text()),
                "company": _clean(company.get_text()) if company else "",
                "location": _clean(loc.get_text()) if loc else location,
                "url": url,
                "date_posted": "",
                "salary": _clean(salary.get_text()) if salary else "",
                "snippet": "",
            })
    return jobs

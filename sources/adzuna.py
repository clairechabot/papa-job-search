"""Adzuna job-search API (free tier) — aggregates many boards incl. Indeed.

Optional: requires ADZUNA_APP_ID + ADZUNA_APP_KEY (free at
developer.adzuna.com). Without keys the source is skipped cleanly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch  # noqa: E402

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# (country, query) - dual citizen, so US postings are first-class.
QUERIES = [
    ("ca", {"what_or": "CFO \"chief financial officer\" \"VP finance\" \"head of finance\" \"director of finance\"",
            "where": "Nova Scotia", "distance": 250}),
    ("ca", {"what_or": "CFO \"chief financial officer\" \"VP finance\"",
            "where": "New Brunswick", "distance": 200}),
    ("ca", {"what_or": "CFO \"chief financial officer\"", "what_and": "remote"}),
    ("us", {"what_or": "CFO \"chief financial officer\"", "what_and": "remote"}),
    ("us", {"what_or": "CFO \"chief financial officer\" \"VP finance\"",
            "where": "Boston", "distance": 150}),
    ("us", {"what_or": "\"portfolio company\" CFO \"private equity\""}),
]


class MissingKeys(RuntimeError):
    pass


def fetch_jobs() -> list[dict]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise MissingKeys("ADZUNA_APP_ID / ADZUNA_APP_KEY not set (optional source)")
    jobs = []
    for country, query in QUERIES:
        params = {"app_id": app_id, "app_key": app_key,
                  "results_per_page": 30, "max_days_old": 14,
                  "sort_by": "date", **query}
        data = fetch(API.format(country=country), params=params).json()
        for item in data.get("results", []):
            jobs.append({
                "source": "Adzuna",
                "title": item.get("title", ""),
                "company": (item.get("company") or {}).get("display_name", ""),
                "location": (item.get("location") or {}).get("display_name", ""),
                "url": item.get("redirect_url", ""),
                "date_posted": (item.get("created") or "")[:10],
                "salary": (f"${item['salary_min']:,.0f}-${item['salary_max']:,.0f} "
                           f"{'CAD' if country == 'ca' else 'USD'}"
                           if item.get("salary_min") and item.get("salary_max") else ""),
                "snippet": (item.get("description") or "")[:300],
            })
    return jobs

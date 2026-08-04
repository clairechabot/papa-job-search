"""Canada Job Bank (jobbank.gc.ca) — official federal job board.

The RSS feed endpoint ignores search terms (verified 2026-08), so we scrape
the HTML search results, which honour searchstring + locationstring. Result
markup: <article> -> a.resultJobItem (href), .noctitle (title), li.business
(employer), li.location, li.salary, li.date.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch  # noqa: E402

BASE = "https://www.jobbank.gc.ca"

# One search per (term, location). Nova Scotia primary; national remote-friendly
# senior-finance sweep second.
SEARCHES = [
    ("cfo", "Nova Scotia"),
    ("chief financial officer", "Nova Scotia"),
    ("director of finance", "Nova Scotia"),
    ("vice president finance", "Nova Scotia"),
    ("controller", "Nova Scotia"),
    ("chief financial officer", ""),  # national — remote roles get gated later
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for article in soup.select("article"):
        link = article.select_one("a.resultJobItem")
        title = article.select_one(".noctitle")
        if not link or not title:
            continue
        # Title node includes marker sub-spans; take the first text chunk.
        title_text = _clean(next(iter(title.stripped_strings), ""))
        url = link.get("href", "").split(";jsessionid")[0]
        jobs.append({
            "source": "Job Bank (Canada)",
            "title": title_text,
            "company": _clean(article.select_one("li.business").get_text()
                              if article.select_one("li.business") else ""),
            "location": _clean(article.select_one("li.location").get_text()
                               if article.select_one("li.location") else "")
                        .removeprefix("Location"),
            "url": f"{BASE}{url}" if url.startswith("/") else url,
            "date_posted": _clean(article.select_one("li.date").get_text()
                                  if article.select_one("li.date") else ""),
            "salary": _clean(article.select_one("li.salary").get_text()
                             if article.select_one("li.salary") else "")
                      .removeprefix("Salary").strip(),
            "snippet": "",
        })
    return jobs


def fetch_jobs() -> list[dict]:
    jobs = []
    for term, location in SEARCHES:
        params = {"searchstring": term, "sort": "D"}
        if location:
            params["locationstring"] = location
        resp = fetch(f"{BASE}/jobsearch/jobsearch", params=params)
        jobs.extend(_parse_results(resp.text))
    return jobs

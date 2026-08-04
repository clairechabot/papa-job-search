"""Nova Scotia / Atlantic headhunters - Marcel's own shortlist plus Meridia
(already a dedicated source). Senior finance seats in NS often go through
these firms before (or instead of) public boards.

Listing pages verified reachable 2026-08. Each firm gets a generic
best-effort anchor scrape with a finance-title filter; per-firm failures
degrade gracefully via fetch.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch_with_proxy_fallback  # noqa: E402

FIRMS = [
    ("Venor", "https://venor.ca/opportunities"),
    ("Summit Search Group", "https://www.summitsearchgroup.com/opportunities/"),
    ("Macdonald Search Group", "https://macdonaldsearchgroup.com/job-listings"),
    ("Lock Search Group", "https://locksearchgroup.com/opportunities/"),
    ("Accountant Staffing", "https://www.accountantstaffing.com/job-opportunities"),
]

FINANCE_TITLE = re.compile(
    r"\b(cfo|chief financial|finance|financial|controller|contr[oô]leur"
    r"|treasurer|accounting|fp&a|vp finance|directeur financier|cao\b"
    r"|chief administrative)\b", re.I)

# Anchors that are navigation, not postings.
NAV_NOISE = re.compile(r"(submit|alert|sign.?up|resume|about|contact|home"
                       r"|privacy|linkedin|facebook|instagram)", re.I)


def _scrape_firm(name: str, listing_url: str) -> list[dict]:
    resp = fetch_with_proxy_fallback(listing_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.stripped_strings)
        href = a["href"]
        if (not text or len(text) < 6 or len(text) > 120
                or NAV_NOISE.search(text) or NAV_NOISE.search(href)):
            continue
        if not FINANCE_TITLE.search(text):
            continue
        url = urljoin(listing_url, href)
        if url in seen or url.rstrip("/") == listing_url.rstrip("/"):
            continue
        seen.add(url)
        jobs.append({
            "source": f"{name} (recruiter)",
            "title": text,
            "company": f"via {name}",
            "location": "Atlantic Canada",
            "url": url,
            "date_posted": "",
            "salary": "",
            "snippet": "",
        })
    return jobs


def fetch_jobs() -> list[dict]:
    """One combined source; individual firm failures are tolerated here so a
    single 404 doesn't hide the other four firms."""
    jobs, failures = [], []
    for name, url in FIRMS:
        try:
            jobs.extend(_scrape_firm(name, url))
        except Exception as e:  # noqa: BLE001 - boundary: external sites
            failures.append(f"{name}: {type(e).__name__}")
    if failures and not jobs:
        raise RuntimeError("; ".join(failures))
    if failures:
        print(f"[recruiters] partial: {'; '.join(failures)}", flush=True)
    return jobs

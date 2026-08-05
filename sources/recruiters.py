"""Recruiter / executive-search listings - Marcel's Atlantic shortlist plus
the national and US firms Claire added 2026-08 (Page Executive, TrueNorth,
CFO Search, Robert Half Canada). Meridia stays a dedicated source.

Senior finance seats often go through these firms before (or instead of)
public boards. Each firm gets a best-effort anchor scrape with a
finance-title filter; per-firm failures degrade gracefully via fetch.py.

Location handling: the Atlantic firms tag "Atlantic Canada" (tier 1 via the
NS regex). National/US firms either parse a real location (Robert Half's
job URLs embed city-prov) or carry a firm-level default plus a `tier_hint`
that fetch.tag_tier uses only when the location text resolves to nothing -
TrueNorth's PE-CFO mandates rarely state geography in the title, but they
are US searches, so they surface as tier 4 rather than vanishing.

Not scrapeable (no public client listings; they live in the web edition's
Recruiter watch panel as outreach targets instead): Falcon (falcon-pe.com),
Vision Search Partners, Bohan & Bradstreet (their jobs page 404s; openings
are posted on their LinkedIn).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch_with_proxy_fallback  # noqa: E402

# name, listing url, default location, tier_hint (0 = no hint: out-of-area
# unless the title itself carries a tierable region)
FIRMS = [
    ("Venor", "https://venor.ca/opportunities", "Atlantic Canada", 0),
    ("Summit Search Group", "https://www.summitsearchgroup.com/opportunities/",
     "Atlantic Canada", 0),
    ("Macdonald Search Group", "https://macdonaldsearchgroup.com/job-listings",
     "Atlantic Canada", 0),
    ("Lock Search Group", "https://locksearchgroup.com/opportunities/",
     "Atlantic Canada", 0),
    ("Accountant Staffing", "https://www.accountantstaffing.com/job-opportunities",
     "Atlantic Canada", 0),
    # PE-focused US boutique; mandates rarely name a state in the title.
    ("TrueNorth Executive Search", "https://careers.truenorthsearch.com",
     "United States", 4),
    # US CFO boutique; /cfo-jobs/ is partly marketing, noise filter matters.
    ("CFO Search Inc", "https://www.cfo-search.com/cfo-jobs/",
     "United States", 4),
    # Global CFO category page; only titles that name a tierable region
    # survive the gate (no hint - most listings are outside his map).
    ("Page Executive", "https://www.pageexecutive.com/jobs/cfo-financial-management",
     "", 0),
]

FINANCE_TITLE = re.compile(
    r"\b(cfo|chief financial|finance|financial|controller|contr[oô]leur"
    r"|treasurer|treasury|accounting|fp&a|vp finance|directeur financier"
    r"|cao\b|chief administrative)\b", re.I)

# Anchors that are navigation/marketing, not postings. Careful with broad
# words: "services" here once killed TrueNorth's "Healthcare Services" CFO
# mandates - URL-shaped patterns only for anything that can appear in a
# legitimate title. "-cfo-search/" hits CFO Search Inc's city marketing
# pages (/los-angeles-cfo-search/) but not its domain or /cfo-jobs/ links.
NAV_NOISE = re.compile(
    r"(submit|alert|sign.?up|resume|about|contact|home|privacy|linkedin"
    r"|facebook|instagram|blog|salary|job.?description|when.to.hire"
    r"|headhunters|executive-search|recruiters|interim-cfo-services"
    r"|-cfo-search/|/advice/|recruitment-expertise)", re.I)


def _scrape_firm(name: str, listing_url: str, location: str,
                 tier_hint: int) -> list[dict]:
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
        job = {
            "source": f"{name} (recruiter)",
            "title": text,
            "company": f"via {name}",
            "location": location,
            "url": url,
            "date_posted": "",
            "salary": "",
            "snippet": "",
        }
        if tier_hint:
            job["tier_hint"] = tier_hint
        jobs.append(job)
    return jobs


# Robert Half Canada embeds "city-prov" in every job URL:
#   /ca/en/job/mississauga-on/sr-financial-analyst/05010-...
ROBERT_HALF_URL = "https://www.roberthalf.com/ca/en/jobs"
RH_JOB_HREF = re.compile(r"/ca/en/job/([a-z-]+)-([a-z]{2})/", re.I)


def _scrape_robert_half() -> list[dict]:
    resp = fetch_with_proxy_fallback(ROBERT_HALF_URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = RH_JOB_HREF.search(a["href"])
        text = " ".join(a.stripped_strings)
        if not m or not text or len(text) < 6 or len(text) > 120:
            continue
        if not FINANCE_TITLE.search(text):
            continue
        url = urljoin(ROBERT_HALF_URL, a["href"])
        if url in seen:
            continue
        seen.add(url)
        city = m.group(1).replace("-", " ").title()
        prov = m.group(2).upper()
        jobs.append({
            "source": "Robert Half (recruiter)",
            "title": text,
            "company": "via Robert Half",
            "location": f"{city}, {prov}",
            "url": url,
            "date_posted": "",
            "salary": "",
            "snippet": "",
        })
    return jobs


def fetch_jobs() -> list[dict]:
    """One combined source; individual firm failures are tolerated here so a
    single 404 doesn't hide the other firms."""
    jobs, failures = [], []
    for name, url, location, hint in FIRMS:
        try:
            jobs.extend(_scrape_firm(name, url, location, hint))
        except Exception as e:  # noqa: BLE001 - boundary: external sites
            failures.append(f"{name}: {type(e).__name__}")
    try:
        jobs.extend(_scrape_robert_half())
    except Exception as e:  # noqa: BLE001 - boundary: external sites
        failures.append(f"Robert Half: {type(e).__name__}")
    if failures and not jobs:
        raise RuntimeError("; ".join(failures))
    if failures:
        print(f"[recruiters] partial: {'; '.join(failures)}", flush=True)
    return jobs

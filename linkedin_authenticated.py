"""Authenticated LinkedIn scan - runs ONLY on the self-hosted VM runner
(see VM-SETUP.md). Uses the Playwright session captured by linkedin_auth.py
at ~/.config/linkedin-auth.json.

Two jobs:
  1. Logged-in LinkedIn Jobs searches per location tier (richer results and
     posted salary vs the guest endpoint).
  2. For each result that passes the title/tier gate, open the posting and
     extract the "Meet the hiring team" contacts (name, headline, profile
     URL) so the newsletter can say who to reach out to.

Results merge into pending_jobs.json (the evening edition consumes it).
Missing/expired auth exits 0 with a warning - the guest layer still covers
LinkedIn, so this degrades, never breaks, the newsletter.

Usage:  python linkedin_authenticated.py [--max-detail 12]
"""
from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
import time
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
AUTH_FILE = Path.home() / ".config" / "linkedin-auth.json"
PENDING_FILE = HERE / "pending_jobs.json"
HALIFAX = ZoneInfo("America/Halifax")

sys.path.insert(0, str(HERE))
from curate import gate  # noqa: E402 - reuse the same title/tier gate
from fetch import tag_tier  # noqa: E402
from history import is_seen, job_fingerprint, load_history  # noqa: E402

# (keywords, location, remote-only)
SEARCHES = [
    ("chief financial officer OR \"VP finance\" OR \"head of finance\"",
     "Nova Scotia, Canada", False),
    ("chief financial officer OR \"VP finance\"", "New Brunswick, Canada", False),
    ("chief financial officer OR \"directeur financier\"", "Quebec, Canada", False),
    ("chief financial officer OR \"VP finance\"", "Canada", True),
    ("chief financial officer OR \"VP finance\"", "United States", True),
    ("CFO private equity portfolio", "United States", True),
    ("chief financial officer", "Boston, Massachusetts, United States", False),
]


def _pause() -> None:
    time.sleep(random.uniform(2.5, 6.0))  # human-ish pacing


# LinkedIn's job cards have gone through several DOM generations; match any.
CARD_SELECTOR = ("div.job-card-container, li[data-occludable-job-id], "
                 "li.jobs-search-results__list-item")
LINK_SELECTOR = ("a.job-card-container__link, a.job-card-list__title--link, "
                 "a[href*='/jobs/view/']")


def _goto(page, url: str, what: str) -> bool:
    """LinkedIn pages stream requests forever, so the 'load' event routinely
    never fires - wait for DOM only, and never let one slow page kill the
    whole scan."""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        return True
    except Exception as e:  # noqa: BLE001 - boundary: flaky remote site
        print(f"[linkedin-auth] goto failed ({what}): {type(e).__name__}",
              flush=True)
        return False


def scrape(max_detail: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    jobs: dict[str, dict] = {}
    with sync_playwright() as p:
        # dev-shm is tiny on small VMs; without this flag Chromium crashes
        # or crawls on a 1GB droplet.
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu"])
        context = browser.new_context(storage_state=str(AUTH_FILE))
        # Skip images/media/fonts: halves memory and load time, and the
        # scraper only reads text anyway.
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font")
            else route.continue_())
        page = context.new_page()

        # Session sanity check.
        if not _goto(page, "https://www.linkedin.com/feed/", "feed"):
            print("[linkedin-auth] could not reach LinkedIn - skipping run",
                  file=sys.stderr)
            return []
        _pause()
        if any(marker in page.url for marker in ("/login", "authwall",
                                                 "checkpoint")):
            print("[linkedin-auth] session EXPIRED - re-run linkedin_auth.py "
                  "locally and re-upload linkedin-auth.json", file=sys.stderr)
            return []

        for keywords, location, remote in SEARCHES:
            url = (f"https://www.linkedin.com/jobs/search/?keywords="
                   f"{quote(keywords)}&location={quote(location)}&f_TPR=r604800"
                   + ("&f_WT=2" if remote else ""))
            if not _goto(page, url, location):
                continue
            try:
                page.wait_for_selector(CARD_SELECTOR, timeout=20000)
            except Exception:  # noqa: BLE001 - empty result page is valid
                print(f"[linkedin-auth] {location}: no result cards appeared "
                      f"(url now: {page.url[:80]})", flush=True)
            _pause()
            cards = page.locator(CARD_SELECTOR).all()[:25]
            for card in cards:
                try:
                    link = card.locator(LINK_SELECTOR).first
                    href = (link.get_attribute("href") or "").split("?")[0]
                    if not href or href in jobs:
                        continue
                    title = (link.inner_text() or "").strip().split("\n")[0]
                    company, loc = "", ""
                    try:
                        company = card.locator(
                            ".artdeco-entity-lockup__subtitle, "
                            ".job-card-container__primary-description"
                        ).first.inner_text().strip()
                        loc = card.locator(
                            ".job-card-container__metadata-wrapper, "
                            ".job-card-container__metadata-item"
                        ).first.inner_text().strip()
                    except Exception:  # noqa: BLE001 - optional fields
                        pass
                    jobs[href] = {
                        "source": "LinkedIn (authenticated)",
                        "title": title, "company": company, "location": loc,
                        "url": f"https://www.linkedin.com{href}"
                               if href.startswith("/") else href,
                        "date_posted": "", "salary": "", "snippet": "",
                    }
                except Exception:  # noqa: BLE001 - boundary: DOM drift
                    continue
            print(f"[linkedin-auth] {location} ({'remote' if remote else 'all'}):"
                  f" {len(cards)} cards", flush=True)

        # Detail pass: hiring team + description snippet for gate-passing jobs.
        detailed = 0
        for job in jobs.values():
            tag_tier(job)
            if not gate(dict(job)) or detailed >= max_detail:
                continue
            detailed += 1
            try:
                if not _goto(page, job["url"], "detail"):
                    continue
                _pause()
                desc = page.locator("#job-details, .jobs-description__content")
                if desc.count():
                    job["snippet"] = " ".join(
                        desc.first.inner_text().split())[:600]
                contacts = []
                for person in page.locator(
                        ".hirer-card__hirer-information, "
                        ".jobs-poster__name-container").all()[:3]:
                    try:
                        a = person.locator("a").first
                        contacts.append({
                            "name": person.inner_text().strip().split("\n")[0],
                            "title": (person.inner_text().strip().split("\n")[1]
                                      if "\n" in person.inner_text().strip() else ""),
                            "url": (a.get_attribute("href") or "").split("?")[0],
                        })
                    except Exception:  # noqa: BLE001
                        continue
                if contacts:
                    job["contacts"] = contacts
            except Exception as e:  # noqa: BLE001 - boundary: DOM drift
                print(f"[linkedin-auth] detail failed for {job['url']}: "
                      f"{type(e).__name__}", flush=True)
        browser.close()
    return list(jobs.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-detail", type=int, default=12,
                        help="max postings to open for hiring-team extraction")
    args = parser.parse_args()

    if not AUTH_FILE.exists():
        print(f"[linkedin-auth] no session at {AUTH_FILE} - skipping "
              "(run linkedin_auth.py locally, scp the file to the VM)")
        return

    found = scrape(args.max_detail)
    if not found:
        return

    history = load_history()
    pending = {"scanned_at": "", "jobs": [], "source_status": {}}
    if PENDING_FILE.exists():
        pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    pool = {job_fingerprint(j): j for j in pending.get("jobs", [])}
    fresh = 0
    for job in found:
        fp = job_fingerprint(job)
        if is_seen(job, history):
            continue
        if fp in pool:
            # Authenticated data is richer - upgrade the pooled record.
            pool[fp].update({k: v for k, v in job.items() if v})
        else:
            pool[fp] = job
            fresh += 1
    pending["jobs"] = list(pool.values())
    pending["scanned_at"] = datetime.datetime.now(HALIFAX).isoformat()
    pending.setdefault("source_status", {})["LinkedIn (authenticated)"] = (
        f"ok ({len(found)} found, {fresh} new)")
    PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"[linkedin-auth] merged {fresh} new job(s) into pending pool "
          f"({len(pool)} total)")


if __name__ == "__main__":
    main()

"""Orchestrator: run every job source + news feeds, dedup against history,
tag location tiers, and manage the pending pool for the once-daily edition.

Two modes (once-daily email, two scans):
  python fetch.py --scan-only   # morning: fetch + merge into pending_jobs.json,
                                # no email, no Claude spend (committed by CI)
  python fetch.py               # evening: fetch + merge pending pool, write
                                # fetched_data.json for curate.py

Per-source failures degrade gracefully (the edition footer reports them).

Usage:  python fetch.py [--scan-only] [--include-seen]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from history import is_seen, job_fingerprint, load_history, normalize_url
from sources import adzuna, ai_news, careerbeacon, job_bank, linkedin, meridia, recruiters

HERE = Path(__file__).parent
OUT_FILE = HERE / "fetched_data.json"
PENDING_FILE = HERE / "pending_jobs.json"
HALIFAX = ZoneInfo("America/Halifax")

JOB_SOURCES = [
    ("Job Bank (Canada)", job_bank.fetch_jobs),
    ("LinkedIn", linkedin.fetch_jobs),
    ("Meridia Recruitment (KBRS)", meridia.fetch_jobs),
    ("NS recruiters", recruiters.fetch_jobs),
    ("CareerBeacon", careerbeacon.fetch_jobs),
    ("Adzuna", adzuna.fetch_jobs),
]

# ---------------------------------------------------------------------------
# Location tiers (see profile/candidate.md)
# ---------------------------------------------------------------------------
NS = re.compile(r"\b(NS|Nova Scotia|Halifax|Dartmouth|Bedford|Sydney|Truro"
                r"|Kentville|Wolfville|New Glasgow|Bridgewater|Antigonish"
                r"|Yarmouth|Amherst|Atlantic)\b", re.I)
EASTERN_CA = re.compile(r"\b(NB|New Brunswick|Moncton|Saint John|Fredericton"
                        r"|PE|PEI|Prince Edward|Charlottetown|NL|Newfoundland"
                        r"|St\.? John's|QC|Quebec|Québec|Montr[eé]al|Sherbrooke"
                        r"|Gatineau|Trois-Rivi[eè]res)\b", re.I)
REMOTE = re.compile(r"\b(remote|telework|work from home|anywhere)\b", re.I)
NE_US = re.compile(r"\b(MA|Massachusetts|Boston|ME|Maine|Portland|NH|New"
                   r" Hampshire|VT|Vermont|CT|Connecticut|RI|Rhode Island"
                   r"|NY|New York|Albany|Buffalo|New England)\b", re.I)


# Sources whose entire catchment is Atlantic Canada - their postings are
# tier 1 even when the location text is vague. The national/US recruiter
# firms added 2026-08 are NOT here: they tier by location, or by the
# firm-level tier_hint recruiters.py attaches when a mandate's geography
# isn't stated (e.g. TrueNorth's PE-CFO searches).
ATLANTIC_SOURCES = {
    "Meridia Recruitment (KBRS)", "CareerBeacon",
    "Venor (recruiter)", "Summit Search Group (recruiter)",
    "Macdonald Search Group (recruiter)", "Lock Search Group (recruiter)",
    "Accountant Staffing (recruiter)",
}


def tag_tier(job: dict) -> None:
    """Annotate job['tier'] 1-4, or 0 (out of area - the gate rejects)."""
    text = f"{job.get('location', '')} {job.get('title', '')}"
    if job.get("source") in ATLANTIC_SOURCES:
        job["tier"] = 1  # Atlantic-scoped sources
    elif NS.search(text):
        job["tier"] = 1
    elif EASTERN_CA.search(text):
        job["tier"] = 2
    elif REMOTE.search(text):
        job["tier"] = 3
    elif NE_US.search(text):
        job["tier"] = 4
    else:
        job["tier"] = job.get("tier_hint", 0)


def _load_pending() -> list[dict]:
    if PENDING_FILE.exists():
        return json.loads(PENDING_FILE.read_text(encoding="utf-8")).get("jobs", [])
    return []


def download_tracker(now: datetime.datetime) -> None:
    """Application-tracker read-back: pull the sheet's published CSV into
    tracker_data.json for curate/webpage. `or`-guard (not a get default) -
    the workflow passes the repo variable, which is EMPTY when unset."""
    csv_url = os.environ.get("SHEET_CSV_URL") or ""
    if not csv_url:
        return
    import csv as csvmod
    import io

    try:
        resp = requests.get(csv_url, timeout=30)
        resp.raise_for_status()
        rows = []
        for r in csvmod.DictReader(io.StringIO(resp.text)):
            if not (r.get("Title") or r.get("Company")):
                continue
            rows.append({
                "title": r.get("Title", ""), "company": r.get("Company", ""),
                "url": r.get("Job URL", ""),
                "normalized_url": normalize_url(r.get("Job URL", "")),
                "fingerprint": job_fingerprint(
                    {"company": r.get("Company", ""),
                     "title": r.get("Title", "")}),
                "status": r.get("Status", ""),
                "applied_on": r.get("Applied on", ""),
                "last_contact_on": r.get("Last contact on", ""),
                "meeting_on": r.get("Meeting on", ""),
                "contact_via": r.get("Contact via", ""),
            })
        (HERE / "tracker_data.json").write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[fetch] tracker: {len(rows)} tracked row(s)")
    except Exception as e:  # noqa: BLE001 - boundary: external fetch
        print(f"[fetch] tracker unavailable: {type(e).__name__}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-only", action="store_true",
                        help="merge results into pending_jobs.json and stop")
    parser.add_argument("--include-seen", action="store_true",
                        help="skip history dedup (testing)")
    args = parser.parse_args()

    history = load_history()
    now = datetime.datetime.now(HALIFAX)

    pending = _load_pending()
    pool: dict[str, dict] = {job_fingerprint(j): j for j in pending}
    source_status: dict[str, str] = {}
    if pending:
        source_status["Morning scan"] = f"carried {len(pending)} job(s) forward"

    for name, fetch_fn in JOB_SOURCES:
        try:
            raw = fetch_fn()
            fresh = 0
            for job in raw:
                fp = job_fingerprint(job)
                if fp in pool:
                    continue
                if not args.include_seen and is_seen(job, history):
                    continue
                tag_tier(job)
                pool[fp] = job
                fresh += 1
            source_status[name] = f"ok ({len(raw)} found, {fresh} new)"
        except adzuna.MissingKeys as e:
            source_status[name] = f"skipped: {e}"
        except Exception as e:  # noqa: BLE001 - boundary: external job boards
            source_status[name] = f"unavailable: {type(e).__name__}: {e}"
        print(f"[fetch] {name}: {source_status[name]}", flush=True)

    jobs = list(pool.values())

    if args.scan_only:
        PENDING_FILE.write_text(json.dumps({
            "scanned_at": now.isoformat(),
            "jobs": jobs,
            "source_status": source_status,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[fetch] scan-only: {len(jobs)} job(s) pending for the evening edition")
        return

    download_tracker(now)

    ai_articles, ai_status = ai_news.fetch_articles(ai_news.AI_FEEDS)
    ai_articles = [a for a in ai_articles
                   if args.include_seen or a["url"] not in history["ai_article_urls"]]
    ns_articles, ns_status = ai_news.fetch_articles(
        ai_news.NS_BUSINESS_FEEDS, limit_per_feed=15)
    for name, st in {**ai_status, **ns_status}.items():
        print(f"[fetch] feed {name}: {st}", flush=True)

    OUT_FILE.write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "jobs": jobs,
        "ai_articles": ai_articles,
        "ns_articles": ns_articles,
        "source_status": {**source_status, **ai_status, **ns_status},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    # Pool consumed: clear pending so tomorrow starts fresh.
    PENDING_FILE.write_text(json.dumps({
        "scanned_at": now.isoformat(), "jobs": [], "source_status": {}},
        indent=2), encoding="utf-8")
    print(f"[fetch] wrote {OUT_FILE.name}: {len(jobs)} jobs (incl. pending pool), "
          f"{len(ai_articles)} AI articles, {len(ns_articles)} NS articles")

    if not jobs and all("unavailable" in s for s in source_status.values()):
        print("[fetch] WARNING: every job source failed", file=sys.stderr)


if __name__ == "__main__":
    main()

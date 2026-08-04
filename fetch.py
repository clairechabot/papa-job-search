"""Orchestrator: run every job source + news feeds, dedup against history,
write fetched_data.json for curate.py.

Per-source failures degrade gracefully (the edition notes the outage) —
pattern from the Curated Canopy fetcher + Athena's scraper tiers.

Usage:  python fetch.py [--include-seen]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from history import is_seen, job_fingerprint, load_history
from sources import adzuna, ai_news, careerbeacon, job_bank, meridia

OUT_FILE = Path(__file__).parent / "fetched_data.json"
HALIFAX = ZoneInfo("America/Halifax")

JOB_SOURCES = [
    ("Job Bank (Canada)", job_bank.fetch_jobs),
    ("Meridia Recruitment (KBRS)", meridia.fetch_jobs),
    ("CareerBeacon", careerbeacon.fetch_jobs),
    ("Adzuna", adzuna.fetch_jobs),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-seen", action="store_true",
                        help="skip history dedup (testing)")
    args = parser.parse_args()

    history = load_history()
    now = datetime.datetime.now(HALIFAX)

    jobs, source_status = [], {}
    seen_this_run: set[str] = set()
    for name, fetch_fn in JOB_SOURCES:
        try:
            raw = fetch_fn()
            fresh = []
            for job in raw:
                fp = job_fingerprint(job)
                if fp in seen_this_run:
                    continue  # same job from a search overlap or another board
                if not args.include_seen and is_seen(job, history):
                    continue
                seen_this_run.add(fp)
                fresh.append(job)
            jobs.extend(fresh)
            source_status[name] = f"ok ({len(raw)} found, {len(fresh)} new)"
        except adzuna.MissingKeys as e:
            source_status[name] = f"skipped: {e}"
        except Exception as e:  # noqa: BLE001 — boundary: external job boards
            source_status[name] = f"unavailable: {type(e).__name__}: {e}"
        print(f"[fetch] {name}: {source_status[name]}", flush=True)

    ai_articles, ai_status = ai_news.fetch_articles(ai_news.AI_FEEDS)
    ai_articles = [a for a in ai_articles
                   if args.include_seen or a["url"] not in history["ai_article_urls"]]
    for name, st in ai_status.items():
        print(f"[fetch] AI feed {name}: {st}", flush=True)

    # NS business news only matters for the Sunday networking radar; cheap to
    # always fetch, curate.py decides whether to use it.
    ns_articles, ns_status = ai_news.fetch_articles(
        ai_news.NS_BUSINESS_FEEDS, limit_per_feed=15)
    for name, st in ns_status.items():
        print(f"[fetch] NS feed {name}: {st}", flush=True)

    OUT_FILE.write_text(json.dumps({
        "fetched_at": now.isoformat(),
        "jobs": jobs,
        "ai_articles": ai_articles,
        "ns_articles": ns_articles,
        "source_status": {**source_status, **ai_status, **ns_status},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[fetch] wrote {OUT_FILE.name}: {len(jobs)} new jobs, "
          f"{len(ai_articles)} AI articles, {len(ns_articles)} NS articles")

    if not jobs and all("unavailable" in s for s in source_status.values()):
        print("[fetch] WARNING: every job source failed", file=sys.stderr)


if __name__ == "__main__":
    main()

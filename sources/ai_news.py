"""AI-for-the-workplace reading: RSS feeds curated for a finance executive
staying current on AI, not for engineers. Verified reachable 2026-08.

Also carries the Nova Scotia business-news feeds that power the Sunday
"networking radar" section (leadership changes, expansions, funding).
"""
from __future__ import annotations

import sys
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from http_fetch import fetch  # noqa: E402

AI_FEEDS = [
    ("CFO Dive", "https://www.cfodive.com/feeds/news/"),
    ("MIT Sloan Management Review", "https://sloanreview.mit.edu/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Harvard Business Review", "https://feeds.hbr.org/harvardbusiness"),
]

NS_BUSINESS_FEEDS = [
    ("CBC Nova Scotia", "https://www.cbc.ca/webfeed/rss/rss-canada-novascotia"),
    ("Entrevestor (Atlantic startups)", "https://entrevestor.com/rss"),
    ("Halifax Examiner", "https://www.halifaxexaminer.ca/feed/"),
]


def _fetch_feed(name: str, url: str, limit: int) -> list[dict]:
    resp = fetch(url, timeout=30, retries=2)
    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries[:limit]:
        items.append({
            "feed": name,
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "summary": (entry.get("summary", "") or "")[:500],
            "published": entry.get("published", ""),
        })
    return items


def fetch_articles(feeds: list[tuple[str, str]] | None = None,
                   limit_per_feed: int = 10) -> tuple[list[dict], dict]:
    """Returns (articles, per-feed status dict)."""
    articles, status = [], {}
    for name, url in (feeds or AI_FEEDS):
        try:
            items = _fetch_feed(name, url, limit_per_feed)
            articles.extend(items)
            status[name] = f"ok ({len(items)})"
        except Exception as e:  # noqa: BLE001 — boundary: external feeds
            status[name] = f"unavailable: {type(e).__name__}"
    return articles, status

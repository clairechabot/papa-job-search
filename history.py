"""Seen-content memory so nothing repeats across editions.

Pattern from the Curated Canopy newsletter's history.json, with the
cross-board fuzzy job fingerprint adapted from Ellipsis Athena's
scoring/matcher.py normalization (legal-suffix stripping, lowercase collapse)
so the same role posted on two job boards only appears once."""
from __future__ import annotations

import json
import re
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "history.json"

LEGAL_SUFFIXES = (" inc", " inc.", " ltd", " ltd.", " limited", " llc",
                  " corp", " corp.", " co.", " co", " group", " canada")


def normalize(text: str) -> str:
    """Lowercase, strip legal suffixes and punctuation, collapse whitespace."""
    t = (text or "").lower().strip()
    for suffix in LEGAL_SUFFIXES:
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def job_fingerprint(job: dict) -> str:
    """Stable identity for a job across boards: company + title, normalized."""
    return f"{normalize(job.get('company', ''))}|{normalize(job.get('title', ''))}"


def load_history() -> dict:
    """Return {job_fingerprints: set, job_urls: set, ai_article_urls: set}.
    Missing buckets default to empty so an older/absent history.json loads."""
    data = {}
    if HISTORY_FILE.exists():
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8-sig"))
    return {
        "job_fingerprints": set(data.get("job_fingerprints", [])),
        "job_urls": set(data.get("job_urls", [])),
        "ai_article_urls": set(data.get("ai_article_urls", [])),
    }


def save_history(history: dict) -> None:
    """Persist, preserving any keys other code stores in the file."""
    existing = {}
    if HISTORY_FILE.exists():
        existing = json.loads(HISTORY_FILE.read_text(encoding="utf-8-sig"))
    for bucket in ("job_fingerprints", "job_urls", "ai_article_urls"):
        existing[bucket] = sorted(history[bucket])
    HISTORY_FILE.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def is_seen(job: dict, history: dict) -> bool:
    return (job.get("url") in history["job_urls"]
            or job_fingerprint(job) in history["job_fingerprints"])


def mark_seen(job: dict, history: dict) -> None:
    if job.get("url"):
        history["job_urls"].add(job["url"])
    history["job_fingerprints"].add(job_fingerprint(job))

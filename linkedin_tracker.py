"""Marcel's LinkedIn -> application tracker (VM-only, zero manual entry).

Runs in the LinkedIn Scan (VM) workflow with MARCEL'S session
(~/.config/linkedin-auth-marcel.json - see SHEET-SETUP.md Part 6; distinct
from the job-scan session). Two read-only passes:

  1. His "Applied" jobs list (my-items) -> action=applied events, catching
     Easy Apply applications that leave no email trail.
  2. His messaging conversation LIST (participant names + timestamps only;
     message bodies are never opened or stored) -> action=contact events
     for conversations matching a company already in the tracker sheet.

Events POST to the tracker sheet's Apps Script webhook. Anything missing
(session file, webhook config, selectors drifting) degrades to a warning
and exit 0 - this feed is an enricher, never a blocker.

Env:  SHEET_WEBHOOK_URL, SHEET_TOKEN, SHEET_CSV_URL (all from repo vars)
Usage:  python3 linkedin_tracker.py
"""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
AUTH_FILE = Path.home() / ".config" / "linkedin-auth-marcel.json"
APPLIED_URL = "https://www.linkedin.com/my-items/saved-jobs/?cardType=APPLIED"
MESSAGING_URL = "https://www.linkedin.com/messaging/"

sys.path.insert(0, str(HERE))
from history import normalize  # noqa: E402
from linkedin_common import goto, linkedin_page, pause  # noqa: E402

WEBHOOK = os.environ.get("SHEET_WEBHOOK_URL") or ""
TOKEN = os.environ.get("SHEET_TOKEN") or ""
CSV_URL = os.environ.get("SHEET_CSV_URL") or ""


def post_event(evt: dict) -> None:
    evt = {**evt, "token": TOKEN}
    try:
        requests.post(WEBHOOK, json=evt, timeout=20)
    except Exception as e:  # noqa: BLE001 - boundary: webhook is best-effort
        print(f"[li-tracker] webhook post failed: {type(e).__name__}",
              flush=True)


def tracked_companies() -> list[str]:
    """Company names already in the sheet (via its published CSV) - the
    messaging pass only matches against these, so noise stays contained."""
    if not CSV_URL:
        return []
    try:
        resp = requests.get(CSV_URL, timeout=30)
        resp.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(resp.text)))
        return sorted({r.get("Company", "").strip() for r in rows
                       if r.get("Company", "").strip()
                       and r.get("Status", "") not in ("Rejected", "Withdrawn")})
    except Exception as e:  # noqa: BLE001 - boundary: external fetch
        print(f"[li-tracker] tracker CSV unavailable: {type(e).__name__}",
              flush=True)
        return []


def scan_applied(page) -> int:
    if not goto(page, APPLIED_URL, "applied list", tag="li-tracker"):
        return 0
    pause()
    sent = 0
    for a in page.locator("a[href*='/jobs/view/']").all()[:40]:
        try:
            href = (a.get_attribute("href") or "").split("?")[0]
            text = " ".join(a.inner_text().split())
            if not href or not text or len(text) < 4:
                continue
            # Card text is usually "Title \n Company \n location"; the link
            # text alone is the title. Company comes from the card's parent
            # when exposed; tolerate absence (URL id is identity enough).
            company = ""
            try:
                parent_text = a.locator("xpath=ancestor::li[1]").inner_text()
                lines = [ln.strip() for ln in parent_text.split("\n")
                         if ln.strip()]
                if len(lines) > 1 and lines[0].startswith(text[:20]):
                    company = lines[1]
            except Exception:  # noqa: BLE001 - optional enrichment
                pass
            post_event({"action": "applied", "title": text[:120],
                        "company": company[:120],
                        "url": f"https://www.linkedin.com{href}"
                               if href.startswith("/") else href,
                        "via": "linkedin"})
            sent += 1
        except Exception:  # noqa: BLE001 - boundary: DOM drift
            continue
    print(f"[li-tracker] applied list: {sent} event(s) sent", flush=True)
    return sent


def scan_messages(page, companies: list[str]) -> int:
    if not companies:
        print("[li-tracker] no tracked companies yet - skipping messages",
              flush=True)
        return 0
    if not goto(page, MESSAGING_URL, "messaging", tag="li-tracker"):
        return 0
    pause()
    convos = page.locator(
        "li.msg-conversation-listitem, li[class*='conversation-listitem']"
    ).all()[:20]
    norm_companies = [(c, normalize(c)) for c in companies]
    sent = 0
    for convo in convos:
        try:
            text = normalize(" ".join(convo.inner_text().split()))
        except Exception:  # noqa: BLE001 - boundary: DOM drift
            continue
        for company, norm_c in norm_companies:
            if norm_c and len(norm_c) >= 4 and norm_c in text:
                post_event({"action": "contact", "company": company,
                            "via": "LinkedIn"})
                sent += 1
                break
    print(f"[li-tracker] messages: {len(convos)} conversations scanned, "
          f"{sent} matched a tracked company", flush=True)
    return sent


def main() -> None:
    if not AUTH_FILE.exists():
        print(f"[li-tracker] no session at {AUTH_FILE} - skipping "
              "(SHEET-SETUP.md Part 6 sets this up)")
        return
    if not WEBHOOK:
        print("[li-tracker] SHEET_WEBHOOK_URL not set - skipping")
        return
    companies = tracked_companies()
    with linkedin_page(AUTH_FILE, tag="li-tracker") as page:
        if page is None:
            return
        scan_applied(page)
        scan_messages(page, companies)


if __name__ == "__main__":
    main()

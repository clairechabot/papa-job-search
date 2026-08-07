"""Shared Playwright plumbing for the VM's authenticated LinkedIn scripts
(linkedin_authenticated.py = job scanning with Claire's session,
linkedin_tracker.py = Marcel's applied-list/messages feed).

Everything here encodes lessons from the first live runs on the droplet:
domcontentloaded-only waits (LinkedIn never fires 'load'), low-memory
Chromium flags, a fingerprint matching the Windows Chrome that captured the
session, and image/media/font blocking.
"""
from __future__ import annotations

import random
import sys
import time
from contextlib import contextmanager


def pause() -> None:
    time.sleep(random.uniform(2.5, 6.0))  # human-ish pacing


def goto(page, url: str, what: str, tag: str = "linkedin") -> bool:
    """LinkedIn pages stream requests forever, so the 'load' event routinely
    never fires - wait for DOM only, and never let one slow page kill the
    whole scan."""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        return True
    except Exception as e:  # noqa: BLE001 - boundary: flaky remote site
        print(f"[{tag}] goto failed ({what}): {type(e).__name__}", flush=True)
        return False


@contextmanager
def linkedin_page(auth_file, tag: str = "linkedin"):
    """Yield a logged-in LinkedIn page, or None when the session is dead
    (expired / checkpoint / unreachable) - callers just bail politely."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # dev-shm is tiny on small VMs; without this flag Chromium crashes
        # or crawls on a small droplet.
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-blink-features=AutomationControlled"])
        # Present the same fingerprint as the Windows Chrome that captured
        # the session - a mismatched UA from a datacenter IP is what trips
        # LinkedIn's "confirm it's you" wall.
        context = browser.new_context(
            storage_state=str(auth_file),
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/151.0.0.0 Safari/537.36"),
            viewport={"width": 1600, "height": 900},
            locale="en-US",
            timezone_id="America/Toronto")
        # Skip images/media/fonts: halves memory and load time, and the
        # scrapers only read text anyway.
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font")
            else route.continue_())
        page = context.new_page()
        try:
            if not goto(page, "https://www.linkedin.com/feed/", "feed", tag):
                print(f"[{tag}] could not reach LinkedIn - skipping run",
                      file=sys.stderr)
                yield None
                return
            pause()
            if any(m in page.url for m in ("/login", "authwall", "checkpoint")):
                kind = ("security checkpoint (approve the 'new sign-in' "
                        "prompt on the LinkedIn account, then re-run)"
                        if "checkpoint" in page.url else "EXPIRED")
                print(f"[{tag}] session {kind} - redirected to "
                      f"{page.url[:100]}", file=sys.stderr)
                print(f"[{tag}] if this persists: re-run linkedin_auth.py "
                      "locally and re-upload the session file",
                      file=sys.stderr)
                yield None
                return
            yield page
        finally:
            browser.close()

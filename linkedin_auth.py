"""One-time LinkedIn login capture - run this ON YOUR OWN COMPUTER (never on
the VM; LinkedIn wants to see a real browser on a residential IP for login).

    pip install playwright && playwright install chromium
    python linkedin_auth.py

A browser opens; log in to LinkedIn normally (2FA and all). When you land on
the feed, come back to the terminal and press Enter. The session is saved to
linkedin-auth.json - copy it to the VM:

    scp linkedin-auth.json <vm-user>@<vm-ip>:~/.config/linkedin-auth.json

Re-run this whenever the VM scraper reports the session expired (typically
every few months). Treat linkedin-auth.json like a password - never commit it.
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("linkedin-auth.json")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        input("Log in to LinkedIn in the browser window, wait for the feed "
              "to load, then press Enter here... ")
        context.storage_state(path=str(OUT))
        browser.close()
    print(f"Saved session to {OUT.resolve()}")
    print("Now: scp linkedin-auth.json <vm>:~/.config/linkedin-auth.json")


if __name__ == "__main__":
    main()

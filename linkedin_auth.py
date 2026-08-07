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

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="",
                        help="e.g. 'marcel' - writes linkedin-auth-marcel.json "
                             "(Marcel's session powers the application-tracker "
                             "feed; the default file is the job-scan session)")
    args = parser.parse_args()
    out = Path(f"linkedin-auth-{args.account}.json" if args.account
               else "linkedin-auth.json")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        input("Log in to LinkedIn in the browser window, wait for the feed "
              "to load, then press Enter here... ")
        context.storage_state(path=str(out))
        browser.close()
    print(f"Saved session to {out.resolve()}")
    print(f"Now: scp {out.name} <vm>:~/.config/{out.name}")


if __name__ == "__main__":
    main()

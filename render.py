"""Render the daily email - the SHORT-FORM Canopy redesign: masthead with
stats, Vern's note, "Tonight in one minute", a Read-the-full-edition button
plus Archive/Grove links, footer. Job listings, the reading list, follow-up
nudges and the sources line deliberately live in the full edition only
(webpage.py).

Marks rendered jobs as seen in history.json only after a successful send
(or explicit dry run), so a crashed run never swallows jobs.

Env:
    SMTP_USER / EMAIL_USER   sender address + SMTP login (Gmail)
    SMTP_PASS                Gmail app password
    SMTP_HOST / SMTP_SERVER  default smtp.gmail.com
    SMTP_PORT                default 587
    EMAIL_TO                 comma-separated recipients
    EDITION_URL              public URL of the web edition
    ALLOW_NO_EMAIL=1         render only - writes newsletter.html, no send

Usage:  python render.py
"""
from __future__ import annotations

import datetime
import html
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses
from pathlib import Path
from zoneinfo import ZoneInfo

from history import load_history, mark_seen, save_history

HERE = Path(__file__).parent
CURATED_FILE = HERE / "curated_data.json"
EDITIONS_DIR = HERE / "editions"
HALIFAX = ZoneInfo("America/Halifax")

DEFAULT_EDITION_URL = "https://clairechabot.github.io/papa-job-search/"


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_email(data: dict, now: datetime.datetime) -> tuple[str, str]:
    """Short-form email per newsletter-template.html: tables only, inline
    styles, web-safe fonts, no <style> block, no <details>."""
    date_short = now.strftime("%B %-d, %Y")
    edition_url = os.environ.get("EDITION_URL", DEFAULT_EDITION_URL).rstrip("/")
    stats = data.get("stats", {})
    apply_n = stats.get("apply", 0)

    subject = (f"Vern's evening scan - "
               f"{apply_n} apply-worthy lead{'s' if apply_n != 1 else ''} - "
               f"{now.strftime('%A, %B %-d')}")

    note = data.get("encouragement") or (
        "Tonight's scan is in. The full edition is one click below; the "
        "right seat only needs to appear once.")

    digest_rows = "".join(f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding-top:14px;">
        <div style="font-family:Helvetica,Arial,sans-serif;font-size:10.5px;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;color:#79735C;">{esc(d["label"])}</div>
        <p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:17px;line-height:1.6;color:#3C4433;padding-top:3px;">{esc(d["value"])}</p>
      </td></tr>
      </table>""" for d in data.get("digest", []))

    body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#E5DCC4;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#E5DCC4;font-family:Helvetica,Arial,sans-serif;">
<tr><td align="center" style="padding:28px 12px 40px;">

<table role="presentation" width="620" cellpadding="0" cellspacing="0" border="0" style="max-width:620px;width:100%;background:#EFE7D6;border:1px solid #DCD0B4;">

  <!-- masthead -->
  <tr><td style="background:#1E2E1A;padding:40px 34px 34px;text-align:center;">
    <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:3.4px;text-transform:uppercase;color:#D9B968;">Evening Edition &nbsp;&middot;&nbsp; {esc(date_short)}</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:42px;line-height:1.06;color:#F2EAD6;padding-top:14px;">The Next Chapter</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-style:italic;font-size:17px;color:#C6C3A6;padding-top:8px;">A nightly field report from Vern, your scout</div>
    <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2.2px;text-transform:uppercase;color:#C6C3A6;padding-top:20px;">{stats.get("postings_read", 0)} postings read &middot; {stats.get("apply", 0)} apply-worthy &middot; {stats.get("home", 0)} in Nova Scotia</div>
  </td></tr>

  <!-- Vern's note -->
  <tr><td style="padding:32px 34px 8px;">
    <div style="font-family:Helvetica,Arial,sans-serif;font-size:10.5px;font-weight:700;letter-spacing:2.6px;text-transform:uppercase;color:#A87E28;">A note from Vern</div>
    <p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:18px;line-height:1.68;color:#3C4433;padding-top:10px;">{esc(note)}</p>
    <p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-style:italic;font-size:18px;color:#1E2E1A;padding-top:12px;">Yours, Vern</p>
  </td></tr>

  <!-- Tonight in one minute -->
  <tr><td style="padding:26px 34px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#FCF7EB;border:1px solid #C09433;">
    <tr><td style="padding:24px 26px;">
      <div style="font-family:Helvetica,Arial,sans-serif;font-size:10.5px;font-weight:700;letter-spacing:2.6px;text-transform:uppercase;color:#A87E28;">Tonight in one minute</div>
      {digest_rows}
    </td></tr>
    </table>
  </td></tr>

  <!-- links out -->
  <tr><td style="padding:34px 34px 40px;text-align:center;">
    <a href="{edition_url}/" target="_blank" rel="noopener" style="display:inline-block;font-family:Helvetica,Arial,sans-serif;font-size:12px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:#F2EAD6;background:#1E2E1A;border:1px solid #C09433;padding:16px 30px;text-decoration:none;white-space:nowrap;">Read the full edition&nbsp;&rarr;</a>
    <p style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:15.5px;line-height:1.6;color:#79735C;padding-top:18px;">The full edition has every job with Vern's notes and Claude prompts, the recruiter watch and the complete reading list.</p>
    <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:600;letter-spacing:1.6px;text-transform:uppercase;color:#79735C;padding-top:18px;">
      <a href="{edition_url}/archive.html" style="color:#984417;text-decoration:none;">The Archive</a> &nbsp;&middot;&nbsp;
      <a href="{edition_url}/grove.html" style="color:#984417;text-decoration:none;">The Grove</a>
    </div>
  </td></tr>

  <!-- footer -->
  <tr><td style="background:#1E2E1A;padding:26px 34px;text-align:center;">
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:20px;color:#F2EAD6;">The Next Chapter</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-style:italic;font-size:15px;color:#C6C3A6;padding-top:4px;">Grown nightly by Vern, your scout in the canopy</div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return subject, body


def send_email(html_body: str, subject: str) -> None:
    smtp_user = os.environ.get("SMTP_USER") or os.environ.get("EMAIL_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = (os.environ.get("SMTP_SERVER") or os.environ.get("SMTP_HOST")
                 or "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    recipients = [e for _n, e in
                  getaddresses([os.environ.get("EMAIL_TO", "")]) if e]

    if not smtp_user or not smtp_pass:
        raise SystemExit("ERROR: SMTP_USER/SMTP_PASS not set. Check secrets!")
    if not recipients:
        raise SystemExit("ERROR: EMAIL_TO empty. Set the recipient.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Vern | The Next Chapter", smtp_user))
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"[SMTP] Connecting to {smtp_host}:{smtp_port} ...")
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_bytes())
    print(f"[SMTP] Sent to {len(recipients)} recipient(s).")


def main() -> None:
    if not CURATED_FILE.exists():
        raise SystemExit("ERROR: curated_data.json missing - run curate.py first")
    data = json.loads(CURATED_FILE.read_text(encoding="utf-8"))
    now = datetime.datetime.now(HALIFAX)

    subject, body = build_email(data, now)
    (HERE / "newsletter.html").write_text(body, encoding="utf-8")
    EDITIONS_DIR.mkdir(exist_ok=True)
    (EDITIONS_DIR / f"{now:%Y-%m-%d}-email.html").write_text(body,
                                                             encoding="utf-8")
    print(f"[render] wrote newsletter.html ({subject})")

    if os.environ.get("ALLOW_NO_EMAIL") == "1":
        print("[render] ALLOW_NO_EMAIL=1 - skipping send")
    else:
        send_email(body, subject)

    history = load_history()
    for job in data.get("jobs", []):
        mark_seen(job, history)
    for pick in data.get("ai_picks", []):
        history["ai_article_urls"].add(pick["url"])
    save_history(history)
    print(f"[render] history updated: {len(data.get('jobs', []))} jobs marked seen")


if __name__ == "__main__":
    main()

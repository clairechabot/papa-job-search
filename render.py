"""Render the email (bulletproof table HTML, email-client-safe) and send via
SMTP. Marks rendered jobs as seen in history.json only after a successful
send (or dry run), so a crashed run never swallows jobs.

Env (same conventions as the Curated Canopy newsletter):
    SMTP_USER / EMAIL_USER   sender address + SMTP login (Gmail)
    SMTP_PASS                Gmail app password
    SMTP_HOST / SMTP_SERVER  default smtp.gmail.com
    SMTP_PORT                default 587
    EMAIL_TO                 comma-separated recipients
    RECIPIENT_NAME           greeting name (default "Papa")
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
APPLICATIONS_FILE = HERE / "applications.json"
EDITIONS_DIR = HERE / "editions"
HALIFAX = ZoneInfo("America/Halifax")

# Palette: calm, professional, readable on every client.
INK = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#155e75"      # deep teal
STAR = "#b45309"        # amber
BG = "#f4f4f2"
CARD = "#ffffff"
RULE = "#e5e7eb"


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _stars(score) -> str:
    if not score:
        return ""
    return (f'<span style="color:{STAR};font-size:13px;letter-spacing:1px;">'
            f'{"&#9733;" * score}{"&#9734;" * (5 - score)}</span>')


def _job_row(job: dict) -> str:
    meta_bits = [b for b in (job.get("company"), job.get("location"),
                             job.get("salary"), job.get("source")) if b]
    why = (f'<div style="margin:6px 0 0;color:{INK};font-size:14px;'
           f'line-height:1.5;">{esc(job["why"])}</div>'
           if job.get("why") else "")
    watch = (f'<div style="margin:4px 0 0;color:{MUTED};font-size:13px;'
             f'font-style:italic;">Watch out: {esc(job["watch_out"])}</div>'
             if job.get("watch_out") else "")
    return f"""
    <tr><td style="padding:14px 18px;border-bottom:1px solid {RULE};">
      <div>{_stars(job.get("score"))}</div>
      <a href="{esc(job.get("url", ""))}"
         style="color:{ACCENT};font-size:16px;font-weight:bold;
                text-decoration:none;">{esc(job.get("title", "Untitled role"))}</a>
      <div style="color:{MUTED};font-size:13px;margin-top:3px;">
        {esc(" &middot; ".join(meta_bits))}</div>
      {why}{watch}
    </td></tr>"""


def _section(title: str, body: str) -> str:
    return f"""
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:{CARD};border-radius:8px;margin-top:18px;">
    <tr><td style="padding:14px 18px 4px;">
      <h2 style="margin:0;font-size:13px;letter-spacing:2px;color:{MUTED};
                 text-transform:uppercase;">{esc(title)}</h2>
    </td></tr>
    {body}
  </table>"""


def _load_applications() -> list[dict]:
    if APPLICATIONS_FILE.exists():
        return json.loads(APPLICATIONS_FILE.read_text(encoding="utf-8")).get(
            "applications", [])
    return []


def _followup_section(now: datetime.datetime) -> str:
    """Applications needing a follow-up nudge (>7 days silent) + interviews."""
    rows = []
    for app in _load_applications():
        if app.get("status") not in (None, "", "applied", "waiting"):
            continue
        applied = app.get("applied_on")
        try:
            days = (now.date() - datetime.date.fromisoformat(applied)).days
        except (TypeError, ValueError):
            continue
        if days >= 7:
            rows.append(
                f'<tr><td style="padding:8px 18px;border-bottom:1px solid {RULE};'
                f'font-size:14px;color:{INK};">{esc(app.get("role", "?"))} at '
                f'{esc(app.get("company", "?"))} - applied {days} days ago. '
                f'Worth a polite follow-up note.</td></tr>')
    if not rows:
        return ""
    return _section("Follow-ups", "".join(rows))


def build_email(data: dict, now: datetime.datetime, recipient: str) -> tuple[str, str]:
    """Returns (subject, html_body)."""
    edition = data.get("edition", "morning")
    weekday = data.get("weekday", now.strftime("%A"))
    date_line = now.strftime("%A, %B %-d")
    jobs = data.get("jobs", [])
    top = [j for j in jobs if (j.get("score") or 0) >= 4]
    worth_look = [j for j in jobs if (j.get("score") or 0) == 3]
    unscored = [j for j in jobs if j.get("score") is None]

    n_hot = len(top) or len(unscored) or len(jobs)
    subject = (f"{'Morning' if edition == 'morning' else 'Evening'} job scan - "
               f"{n_hot} lead{'s' if n_hot != 1 else ''} - {date_line}")

    greeting = data.get("encouragement") or (
        "New scan of the Atlantic Canada market below. The right seat only "
        "needs to show up once.")

    sections = []
    if top:
        sections.append(_section("Apply-worthy", "".join(_job_row(j) for j in top)))
    if worth_look:
        sections.append(_section("Worth a look", "".join(_job_row(j) for j in worth_look)))
    if unscored:
        sections.append(_section("New postings (unscored)",
                                 "".join(_job_row(j) for j in unscored)))
    if not (top or worth_look or unscored):
        sections.append(_section("Job scan", f"""
      <tr><td style="padding:14px 18px;color:{INK};font-size:14px;
                     line-height:1.6;">
        Nothing new that clears the bar this scan. That is normal - senior
        seats surface in waves. The scan runs again tonight.</td></tr>"""))

    for pick in data.get("ai_picks", []):
        pass  # rendered below as one section
    if data.get("ai_picks"):
        rows = "".join(f"""
      <tr><td style="padding:10px 18px;border-bottom:1px solid {RULE};">
        <a href="{esc(a["url"])}" style="color:{ACCENT};font-size:15px;
           font-weight:bold;text-decoration:none;">{esc(a["title"])}</a>
        <div style="color:{MUTED};font-size:12px;margin-top:2px;">{esc(a["feed"])}</div>
        <div style="color:{INK};font-size:13px;margin-top:4px;
                    line-height:1.5;">{esc(a.get("note", ""))}</div>
      </td></tr>""" for a in data["ai_picks"])
        sections.append(_section("AI for the workplace", rows))

    # Sunday evening: networking radar from NS business headlines.
    if weekday == "Sunday" and edition == "evening" and data.get("ns_articles"):
        rows = "".join(f"""
      <tr><td style="padding:8px 18px;border-bottom:1px solid {RULE};">
        <a href="{esc(a["url"])}" style="color:{ACCENT};font-size:14px;
           text-decoration:none;">{esc(a["title"])}</a>
        <span style="color:{MUTED};font-size:12px;"> - {esc(a["feed"])}</span>
      </td></tr>""" for a in data["ns_articles"][:8])
        sections.append(_section("Nova Scotia radar - who is growing, who is hiring next",
                                 rows))

    sections.append(_followup_section(now))

    body = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:{BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="max-width:600px;width:100%;
              font-family:Georgia,'Times New Roman',serif;">
  <tr><td style="padding:0 6px 14px;">
    <div style="font-size:12px;letter-spacing:3px;color:{MUTED};
                text-transform:uppercase;">The Next Chapter</div>
    <div style="font-size:24px;color:{INK};font-weight:bold;margin-top:2px;">
      {"Morning" if edition == "morning" else "Evening"} Edition</div>
    <div style="font-size:13px;color:{MUTED};margin-top:2px;">{date_line}</div>
  </td></tr>
  <tr><td style="padding:0 6px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:{CARD};border-radius:8px;border-left:4px solid {ACCENT};">
      <tr><td style="padding:14px 18px;color:{INK};font-size:15px;
                     line-height:1.6;">{esc(greeting)}</td></tr>
    </table>
    {"".join(sections)}
    <div style="padding:18px 6px;color:{MUTED};font-size:12px;line-height:1.6;">
      Sent with love, twice a day, by your automated job scout.<br>
      Sources this run: {esc("; ".join(f"{k}: {v}" for k, v in
                                       data.get("source_status", {}).items()))}
    </div>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
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
    msg["From"] = formataddr(("The Next Chapter", smtp_user))
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
    recipient = os.environ.get("RECIPIENT_NAME", "Papa")

    subject, body = build_email(data, now, recipient)
    (HERE / "newsletter.html").write_text(body, encoding="utf-8")
    EDITIONS_DIR.mkdir(exist_ok=True)
    (EDITIONS_DIR / f"{now:%Y-%m-%d}-{data.get('edition', 'morning')}.html"
     ).write_text(body, encoding="utf-8")
    print(f"[render] wrote newsletter.html ({subject})")

    if os.environ.get("ALLOW_NO_EMAIL") == "1":
        print("[render] ALLOW_NO_EMAIL=1 - skipping send")
    else:
        send_email(body, subject)

    # Only after a successful send (or explicit dry run) do jobs become "seen".
    history = load_history()
    for job in data.get("jobs", []):
        mark_seen(job, history)
    for pick in data.get("ai_picks", []):
        history["ai_article_urls"].add(pick["url"])
    save_history(history)
    print(f"[render] history updated: {len(data.get('jobs', []))} jobs marked seen")


if __name__ == "__main__":
    main()

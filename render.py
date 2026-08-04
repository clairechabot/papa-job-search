"""Render the daily email - a short cover from Vern (top jobs + note +
links to the full web edition) - and send via SMTP. The full everything-page
is built separately by webpage.py; the email links to it.

Marks rendered jobs as seen in history.json only after a successful send
(or explicit dry run), so a crashed run never swallows jobs.

Env:
    SMTP_USER / EMAIL_USER   sender address + SMTP login (Gmail)
    SMTP_PASS                Gmail app password
    SMTP_HOST / SMTP_SERVER  default smtp.gmail.com
    SMTP_PORT                default 587
    EMAIL_TO                 comma-separated recipients
    RECIPIENT_NAME           greeting name (default "Marcel")
    EDITION_URL              public URL of the web edition (footer links)
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

DEFAULT_EDITION_URL = "https://clairechabot.github.io/papa-job-search/"

INK = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#155e75"
STAR = "#b45309"
BG = "#f4f4f2"
CARD = "#ffffff"
RULE = "#e5e7eb"

TIER_LABELS = {1: "Nova Scotia", 2: "Eastern Canada", 3: "Remote",
               4: "Northeast US"}


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def stars(score) -> str:
    if not score:
        return ""
    return (f'<span style="color:{STAR};font-size:13px;letter-spacing:1px;">'
            f'{"&#9733;" * score}{"&#9734;" * (5 - score)}</span>')


def _tier_chip(job: dict) -> str:
    label = TIER_LABELS.get(job.get("tier"))
    bits = []
    if label:
        bits.append(label)
    if job.get("wildcard"):
        bits.append("left field")
    if not bits:
        return ""
    return (f'<span style="background:#e6eef0;color:{ACCENT};font-size:11px;'
            f'padding:1px 8px;border-radius:8px;font-family:Helvetica,Arial,'
            f'sans-serif;">{esc(" · ".join(bits))}</span>')


def _contact_line(job: dict) -> str:
    contacts = job.get("contacts") or []
    if not contacts:
        return ""
    c = contacts[0]
    who = esc(c.get("name", ""))
    title = esc(c.get("title", ""))
    url = esc(c.get("url", ""))
    link = (f' — <a href="{url}" style="color:{ACCENT};">LinkedIn</a>'
            if url else "")
    return (f'<div style="margin:5px 0 0;color:{INK};font-size:13px;">'
            f'<b>Reach out:</b> {who}{", " + title if title else ""}{link}'
            f' <span style="color:{MUTED};">(ask Vern in your Claude Project'
            f' to draft the note)</span></div>')


def _kickoff_box(job: dict) -> str:
    prompt = job.get("kickoff_prompt")
    if not prompt:
        return ""
    return f"""
      <div style="margin:8px 0 0;border:1px dashed {ACCENT};border-radius:6px;
                  background:#f7fafb;padding:8px 10px;">
        <div style="font-size:11px;letter-spacing:1px;color:{ACCENT};
                    text-transform:uppercase;font-family:Helvetica,Arial,
                    sans-serif;">Start here — copy into your Claude Project</div>
        <div style="font-family:Menlo,Consolas,monospace;font-size:12px;
                    color:{INK};line-height:1.5;margin-top:4px;
                    white-space:pre-wrap;">{esc(prompt)}</div>
      </div>"""


def job_row(job: dict, with_kickoff: bool = True) -> str:
    meta_bits = [b for b in (job.get("company"), job.get("location"),
                             job.get("salary"), job.get("source")) if b]
    summary = (f'<div style="margin:6px 0 0;color:{INK};font-size:14px;'
               f'line-height:1.5;">{esc(job["summary"])}</div>'
               if job.get("summary") else "")
    why = (f'<div style="margin:4px 0 0;color:{INK};font-size:14px;'
           f'line-height:1.5;"><b>Why:</b> {esc(job["why"])}</div>'
           if job.get("why") else "")
    watch = (f'<div style="margin:4px 0 0;color:{MUTED};font-size:13px;'
             f'font-style:italic;">Watch out: {esc(job["watch_out"])}</div>'
             if job.get("watch_out") else "")
    return f"""
    <tr><td style="padding:14px 18px;border-bottom:1px solid {RULE};">
      <div>{stars(job.get("score"))} {_tier_chip(job)}</div>
      <a href="{esc(job.get("url", ""))}"
         style="color:{ACCENT};font-size:16px;font-weight:bold;
                text-decoration:none;">{esc(job.get("title", "Untitled role"))}</a>
      <div style="color:{MUTED};font-size:13px;margin-top:3px;">
        {esc(" &middot; ".join(meta_bits))}</div>
      {summary}{why}{watch}{_contact_line(job)}
      {_kickoff_box(job) if with_kickoff else ""}
    </td></tr>"""


def section(title: str, body: str) -> str:
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
    rows = []
    for app in _load_applications():
        if app.get("status") not in (None, "", "applied", "waiting"):
            continue
        try:
            days = (now.date()
                    - datetime.date.fromisoformat(app.get("applied_on"))).days
        except (TypeError, ValueError):
            continue
        if days >= 7:
            rows.append(
                f'<tr><td style="padding:8px 18px;border-bottom:1px solid {RULE};'
                f'font-size:14px;color:{INK};">{esc(app.get("role", "?"))} at '
                f'{esc(app.get("company", "?"))} - applied {days} days ago. '
                f'Worth a polite follow-up note (Vern can draft it).</td></tr>')
    if not rows:
        return ""
    return section("Follow-ups", "".join(rows))


def build_email(data: dict, now: datetime.datetime) -> tuple[str, str]:
    """The short daily cover: Vern's note, top jobs, links out."""
    date_line = now.strftime("%A, %B %-d")
    edition_url = os.environ.get("EDITION_URL", DEFAULT_EDITION_URL).rstrip("/")
    jobs = data.get("jobs", [])
    top = [j for j in jobs if (j.get("score") or 0) >= 4]
    worth_look = [j for j in jobs if (j.get("score") or 0) == 3]
    unscored = [j for j in jobs if j.get("score") is None]
    wildcards = [j for j in jobs if j.get("wildcard")
                 and (j.get("score") or 0) >= 3]

    n_hot = len(top) or len(worth_look) or len(unscored)
    subject = (f"Vern's evening scan - {n_hot} lead{'s' if n_hot != 1 else ''}"
               f" - {date_line}")

    greeting = data.get("encouragement") or (
        "Today's scan of the market is below. The right seat only needs to "
        "show up once.")

    sections = []
    if top:
        sections.append(section("Apply-worthy",
                                "".join(job_row(j) for j in top)))
    if worth_look:
        sections.append(section("Worth a look",
                                "".join(job_row(j) for j in worth_look[:5])))
    if unscored:
        sections.append(section("New postings (unscored)",
                                "".join(job_row(j, with_kickoff=False)
                                        for j in unscored[:10])))
    if wildcards:
        sections.append(section("Left field",
                                "".join(job_row(j) for j in wildcards
                                        if j not in top)))
    if not (top or worth_look or unscored):
        sections.append(section("Job scan", f"""
      <tr><td style="padding:14px 18px;color:{INK};font-size:14px;
                     line-height:1.6;">
        Nothing new clears the bar today. That is normal - senior seats
        surface in waves, and the recruiters section on the full page is the
        better lever on quiet days. The scan runs again tomorrow.</td></tr>"""))

    if data.get("ai_picks"):
        rows = "".join(f"""
      <tr><td style="padding:10px 18px;border-bottom:1px solid {RULE};">
        <a href="{esc(a["url"])}" style="color:{ACCENT};font-size:15px;
           font-weight:bold;text-decoration:none;">{esc(a["title"])}</a>
        <div style="color:{MUTED};font-size:12px;margin-top:2px;">{esc(a["feed"])}</div>
        <div style="color:{INK};font-size:13px;margin-top:4px;
                    line-height:1.5;">{esc(a.get("note", ""))}</div>
      </td></tr>""" for a in data["ai_picks"])
        sections.append(section("AI for the workplace", rows))

    sections.append(_followup_section(now))

    footer_links = (
        f'<a href="{edition_url}/" style="color:{ACCENT};font-weight:bold;">'
        f'Read the full edition &rarr;</a> &nbsp;&middot;&nbsp; '
        f'<a href="{edition_url}/archive.html" style="color:{ACCENT};">The Archive</a>'
        f' &nbsp;&middot;&nbsp; '
        f'<a href="{edition_url}/grove.html" style="color:{ACCENT};">The Grove</a>')

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
                text-transform:uppercase;">Vern &middot; The Next Chapter</div>
    <div style="font-size:24px;color:{INK};font-weight:bold;margin-top:2px;">
      Evening Edition</div>
    <div style="font-size:13px;color:{MUTED};margin-top:2px;">{date_line}</div>
  </td></tr>
  <tr><td style="padding:0 6px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:{CARD};border-radius:8px;border-left:4px solid {ACCENT};">
      <tr><td style="padding:14px 18px;color:{INK};font-size:15px;
                     line-height:1.6;">{esc(greeting)}
        <div style="margin-top:6px;color:{MUTED};font-size:13px;">- Vern</div>
      </td></tr>
    </table>
    {"".join(sections)}
    <div style="padding:16px 6px 4px;font-size:15px;">{footer_links}</div>
    <div style="padding:8px 6px 18px;color:{MUTED};font-size:12px;line-height:1.6;">
      The full edition has every job (including the maybes), all hiring
      contacts, the recruiter watch, and the complete reading list.<br>
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
    (EDITIONS_DIR / f"{now:%Y-%m-%d}.html").write_text(body, encoding="utf-8")
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

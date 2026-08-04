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

# Botanical Editorial palette, shared with the Curated Canopy newsletter
# (Newsletter/design/tokens.css): warm stone paper, forest ink, moss accents,
# terracotta links.
INK = "#20271F"        # deep forest near-black
SOFT = "#4A4A3E"       # warm taupe text
MUTED = "#7C7565"      # muted metadata
FOREST = "#2C3A2B"     # headings
MOSS = "#6E7B4B"       # accents
MOSS_DEEP = "#55603A"  # eyebrows / labels
ACCENT = "#A85A36"     # terracotta (links, CTA)
STAR = "#A85A36"
BG = "#E9E1D1"         # page background (deeper stone)
CARD = "#F4EEE2"       # paper
SURFACE = "#FBF7EE"    # note / inset panels
RULE = "#D9CFBC"       # hairline
SERIF = "Georgia,'Times New Roman',serif"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"

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
    return (f'<span style="background:#EDE7D8;color:{MOSS_DEEP};font-size:11px;'
            f'padding:2px 10px;border-radius:100px;font-family:{SANS};'
            f'letter-spacing:0.04em;">{esc(" · ".join(bits))}</span>')


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
      <div style="margin:10px 0 0;border:1px dashed {ACCENT};border-radius:8px;
                  background:{CARD};padding:9px 12px;">
        <div style="font-size:10.5px;letter-spacing:2px;color:{ACCENT};
                    text-transform:uppercase;font-family:{SANS};
                    font-weight:600;">Start here — copy into your Claude Project</div>
        <div style="font-family:ui-monospace,Menlo,Consolas,monospace;
                    font-size:12px;color:{SOFT};line-height:1.55;
                    margin-top:5px;white-space:pre-wrap;">{esc(prompt)}</div>
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
         style="background:{SURFACE};border:1px solid {RULE};
                border-radius:12px;margin-top:20px;">
    <tr><td style="padding:16px 18px 6px;">
      <h2 style="margin:0;font-size:11px;letter-spacing:3px;color:{MOSS_DEEP};
                 text-transform:uppercase;font-family:{SANS};
                 font-weight:600;">{esc(title)}</h2>
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
<tr><td align="center" style="padding:26px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="max-width:600px;width:100%;background:{CARD};
              border:1px solid {RULE};border-radius:12px;
              font-family:{SERIF};">
  <tr><td align="center" style="padding:38px 28px 24px;">
    <div style="font-size:11px;font-weight:600;letter-spacing:4px;
                color:{MOSS_DEEP};text-transform:uppercase;
                font-family:{SANS};">The Next Chapter</div>
    <div style="font-family:{SERIF};font-size:38px;line-height:1.05;
                color:{FOREST};margin-top:14px;">Evening Edition</div>
    <div style="font-family:{SERIF};font-style:italic;font-size:15px;
                color:{SOFT};margin-top:8px;">a nightly field report from
                Vern, your scout</div>
    <div style="font-size:11px;letter-spacing:2.5px;color:{MUTED};
                text-transform:uppercase;font-family:{SANS};
                margin-top:18px;">{date_line}
                &nbsp;&middot;&nbsp; Atlantic Time</div>
  </td></tr>
  <tr><td style="padding:0 20px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:{SURFACE};border-top:1px solid {RULE};
                  border-bottom:1px solid {RULE};">
      <tr>
        <td width="58" valign="top" style="padding:22px 0 22px 18px;">
          <div style="width:44px;height:44px;border-radius:50%;
                      border:1px solid {MOSS};color:{MOSS_DEEP};
                      font-family:{SERIF};font-size:21px;line-height:44px;
                      text-align:center;">V</div>
        </td>
        <td style="padding:20px 18px 22px 14px;">
          <div style="font-size:10.5px;font-weight:600;letter-spacing:3px;
                      color:{MOSS_DEEP};text-transform:uppercase;
                      font-family:{SANS};">A note from Vern</div>
          <div style="font-family:{SERIF};color:{INK};font-size:16px;
                      line-height:1.65;margin-top:7px;">{esc(greeting)}</div>
          <div style="font-family:{SERIF};font-style:italic;color:{MUTED};
                      font-size:13px;margin-top:8px;">Yours, Vern</div>
        </td>
      </tr>
    </table>
    {"".join(sections)}
    <div style="padding:20px 6px 4px;font-size:15px;text-align:center;
                font-family:{SANS};">{footer_links}</div>
    <div style="padding:10px 14px 26px;color:{MUTED};font-size:12px;
                line-height:1.6;text-align:center;font-family:{SANS};">
      The full edition has every job (including the maybes), all hiring
      contacts, the recruiter watch, and the complete reading list.<br><br>
      <span style="font-size:11px;">Sources this run:
      {esc("; ".join(f"{k}: {v}" for k, v in
                     data.get("source_status", {}).items()))}</span>
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

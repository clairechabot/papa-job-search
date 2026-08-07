"""Build the full web edition for GitHub Pages - Canopy redesign templates
(applied 2026-08 from the Newsletter_redesign_with_Canopy_system package;
per Claire, the full edition carries NO "note from Vern" - the digest sits
centered in its place; the note lives in the email only).

Outputs (all committed; Pages serves /docs on main):
    docs/index.html          full edition: masthead stats, Tonight-in-one-
                             minute digest, top pick, five tab panels
    docs/editions/<date>.html  permanent copy
    docs/archive.html        browsable index of past editions
    docs/grove.json          cumulative store of everything ever featured
    docs/grove.html          The Grove - client-side search + filter chips

Usage:  python webpage.py   (after curate.py)
"""
from __future__ import annotations

import datetime
import html
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from history import job_fingerprint, normalize_url

HERE = Path(__file__).parent
CURATED_FILE = HERE / "curated_data.json"
DOCS = HERE / "docs"
EDITIONS = DOCS / "editions"
GROVE_JSON = DOCS / "grove.json"
HALIFAX = ZoneInfo("America/Halifax")

TIER_LABELS = {1: "Nova Scotia", 2: "Eastern Canada", 3: "Remote",
               4: "Northeast US"}

FIRMS = [
    ("Meridia Recruitment (KBRS)", "Halifax · Atlantic Canada",
     "https://meridiarecruitment.ca/career-opportunities/careers"),
    ("Venor", "Halifax", "https://venor.ca/opportunities"),
    ("Summit Search Group", "National · Atlantic desk",
     "https://www.summitsearchgroup.com/opportunities/"),
    ("Macdonald Search Group", "Halifax office",
     "https://macdonaldsearchgroup.com/job-listings"),
    ("Lock Search Group", "Atlantic practice",
     "https://locksearchgroup.com/opportunities/"),
    ("Accountant Staffing", "Halifax · finance specialists",
     "https://www.accountantstaffing.com/job-opportunities"),
    ("TrueNorth Executive Search", "US · PE-backed CFO mandates",
     "https://careers.truenorthsearch.com"),
    ("CFO Search Inc", "US · CFO boutique",
     "https://www.cfo-search.com/cfo-jobs/"),
    ("Page Executive", "Global · CFO practice",
     "https://www.pageexecutive.com/jobs/cfo-financial-management"),
    ("Robert Half", "Canada · finance & accounting",
     "https://www.roberthalf.com/ca/en/jobs"),
    ("Falcon", "US · PE talent partner - no public listings, introduce yourself",
     "https://falcon-pe.com/"),
    ("Vision Search Partners", "New England · financial search - no public "
     "listings, introduce yourself", "https://visionsearchpartners.com/"),
    ("Bohan & Bradstreet", "Connecticut · openings post to their LinkedIn",
     "https://www.linkedin.com/company/bohan-&-bradstreet"),
]

FONTS = ("https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,"
         "wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Newsreader:ital,"
         "opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Hanken+"
         "Grotesk:wght@400;500;600;700&display=swap")

# Template CSS, verbatim from index-template.html, with two sanctioned
# adaptations for the note removal: .note/.monogram rules dropped and .intro
# re-flowed as a single centered digest column.
INDEX_CSS = """
:root{
  --paper:#EFE7D6;--paper-deep:#E5DCC4;--surface:#FCF7EB;
  --ink:#1B2716;--ink-soft:#3C4433;--ink-mute:#79735C;
  --forest:#1E2E1A;--forest-deep:#162313;
  --brass:#C09433;--brass-deep:#A87E28;--brass-soft:#D9B968;
  --clay:#B6541F;--clay-deep:#984417;
  --line:#DCD0B4;--line-on-dark:rgba(216,185,104,.32);
  --cream:#F2EAD6;--cream-mute:#C6C3A6;
  --display:'Cormorant Garamond',Georgia,'Times New Roman',serif;
  --serif:'Newsreader',Georgia,'Times New Roman',serif;
  --sans:'Hanken Grotesk',-apple-system,'Segoe UI',sans-serif;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;background:var(--paper)}
body{font-family:var(--sans);background:var(--paper);color:var(--ink);line-height:1.6;-webkit-font-smoothing:antialiased;min-height:100vh;display:flex;flex-direction:column;overflow-wrap:break-word}
main{flex:1 0 auto}
a{color:var(--clay-deep);text-decoration:none}
a:hover{color:var(--clay)}
.wrap{max-width:1120px;margin:0 auto;padding:0 40px;width:100%}
.eyebrow{display:inline-flex;align-items:center;gap:11px;font-size:11px;font-weight:600;letter-spacing:.24em;text-transform:uppercase;color:var(--brass-deep)}
.eyebrow::before,.eyebrow::after{content:"";width:6px;height:6px;background:var(--brass);transform:rotate(45deg);flex:none}
.eyebrow.plain::before,.eyebrow.plain::after{display:none}

/* masthead */
.cover{position:relative;background:var(--forest);color:var(--cream);text-align:center;padding:64px 40px 54px;overflow:hidden}
.cover::before{content:"";position:absolute;inset:14px;border:1px solid var(--line-on-dark)}
.cover::after{content:"";position:absolute;inset:19px;border:1px solid rgba(216,185,104,.14)}
.cover-in{position:relative}
.cover .eyebrow{color:var(--brass-soft)}
.cover .eyebrow::before,.cover .eyebrow::after{background:var(--brass-soft)}
.cover h1{font-family:var(--display);font-weight:600;font-size:clamp(52px,8vw,96px);line-height:.95;margin-top:18px}
.cover .tagline{font-family:var(--display);font-style:italic;font-weight:500;font-size:clamp(19px,2.6vw,26px);color:var(--cream-mute);margin-top:12px}
.cover .stats{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:14px;margin-top:26px;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--cream-mute)}
.cover .stats .dot{width:4px;height:4px;border-radius:50%;background:var(--brass-soft)}

/* the daily groaner (Marcel's request: one fresh dad joke per edition) */
.groaner{max-width:720px;margin:0 auto;padding:38px 40px 0;text-align:center}
.groaner p{font-family:var(--serif);font-style:italic;font-size:17.5px;line-height:1.6;color:var(--ink-soft);margin-top:12px}

/* intro: digest only (Vern's note removed from the full edition) */
.intro{max-width:720px;margin:0 auto;padding:44px 40px 0}
.digest{min-width:0}
.digest .row{display:flex;gap:16px;padding:11px 0;border-top:1px solid var(--line);align-items:baseline}
.digest .row:first-of-type{border-top:0}
.digest .k{flex:none;width:96px;font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-mute)}
.digest .v{font-family:var(--serif);font-size:16.5px;line-height:1.5;color:var(--ink-soft)}

/* ornament rule */
.rule{display:flex;justify-content:center;align-items:center;gap:10px;padding:34px 0 6px}
.rule i{width:120px;height:1px;background:var(--brass);opacity:.55}
.rule b{width:7px;height:7px;background:var(--brass);transform:rotate(45deg)}

/* top pick */
.pick{display:grid;grid-template-columns:1.55fr 1fr;border-top:1px solid var(--brass);border-bottom:1px solid var(--brass)}
.pick .main{padding:44px 48px 44px 0;border-right:1px solid var(--line);display:flex;flex-direction:column;justify-content:center}
.pick h2{margin-top:16px}
.pick h2 a{font-family:var(--display);font-weight:600;font-size:clamp(32px,3.6vw,46px);line-height:1.05;color:var(--forest)}
.pick h2 a:hover{color:var(--clay-deep)}
.pick .meta{margin-top:12px;font-size:11.5px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-mute)}
.pick p{font-family:var(--serif);font-size:18px;line-height:1.6;color:var(--ink-soft);margin-top:18px;max-width:46ch}
.pick .go{display:inline-flex;align-items:center;gap:9px;margin-top:26px;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
.pick .go span{color:var(--brass-deep)}
.pick .side{padding:44px 0 44px 44px;display:flex;flex-direction:column;justify-content:center;gap:18px}
.pick .side .k{font-size:10.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-mute)}
.pick .side .stars{color:var(--clay);font-size:22px;letter-spacing:5px;margin-top:6px}
.pick .side .region{font-family:var(--display);font-size:26px;color:var(--forest);margin-top:2px}
.pick .side p{font-family:var(--serif);font-style:italic;font-size:16px;line-height:1.5;color:var(--ink-mute);margin-top:4px;max-width:none}

/* sticky tabs */
.tabbar{position:sticky;top:0;z-index:50;background:rgba(239,231,214,.92);backdrop-filter:blur(10px) saturate(120%);border-bottom:1px solid var(--brass);margin-top:10px}
.tabbar-in{max-width:1120px;margin:0 auto;padding:0 40px;display:flex;align-items:center;gap:4px;height:62px;overflow-x:auto;scrollbar-width:none}
.tabbar-in::-webkit-scrollbar{display:none}
.tab{white-space:nowrap;cursor:pointer;padding:20px 15px;font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;background:none;border:0;border-bottom:2px solid transparent;color:var(--ink-mute)}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--forest);border-bottom-color:var(--brass)}
.tab .ix{font-family:var(--display);font-style:italic;font-weight:600;font-size:14px;text-transform:none;letter-spacing:0;margin-right:7px;color:var(--brass-deep)}
.tab .n{margin-left:8px;font-size:10px;letter-spacing:.08em;color:#B3AA92}
.tab.active .n{color:var(--brass-deep)}

/* sections */
.panel{display:none;padding:52px 0 24px}
.panel.active{display:block}
.sec-head{margin-bottom:34px}
.sec-head h3{font-family:var(--display);font-weight:600;font-size:clamp(32px,4.2vw,48px);line-height:1.02;color:var(--forest);margin-top:12px}
.sec-head .lede{font-family:var(--serif);font-style:italic;font-size:18px;color:var(--ink-mute);margin-top:9px;max-width:56ch}
.list{border-bottom:1px solid var(--line)}

/* job row */
.job{display:grid;grid-template-columns:112px minmax(0,1fr);gap:0 32px;padding:30px 0;border-top:1px solid var(--line);align-items:start}
.job .rail{display:flex;flex-direction:column;gap:9px;padding-top:7px}
.job .no{font-family:var(--display);font-style:italic;font-weight:600;font-size:16px;color:var(--brass-deep)}
.job .stars{color:var(--clay);font-size:15px;letter-spacing:3px}
.badge{align-self:flex-start;font-size:9.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:4px 9px;border:1px solid var(--brass);color:var(--brass-deep)}
.job .body{min-width:0;max-width:72ch}
.job h4 a{font-family:var(--display);font-weight:600;font-size:31px;line-height:1.12;color:var(--forest);display:block}
.job h4 a:hover{color:var(--clay-deep)}
.job .meta{margin-top:9px;font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-mute)}
.job .summary{font-family:var(--serif);font-size:17.5px;line-height:1.62;color:var(--ink-soft);margin-top:15px}
.block{margin-top:16px}
.block .k{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--brass-deep)}
.block p{font-family:var(--serif);font-size:17px;line-height:1.58;color:var(--ink-soft);margin-top:3px}
.watch{margin-top:16px;border-left:2px solid var(--clay);padding-left:16px}
.watch .k{font-size:10.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--clay-deep)}
.watch p{font-family:var(--serif);font-style:italic;font-size:16.5px;line-height:1.55;color:var(--ink-mute);margin-top:3px}

/* prompt disclosure */
details.prompt{margin-top:20px;border-top:1px solid var(--line)}
details.prompt summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:9px;margin-top:14px;font-size:11.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--clay-deep)}
details.prompt summary::-webkit-details-marker{display:none}
details.prompt summary::before{content:"+";color:var(--brass-deep)}
details.prompt[open] summary::before{content:"–"}
details.prompt .inner{margin-top:14px;background:var(--surface);border:1px solid var(--line);padding:18px 20px}
details.prompt pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.6;white-space:pre-wrap;color:var(--ink-soft)}
.copyrow{display:flex;align-items:center;gap:14px;margin-top:16px;flex-wrap:wrap}
.copy{cursor:pointer;font-family:var(--sans);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:10px 18px;border:1px solid var(--brass);background:transparent;color:var(--brass-deep)}
.copy:hover{background:var(--brass);color:var(--forest-deep)}
.copyhint{font-size:12px;color:var(--ink-mute)}
/* save button + tracker badges */
.actions{margin-top:10px}
.saveb{cursor:pointer;font-family:var(--sans);font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:7px 14px;border:1px solid var(--line);background:transparent;color:var(--ink-mute)}
.saveb:hover{border-color:var(--brass);color:var(--brass-deep)}
.saveb.on{border-color:var(--brass);background:var(--brass);color:var(--forest-deep)}
.badge.tstat{background:var(--forest);color:var(--cream);border-color:var(--forest)}
.inplay-status{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--brass-deep)}
.inplay-quiet{color:var(--clay-deep)}
.addlist{margin-top:16px;border-top:1px dashed var(--line);padding-top:12px}
.addlist .k{font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-mute)}
.addlist ul{margin:8px 0 0;padding-left:20px}
.addlist li{font-size:13.5px;line-height:1.6;color:var(--ink-soft);margin-top:4px}

/* footer */
footer{position:relative;margin-top:40px;background:var(--forest);color:var(--cream);padding:52px 40px 58px;text-align:center}
footer::before{content:"";position:absolute;inset:12px;border:1px solid var(--line-on-dark)}
footer .in{position:relative}
footer .mark{font-family:var(--display);font-weight:600;font-size:32px}
footer .tag{font-family:var(--display);font-style:italic;font-size:18px;color:var(--cream-mute);margin-top:6px}
footer .links{display:flex;gap:18px;justify-content:center;flex-wrap:wrap;margin-top:22px;font-size:11px;letter-spacing:.16em;text-transform:uppercase}
footer .links a{color:var(--brass-soft)}
footer .rule i{background:var(--brass-soft);width:90px;opacity:.6}
footer .rule b{background:var(--brass-soft)}

@media (max-width:900px){
  .pick{grid-template-columns:1fr}
  .pick .main{padding:34px 0;border-right:0;border-bottom:1px solid var(--line)}
  .pick .side{padding:28px 0}
}
@media (max-width:620px){
  .wrap,.intro,.tabbar-in{padding-left:22px;padding-right:22px}
  .cover{padding:48px 22px 40px}
  .job{grid-template-columns:1fr;gap:14px}
  .job .rail{flex-direction:row;align-items:center;gap:14px;padding-top:0}
  .job h4 a{font-size:26px}
}
"""

INDEX_SCRIPTS = """
<script>
// Section tabs
document.getElementById('tabs').addEventListener('click', function (e) {
  var b = e.target.closest('.tab'); if (!b) return;
  document.querySelectorAll('.tab').forEach(function (t) { t.classList.toggle('active', t === b); });
  document.querySelectorAll('.panel').forEach(function (p) { p.classList.toggle('active', p.id === b.dataset.tab); });
  window.scrollTo({ top: document.querySelector('.tabbar').offsetTop - 1, behavior: 'smooth' });
});
// Copy prompt buttons
document.addEventListener('click', function (e) {
  var b = e.target.closest('.copy'); if (!b) return;
  var pre = b.closest('.inner').querySelector('pre');
  var done = function () { b.textContent = 'Copied'; setTimeout(function () { b.textContent = 'Copy prompt'; }, 1600); };
  if (navigator.clipboard) navigator.clipboard.writeText(pre.textContent).then(done, done); else done();
});
// Save buttons: localStorage immediately, then fire-and-forget to the
// tracker sheet's webhook when configured (window.NC_CFG, injected at
// build time from repo variables). Browser-only mode otherwise.
(function () {
  var KEY = 'nc_saved';
  var cfg = window.NC_CFG || {};
  function loadSaved() { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } }
  function storeSaved(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
  function paint(b, on) { b.classList.toggle('on', on); b.innerHTML = on ? '&#9733; Saved' : '&#9734; Save'; }
  var saved = loadSaved();
  document.querySelectorAll('.saveb').forEach(function (b) { paint(b, !!saved[b.dataset.nurl]); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.saveb'); if (!b) return;
    var s = loadSaved();
    var on = !s[b.dataset.nurl];
    if (on) s[b.dataset.nurl] = 1; else delete s[b.dataset.nurl];
    storeSaved(s); paint(b, on);
    if (cfg.webhook) {
      try {
        fetch(cfg.webhook, { method: 'POST', mode: 'no-cors', body: JSON.stringify({
          token: cfg.token, action: on ? 'save' : 'unsave', via: 'edition',
          title: b.dataset.title, company: b.dataset.company,
          location: b.dataset.location, salary: b.dataset.salary,
          score: b.dataset.score, source: b.dataset.source, url: b.dataset.url
        }) });
      } catch (err) {}
    }
  });
})();
</script>
"""

FOOTER = """
<footer>
  <div class="in">
    <div class="rule"><i></i><b></b><i></i></div>
    <div class="mark">The Next Chapter</div>
    <div class="tag">Grown nightly by Vern, your scout in the canopy</div>
    <div class="links">
      <a href="./index.html">Today</a>
      <a href="./archive.html">The Archive</a>
      <a href="./grove.html">The Grove</a>
    </div>
  </div>
</footer>
"""

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]

# ---------------------------------------------------------------------------
# Tracker read-back (fetch.py downloads the published sheet CSV into
# tracker_data.json when SHEET_CSV_URL is configured; absent file = feature
# quietly off). TRACKER maps normalized url / fingerprint -> row dict.
# ---------------------------------------------------------------------------
TRACKER_FILE = Path(__file__).parent / "tracker_data.json"
TRACKER: dict = {"rows": [], "by_id": {}}


def load_tracker() -> None:
    if not TRACKER_FILE.exists():
        return
    try:
        rows = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - boundary: generated file
        return
    TRACKER["rows"] = rows
    for r in rows:
        if r.get("normalized_url"):
            TRACKER["by_id"][r["normalized_url"]] = r
        if r.get("fingerprint"):
            TRACKER["by_id"][r["fingerprint"]] = r


def tracker_status(job: dict) -> str:
    r = (TRACKER["by_id"].get(normalize_url(job.get("url", "")))
         or TRACKER["by_id"].get(job_fingerprint(job)))
    return (r or {}).get("status", "")


# Config the page's client script needs; injected at build time from repo
# variables. Empty values (var not set) leave buttons in browser-only mode -
# `or` guards per the EDITION_URL empty-string lesson.
def nc_cfg() -> str:
    cfg = {"webhook": os.environ.get("SHEET_WEBHOOK_URL") or "",
           "token": os.environ.get("SHEET_TOKEN") or "",
           "csv": os.environ.get("SHEET_CSV_URL") or ""}
    return f"<script>window.NC_CFG = {json.dumps(cfg)};</script>"


def esc(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


def stars_html(score) -> str:
    if not score:
        return ""
    return "&#9733;" * score + "&#9734;" * (5 - score)


def region_label(job: dict) -> str:
    if job.get("wildcard"):
        return "Left field"
    return TIER_LABELS.get(job.get("tier"), "")


def job_row(job: dict, number: int, with_prompt: bool = True) -> str:
    rail = [f'<div class="no">No. {number:02d}</div>']
    if job.get("score"):
        rail.append(f'<div class="stars">{stars_html(job["score"])}</div>')
    region = region_label(job)
    if region:
        rail.append(f'<div class="badge">{esc(region)}</div>')
    tstat = tracker_status(job)
    if tstat:
        rail.append(f'<div class="badge tstat">{esc(tstat)}</div>')
    meta = " · ".join(b for b in (job.get("company"), job.get("location"),
                                  job.get("salary"), job.get("source")) if b)
    save_btn = (f'<div class="actions"><button class="saveb" type="button" '
                f'data-nurl="{esc(normalize_url(job.get("url", "")))}" '
                f'data-url="{esc(job.get("url", ""))}" '
                f'data-title="{esc(job.get("title", ""))}" '
                f'data-company="{esc(job.get("company", ""))}" '
                f'data-location="{esc(job.get("location", ""))}" '
                f'data-salary="{esc(job.get("salary", ""))}" '
                f'data-score="{job.get("score") or ""}" '
                f'data-source="{esc(job.get("source", ""))}">'
                f'&#9734; Save</button></div>')
    body = [f'<h4><a href="{esc(job.get("url", ""))}" target="_blank" '
            f'rel="noopener">{esc(job.get("title", "Untitled role"))}</a></h4>',
            f'<div class="meta">{esc(meta)}</div>', save_btn]
    if job.get("summary"):
        body.append(f'<p class="summary">{esc(job["summary"])}</p>')
    if job.get("why"):
        body.append(f'<div class="block"><div class="k">Why</div>'
                    f'<p>{esc(job["why"])}</p></div>')
    if job.get("watch_out"):
        body.append(f'<div class="watch"><div class="k">Watch out</div>'
                    f'<p>{esc(job["watch_out"])}</p></div>')
    contacts = job.get("contacts") or []
    if contacts:
        rows = " · ".join(
            (f'<a href="{esc(c.get("url", ""))}" target="_blank" '
             f'rel="noopener">{esc(c.get("name", ""))}</a>'
             if c.get("url") else esc(c.get("name", "")))
            + (f', {esc(c["title"])}' if c.get("title") else "")
            for c in contacts)
        body.append(f'<div class="block"><div class="k">Reach out</div>'
                    f'<p>{rows}</p></div>')
    if with_prompt and job.get("kickoff_prompt"):
        attachments = job.get("attachments") or [
            "Paste the full posting text - open the job link above and "
            "copy everything."]
        items = "".join(f"<li>{esc(a)}</li>" for a in attachments)
        body.append(f'''<details class="prompt">
            <summary>Start here — Claude Project prompt</summary>
            <div class="inner">
              <pre>{esc(job["kickoff_prompt"])}</pre>
              <div class="copyrow">
                <button class="copy" type="button">Copy prompt</button>
                <span class="copyhint">Paste into a new chat in your &ldquo;Next Chapter HQ&rdquo; project.</span>
              </div>
              <div class="addlist">
                <div class="k">What Marcel should add to the chat:</div>
                <ul>{items}</ul>
              </div>
            </div>
          </details>''')
    return (f'<article class="job"><div class="rail">{"".join(rail)}</div>'
            f'<div class="body">{"".join(body)}</div></article>')


def inplay_row(r: dict, number: int) -> str:
    """One tracked application in the In-play section."""
    line, quiet = "", False
    if r.get("applied_on"):
        try:
            days = (datetime.date.today()
                    - datetime.date.fromisoformat(r["applied_on"][:10])).days
            line = f"Applied {r['applied_on'][:10]} ({days} days ago)"
            quiet = (r.get("status") == "Applied" and days >= 10
                     and not r.get("last_contact_on"))
        except ValueError:
            line = f"Applied {r['applied_on'][:10]}"
    bits = [b for b in (line,
                        f"last contact {r['last_contact_on'][:10]}"
                        if r.get("last_contact_on") else "",
                        f"meeting {r['meeting_on'][:10]}"
                        if r.get("meeting_on") else "") if b]
    body = [f'<h4><a href="{esc(r.get("url", "") or "#")}" target="_blank" '
            f'rel="noopener">{esc(r.get("title") or r.get("company", ""))}</a></h4>',
            f'<div class="meta">{esc(" · ".join(x for x in (r.get("company"), ", ".join(bits)) if x))}</div>']
    if quiet:
        body.append('<div class="watch"><div class="k">Gone quiet</div>'
                    '<p>No response in 10+ days. Worth a short follow-up '
                    'note - ask Vern in the Project to draft it.</p></div>')
    rail = [f'<div class="no">No. {number:02d}</div>',
            f'<div class="inplay-status{" inplay-quiet" if quiet else ""}">'
            f'{esc(r.get("status", ""))}</div>']
    return (f'<article class="job"><div class="rail">{"".join(rail)}</div>'
            f'<div class="body">{"".join(body)}</div></article>')


def article_row(a: dict) -> str:
    body = [f'<h4><a href="{esc(a.get("url", ""))}" target="_blank" '
            f'rel="noopener">{esc(a.get("title", ""))}</a></h4>',
            f'<div class="meta">{esc(a.get("feed", ""))}</div>']
    if a.get("note"):
        body.append(f'<p class="summary">{esc(a["note"])}</p>')
    return (f'<article class="job"><div class="rail">'
            f'<div class="badge">{esc(a.get("feed", ""))}</div></div>'
            f'<div class="body">{"".join(body)}</div></article>')


def _panel(pid: str, index: int, title: str, lede: str, rows: str,
           active: bool = False) -> str:
    return f'''
  <section class="panel{" active" if active else ""}" id="{pid}">
    <div class="sec-head">
      <div class="eyebrow">Section {["One", "Two", "Three", "Four", "Five", "Six"][index]}</div>
      <h3>{title}</h3>
      <div class="lede">{lede}</div>
    </div>
    <div class="list">{rows}</div>
  </section>'''


def build_edition(data: dict, now: datetime.datetime) -> str:
    date_long = now.strftime("%A, %B %-d, %Y")
    date_short = now.strftime("%B %-d, %Y")
    jobs = data.get("jobs", [])
    stats = data.get("stats", {})
    apply = [j for j in jobs if (j.get("score") or 0) >= 4]
    maybe = ([j for j in jobs if (j.get("score") or 0) == 3]
             + [j for j in jobs if j.get("score") is None])
    screened = [j for j in jobs if (j.get("score") or 0) in (1, 2)]
    picks = {a["url"] for a in data.get("ai_picks", [])}
    articles = data.get("ai_picks", []) + [
        a for a in data.get("ai_articles", []) if a["url"] not in picks][:12]

    inplay = [r for r in TRACKER["rows"]
              if r.get("status") in ("Applied", "Heard back", "Interview",
                                     "Offer")]

    # Tabs + panels, empty sections dropped (tab and panel together).
    sections = [
        ("apply", "Apply-worthy",
         "The seats that clear the bar tonight. Start at the top and work down.",
         [job_row(j, i + 1) for i, j in enumerate(apply)]),
        ("inplay", "In play",
         "Every live application, tracked automatically - applies, replies "
         "and meetings detected from email, calendar and LinkedIn.",
         [inplay_row(r, i + 1) for i, r in enumerate(inplay)]),
        ("maybe", "Worth a look",
         "Real mandates with one thing to verify before you spend an evening on them.",
         [job_row(j, i + 1) for i, j in enumerate(maybe)]),
        ("screened", "Screened out, for the record",
         "Read, rated and set aside — so you know nothing slipped past.",
         [job_row(j, i + 1, with_prompt=False) for i, j in enumerate(screened)]),
        ("reading", "AI for the workplace",
         "Pieces to turn into interview talking points.",
         [article_row(a) for a in articles]),
        ("recruiters", "Recruiter watch — Atlantic Canada",
         "The firms Vern checks every night on your behalf.",
         [f'<article class="job"><div class="rail"><div class="no">{i + 1:02d}'
          f'</div></div><div class="body"><h4><a href="{esc(u)}" '
          f'target="_blank" rel="noopener">{esc(n)}</a></h4>'
          f'<div class="meta">{esc(where)}</div>'
          f'<p class="summary">Finance postings from this firm appear in the '
          f'job sections automatically when they match.</p></div></article>'
          for i, (n, where, u) in enumerate(FIRMS)]),
    ]
    titles = {"apply": "Apply-worthy", "inplay": "In play",
              "maybe": "Worth a look", "screened": "Screened out",
              "reading": "Reading list", "recruiters": "Recruiter watch"}
    present = [(pid, title, lede, rows) for pid, title, lede, rows in sections
               if rows]
    tabs, panels = [], []
    for i, (pid, title, lede, rows) in enumerate(present):
        tabs.append(
            f'<button class="tab{" active" if i == 0 else ""}" '
            f'data-tab="{pid}"><span class="ix">{ROMAN[i]}</span>'
            f'{titles[pid]}<span class="n">{len(rows)}</span></button>')
        panels.append(_panel(pid, i, title, lede, "".join(rows), active=(i == 0)))

    # Tonight in one minute (shared with the email via curated_data digest).
    digest_rows = "".join(
        f'<div class="row"><div class="k">{esc(d["label"])}</div>'
        f'<div class="v">{esc(d["value"])}</div></div>'
        for d in data.get("digest", []))

    # Top pick.
    joke_html = ""
    if data.get("dad_joke"):
        joke_html = f'''
<div class="groaner">
  <div class="eyebrow">The daily groaner</div>
  <p>{esc(data["dad_joke"])}</p>
</div>'''

    top_html = ""
    top = next(iter(apply), None)
    if top:
        meta = " · ".join(b for b in (top.get("company"), top.get("location"),
                                      top.get("source")) if b)
        watch = esc(top.get("watch_out") or "Nothing tonight - read it in full and decide.")
        top_html = f'''
<div class="wrap">
  <div class="pick">
    <div class="main">
      <div class="eyebrow">Tonight's top pick</div>
      <h2><a href="{esc(top.get("url", ""))}" target="_blank" rel="noopener">{esc(top.get("title", ""))}</a></h2>
      <div class="meta">{esc(meta)}</div>
      <p>{esc(top.get("why") or top.get("summary") or "")}</p>
      <a class="go" href="{esc(top.get("url", ""))}" target="_blank" rel="noopener">Read the posting <span>&rarr;</span></a>
    </div>
    <div class="side">
      <div><div class="k">Vern's score</div><div class="stars">{stars_html(top.get("score"))}</div></div>
      <div><div class="k">Region</div><div class="region">{esc(region_label(top) or "—")}</div></div>
      <div><div class="k">Watch out</div><p>{watch}</p></div>
    </div>
  </div>
</div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>The Next Chapter — {esc(date_short)}</title>
<link href="{FONTS}" rel="stylesheet">
<style>{INDEX_CSS}</style>
</head>
<body>

<header class="cover">
  <div class="cover-in">
    <div class="eyebrow">Evening Edition &nbsp;·&nbsp; {esc(date_long)} &nbsp;·&nbsp; Atlantic Time</div>
    <h1>The Next Chapter</h1>
    <div class="tagline">A nightly field report from Vern, your scout</div>
    <div class="stats">
      <span>{stats.get("postings_read", 0)} postings read</span><span class="dot"></span>
      <span>{stats.get("apply", 0)} apply-worthy</span><span class="dot"></span>
      <span>{stats.get("home", 0)} in Nova Scotia</span>
    </div>
  </div>
</header>

{joke_html}
<div class="intro">
  <aside class="digest">
    <div class="eyebrow" style="margin-bottom:16px">Tonight in one minute</div>
    {digest_rows}
  </aside>
</div>

<div class="rule"><i></i><b></b><i></i></div>
{top_html}

<nav class="tabbar">
  <div class="tabbar-in" id="tabs">
    {"".join(tabs)}
  </div>
</nav>

<main class="wrap">
{"".join(panels)}
</main>
{FOOTER}
{nc_cfg()}
{INDEX_SCRIPTS}
</body>
</html>'''


def build_archive() -> None:
    editions = sorted(EDITIONS.glob("*.html"), reverse=True)
    rows = "".join(
        f'<article class="job"><div class="rail"><div class="no">'
        f'{datetime.date.fromisoformat(e.stem).strftime("%b %-d")}</div></div>'
        f'<div class="body"><h4><a href="./editions/{e.name}">'
        f'{datetime.date.fromisoformat(e.stem).strftime("%A, %B %-d, %Y")}'
        f'</a></h4></div></article>'
        for e in editions if _is_date(e.stem))
    body = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>The Archive — The Next Chapter</title>
<link href="{FONTS}" rel="stylesheet">
<style>{INDEX_CSS}
main.wrap{{padding-top:36px}}
.job{{grid-template-columns:112px minmax(0,1fr)}}
.job .no{{font-size:14px}}
.job h4 a{{font-size:26px}}</style></head>
<body>
<header class="cover">
  <div class="cover-in">
    <div class="eyebrow">The Next Chapter</div>
    <h1>The Archive</h1>
    <div class="tagline">Every edition, newest first</div>
  </div>
</header>
<main class="wrap">
  <div class="list" style="margin-top:30px">{rows or
    '<article class="job"><div class="body"><p class="summary">Nothing yet.</p></div></article>'}</div>
</main>
{FOOTER}
</body></html>'''
    (DOCS / "archive.html").write_text(body, encoding="utf-8")


def _is_date(stem: str) -> bool:
    try:
        datetime.date.fromisoformat(stem)
        return True
    except ValueError:
        return False


def update_grove(data: dict, now: datetime.datetime) -> None:
    """Append today's items to the cumulative grove store (shape unchanged)."""
    grove = {"jobs": [], "articles": []}
    if GROVE_JSON.exists():
        grove = json.loads(GROVE_JSON.read_text(encoding="utf-8"))
    seen_jobs = {g.get("url") for g in grove["jobs"]}
    seen_articles = {g.get("url") for g in grove["articles"]}
    date = now.strftime("%Y-%m-%d")
    for j in data.get("jobs", []):
        if j.get("url") in seen_jobs:
            continue
        grove["jobs"].append({
            "date": date, "title": j.get("title"), "company": j.get("company"),
            "location": j.get("location"), "url": j.get("url"),
            "source": j.get("source"), "salary": j.get("salary"),
            "tier": TIER_LABELS.get(j.get("tier"), ""),
            "score": j.get("score"), "summary": j.get("summary"),
            "why": j.get("why"), "watch_out": j.get("watch_out"),
            "kickoff_prompt": j.get("kickoff_prompt"),
            "attachments": j.get("attachments") or [],
            "wildcard": bool(j.get("wildcard")),
        })
    for a in (data.get("ai_picks", []) + data.get("ai_articles", [])
              + data.get("ns_articles", [])):
        if a.get("url") in seen_articles:
            continue
        seen_articles.add(a["url"])
        grove["articles"].append({
            "date": date, "title": a.get("title"), "feed": a.get("feed"),
            "url": a.get("url"), "note": a.get("note", "")})
    GROVE_JSON.write_text(json.dumps(grove, indent=1, ensure_ascii=False),
                          encoding="utf-8")


def build_grove_page() -> None:
    """The Grove - template applied verbatim except the __NC_CFG__ token,
    which receives the webhook/CSV config (empty strings = features off)."""
    template = (Path(__file__).parent / "templates" / "grove.html")
    cfg = {"webhook": os.environ.get("SHEET_WEBHOOK_URL") or "",
           "token": os.environ.get("SHEET_TOKEN") or "",
           "csv": os.environ.get("SHEET_CSV_URL") or ""}
    html_text = template.read_text(encoding="utf-8").replace(
        "__NC_CFG__", json.dumps(cfg))
    (DOCS / "grove.html").write_text(html_text, encoding="utf-8")


def main() -> None:
    load_tracker()
    data = json.loads(CURATED_FILE.read_text(encoding="utf-8"))
    now = datetime.datetime.now(HALIFAX)
    DOCS.mkdir(exist_ok=True)
    EDITIONS.mkdir(exist_ok=True)

    page = build_edition(data, now)
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (EDITIONS / f"{now:%Y-%m-%d}.html").write_text(page, encoding="utf-8")
    update_grove(data, now)
    build_archive()
    build_grove_page()
    print(f"[webpage] wrote docs/index.html, editions/{now:%Y-%m-%d}.html, "
          f"archive.html, grove.html (+ grove.json)")


if __name__ == "__main__":
    main()

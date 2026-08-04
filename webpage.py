"""Build the full web edition for GitHub Pages (pattern: the Curated
Canopy's webpage.py + grove builder).

Outputs (all committed; Pages serves /docs on main):
    docs/index.html          today's full edition - every job with collapsible
                             "Start here" prompt + "Reach out" details, AI
                             alignment summaries, recruiter watch, the full
                             reading list, NS radar
    docs/editions/<date>.html  permanent copy
    docs/archive.html        browsable index of past editions
    docs/grove.json          cumulative store of everything ever featured
    docs/grove.html          "The Grove" - searchable archive of all content

Usage:  python webpage.py   (after curate.py)
"""
from __future__ import annotations

import datetime
import html
import json
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
CURATED_FILE = HERE / "curated_data.json"
DOCS = HERE / "docs"
EDITIONS = DOCS / "editions"
GROVE_JSON = DOCS / "grove.json"
HALIFAX = ZoneInfo("America/Halifax")

TIER_LABELS = {1: "Nova Scotia", 2: "Eastern Canada", 3: "Remote",
               4: "Northeast US"}

# Botanical Editorial - shared design language with the Curated Canopy
# (Newsletter/design/tokens.css): stone paper, forest ink, moss, terracotta.
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
:root{--paper:#F4EEE2;--paper-deep:#E9E1D1;--surface:#FBF7EE;--ink:#20271F;
--ink-soft:#4A4A3E;--ink-mute:#7C7565;--forest:#2C3A2B;--moss:#6E7B4B;
--moss-deep:#55603A;--clay:#A85A36;--clay-deep:#8E4A2C;--line:#D9CFBC;
--line-soft:#E5DCCB;--serif:'Newsreader',Georgia,'Times New Roman',serif;
--sans:'Hanken Grotesk',-apple-system,'Segoe UI',sans-serif;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper-deep);color:var(--ink);
font-family:var(--sans);line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:780px;margin:0 auto;padding:0 0 70px}
.frame{background:var(--paper);border-left:1px solid var(--line-soft);
border-right:1px solid var(--line-soft);padding:0 30px 40px;min-height:100vh}
.masthead{text-align:center;padding:46px 0 26px}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.22em;
text-transform:uppercase;color:var(--moss-deep);font-family:var(--sans)}
h1{font-family:var(--serif);font-weight:500;font-size:42px;line-height:1.05;
letter-spacing:-.01em;color:var(--forest);margin:14px 0 0}
.tagline{font-family:var(--serif);font-style:italic;font-size:16px;
color:var(--ink-soft);margin-top:10px}
.date{margin-top:20px;font-size:11.5px;letter-spacing:.16em;
text-transform:uppercase;color:var(--ink-mute)}
nav{margin:16px 0 0;font-size:12px;letter-spacing:.1em;
text-transform:uppercase;text-align:center}
nav a{color:var(--clay-deep);text-decoration:none;margin:0 10px;
font-weight:600}
nav a:hover{color:var(--clay)}
.note{background:var(--surface);border-top:1px solid var(--line-soft);
border-bottom:1px solid var(--line-soft);padding:26px 24px;margin-top:22px;
display:flex;gap:18px;align-items:flex-start;border-radius:2px}
.monogram{flex-shrink:0;width:46px;height:46px;border-radius:50%;
border:1px solid var(--moss);color:var(--moss-deep);
font-family:var(--serif);font-size:22px;display:flex;align-items:center;
justify-content:center;margin-top:2px}
.note .body{font-family:var(--serif);font-size:17px;line-height:1.65;
color:var(--ink)}
.note .sig{color:var(--ink-mute);font-size:13px;margin-top:8px;
font-family:var(--serif);font-style:italic}
section{background:var(--surface);border:1px solid var(--line-soft);
border-radius:12px;margin-top:26px;padding:6px 0 2px;overflow:hidden;
box-shadow:0 1px 2px rgba(32,39,31,.04),0 12px 32px -16px rgba(32,39,31,.18)}
section>h2{font-size:11px;font-weight:600;letter-spacing:.2em;
color:var(--moss-deep);text-transform:uppercase;margin:14px 20px 10px}
.job,.item{padding:16px 20px;border-top:1px solid var(--line-soft)}
.stars{color:var(--clay);font-size:14px;letter-spacing:2px}
.chip{background:#EDE7D8;color:var(--moss-deep);font-size:11px;
padding:2px 10px;border-radius:100px;vertical-align:2px;margin-left:6px;
letter-spacing:.04em}
.job a.title{font-family:var(--serif);color:var(--forest);font-size:19px;
font-weight:600;text-decoration:none;display:inline-block;margin-top:3px}
.job a.title:hover{color:var(--clay-deep)}
.meta{color:var(--ink-mute);font-size:13px;margin-top:3px}
.summary{margin-top:8px;font-family:var(--serif);font-size:15.5px;
color:var(--ink-soft);line-height:1.6}
.why{margin-top:5px;font-size:14px;color:var(--ink-soft)}
.watch{margin-top:5px;color:var(--ink-mute);font-style:italic;font-size:13px;
font-family:var(--serif)}
details{margin-top:10px;border:1px solid var(--line);border-radius:8px;
background:var(--paper)}
details summary{cursor:pointer;padding:8px 14px;font-size:12px;
letter-spacing:.08em;text-transform:uppercase;color:var(--clay-deep);
font-weight:600}
details summary:hover{color:var(--clay)}
details[open] summary{border-bottom:1px solid var(--line-soft)}
details .inner{padding:12px 14px}
pre.prompt{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;
white-space:pre-wrap;margin:0;line-height:1.55;color:var(--ink-soft)}
.copyhint{color:var(--ink-mute);font-size:11px;margin-top:8px}
.contact{font-size:14px;color:var(--ink-soft)}
.contact a{color:var(--clay-deep)}
footer{margin-top:34px;color:var(--ink-mute);font-size:12px;
text-align:center;border-top:1px solid var(--line-soft);padding-top:18px}
footer a{color:var(--clay-deep)}
input.search{width:100%;padding:12px 16px;font-size:17px;border:1px solid
var(--line);border-radius:10px;font-family:var(--serif);margin:18px 0 4px;
background:var(--surface);color:var(--ink)}
input.search:focus{outline:2px solid var(--moss);border-color:var(--moss)}
.count{color:var(--ink-mute);font-size:13px;margin:6px 0 10px}
@media(max-width:520px){h1{font-size:30px}.frame{padding:0 14px 30px}
.note{padding:18px 14px;gap:12px}}
"""


def esc(t: str) -> str:
    return html.escape(t or "", quote=True)


def stars_html(score) -> str:
    if not score:
        return ""
    return f'<span class="stars">{"★" * score}{"☆" * (5 - score)}</span>'


def chips(job: dict) -> str:
    out = ""
    label = TIER_LABELS.get(job.get("tier"))
    if label:
        out += f'<span class="chip">{esc(label)}</span>'
    if job.get("wildcard"):
        out += '<span class="chip">left field</span>'
    return out


def job_card(job: dict) -> str:
    meta = " · ".join(b for b in (job.get("company"), job.get("location"),
                                  job.get("salary"), job.get("source")) if b)
    parts = [f'<div class="job">',
             f'<div>{stars_html(job.get("score"))}{chips(job)}</div>',
             f'<a class="title" href="{esc(job.get("url", ""))}" '
             f'target="_blank" rel="noopener">{esc(job.get("title", "?"))}</a>',
             f'<div class="meta">{esc(meta)}</div>']
    if job.get("summary"):
        parts.append(f'<div class="summary">{esc(job["summary"])}</div>')
    if job.get("why"):
        parts.append(f'<div class="why"><b>Why:</b> {esc(job["why"])}</div>')
    if job.get("watch_out"):
        parts.append(f'<div class="watch">Watch out: {esc(job["watch_out"])}</div>')
    contacts = job.get("contacts") or []
    if contacts:
        rows = "".join(
            f'<div class="contact">{esc(c.get("name", ""))}'
            f'{", " + esc(c.get("title", "")) if c.get("title") else ""}'
            + (f' — <a href="{esc(c.get("url", ""))}" target="_blank" '
               f'rel="noopener">LinkedIn profile</a>' if c.get("url") else "")
            + '</div>'
            for c in contacts)
        parts.append(f'''<details><summary>Reach out ({len(contacts)})</summary>
<div class="inner">{rows}
<div class="copyhint">Ask Vern in your Claude Project to draft the connection
note or InMail.</div></div></details>''')
    if job.get("kickoff_prompt"):
        parts.append(f'''<details><summary>Start here — Claude Project prompt</summary>
<div class="inner"><pre class="prompt">{esc(job["kickoff_prompt"])}</pre>
<div class="copyhint">Copy this into a new chat in the "Next Chapter HQ"
Claude Project, then paste the posting text underneath.</div></div></details>''')
    parts.append("</div>")
    return "\n".join(parts)


def _page(title: str, body: str, nav_extra: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body><div class="wrap"><div class="frame">
{body}
<footer>Grown nightly by Vern, your scout in the canopy.<br>
<a href="./index.html">Today</a> · <a href="./archive.html">The Archive</a>
· <a href="./grove.html">The Grove</a>{nav_extra}</footer>
</div></div></body></html>"""


def build_edition(data: dict, now: datetime.datetime) -> str:
    date_line = now.strftime("%A, %B %-d, %Y")
    jobs = data.get("jobs", [])
    top = [j for j in jobs if (j.get("score") or 0) >= 4]
    worth = [j for j in jobs if (j.get("score") or 0) == 3]
    low = [j for j in jobs if (j.get("score") or 0) in (1, 2)]
    unscored = [j for j in jobs if j.get("score") is None]
    wild = [j for j in jobs if j.get("wildcard") and (j.get("score") or 0) >= 3]

    sections = []
    if top:
        sections.append("<section><h2>Apply-worthy</h2>"
                        + "".join(job_card(j) for j in top) + "</section>")
    if worth:
        sections.append("<section><h2>Worth a look</h2>"
                        + "".join(job_card(j) for j in worth) + "</section>")
    if wild:
        extra = [j for j in wild if j not in top and j not in worth]
        if extra:
            sections.append("<section><h2>Left field</h2>"
                            + "".join(job_card(j) for j in extra) + "</section>")
    if unscored:
        sections.append("<section><h2>New postings (unscored)</h2>"
                        + "".join(job_card(j) for j in unscored) + "</section>")
    if low:
        rows = "".join(job_card(j) for j in low)
        sections.append(f"<section><h2>Screened out (for the record)</h2>"
                        f"<details style='margin:0 18px 14px'><summary>"
                        f"{len(low)} low-rated posting(s)</summary>"
                        f"<div class='inner'>{rows}</div></details></section>")

    # Recruiter watch - the standing five + Meridia.
    firms = [
        ("Meridia Recruitment (KBRS)", "https://meridiarecruitment.ca/career-opportunities/careers"),
        ("Venor", "https://venor.ca/opportunities"),
        ("Summit Search Group", "https://www.summitsearchgroup.com/opportunities/"),
        ("Macdonald Search Group", "https://macdonaldsearchgroup.com/job-listings"),
        ("Lock Search Group", "https://locksearchgroup.com/opportunities/"),
        ("Accountant Staffing", "https://www.accountantstaffing.com/job-opportunities"),
    ]
    firm_rows = "".join(
        f'<div class="item"><a class="title" style="font-size:15px" '
        f'href="{esc(u)}" target="_blank" rel="noopener">{esc(n)}</a>'
        f'<div class="meta">Finance postings from this firm appear in the job '
        f'sections automatically when they match.</div></div>'
        for n, u in firms)
    sections.append("<section><h2>Recruiter watch - Atlantic Canada</h2>"
                    + firm_rows + "</section>")

    # Full reading list (email carries only the picks).
    picks = {a["url"] for a in data.get("ai_picks", [])}
    articles = data.get("ai_picks", []) + [
        a for a in data.get("ai_articles", []) if a["url"] not in picks][:12]
    if articles:
        rows = "".join(
            f'<div class="item"><a class="title" style="font-size:15px" '
            f'href="{esc(a["url"])}" target="_blank" rel="noopener">'
            f'{esc(a["title"])}</a>'
            f'{"<span class=chip>Vern&#39;s pick</span>" if a["url"] in picks else ""}'
            f'<div class="meta">{esc(a.get("feed", ""))}</div>'
            + (f'<div class="summary" style="font-size:14px">{esc(a["note"])}</div>'
               if a.get("note") else "")
            + '</div>'
            for a in articles)
        sections.append("<section><h2>AI for the workplace - full reading list"
                        "</h2>" + rows + "</section>")

    if data.get("ns_articles"):
        rows = "".join(
            f'<div class="item"><a class="title" style="font-size:15px" '
            f'href="{esc(a["url"])}" target="_blank" rel="noopener">'
            f'{esc(a["title"])}</a>'
            f'<div class="meta">{esc(a.get("feed", ""))}</div></div>'
            for a in data["ns_articles"][:10])
        sections.append("<section><h2>Nova Scotia radar - who is growing, who "
                        "hires next</h2>" + rows + "</section>")

    note = data.get("encouragement") or "Today's full scan is below."
    body = f"""
<div class="masthead">
<div class="eyebrow">The Next Chapter</div>
<h1>Evening Edition</h1>
<div class="tagline">a nightly field report from Vern, your scout</div>
<div class="date">{date_line} · Atlantic Time</div>
<nav><a href="./archive.html">The Archive</a>
<a href="./grove.html">The Grove</a></nav>
</div>
<div class="note"><div class="monogram">V</div>
<div><div class="eyebrow" style="margin-bottom:6px">A note from Vern</div>
<div class="body">{esc(note)}</div>
<div class="sig">Yours, Vern</div></div></div>
{"".join(sections)}"""
    return _page(f"The Next Chapter - {date_line}", body)


def build_archive() -> None:
    editions = sorted(EDITIONS.glob("*.html"), reverse=True)
    rows = "".join(
        f'<div class="item"><a class="title" style="font-size:15px" '
        f'href="./editions/{e.name}">'
        f'{datetime.date.fromisoformat(e.stem).strftime("%A, %B %-d, %Y")}'
        f'</a></div>'
        for e in editions if _is_date(e.stem))
    body = f"""
<div class="masthead">
<div class="eyebrow">The Next Chapter</div>
<h1>The Archive</h1>
<div class="tagline">every edition, newest first</div>
</div>
<section><h2>Editions</h2>{rows or '<div class="item">Nothing yet.</div>'}</section>"""
    (DOCS / "archive.html").write_text(_page("The Archive", body),
                                       encoding="utf-8")


def _is_date(stem: str) -> bool:
    try:
        datetime.date.fromisoformat(stem)
        return True
    except ValueError:
        return False


def update_grove(data: dict, now: datetime.datetime) -> None:
    """Append today's items to the cumulative grove store."""
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


GROVE_JS = """
const fmt = s => (s||'');
fetch('./grove.json',{cache:'no-cache'}).then(r=>r.json()).then(d=>{
  const jobs=d.jobs||[], arts=d.articles||[];
  const box=document.getElementById('results');
  const count=document.getElementById('count');
  const input=document.getElementById('q');
  function starTxt(n){return n?'★'.repeat(n)+'☆'.repeat(5-n):'';}
  function render(q){
    q=(q||'').toLowerCase();
    const match=o=>!q||Object.values(o).join(' ').toLowerCase().includes(q);
    const J=jobs.filter(match).reverse(), A=arts.filter(match).reverse();
    count.textContent=J.length+' job(s), '+A.length+' article(s)'+(q?' matching "'+q+'"':' in The Grove');
    let h='';
    if(J.length){h+='<section><h2>Jobs</h2>'+J.map(j=>
      '<div class="job"><div><span class="stars">'+starTxt(j.score)+'</span>'
      +(j.tier?'<span class="chip">'+fmt(j.tier)+'</span>':'')
      +(j.wildcard?'<span class="chip">left field</span>':'')
      +'<span class="chip">'+fmt(j.date)+'</span></div>'
      +'<a class="title" target="_blank" rel="noopener" href="'+fmt(j.url)+'">'+fmt(j.title)+'</a>'
      +'<div class="meta">'+[j.company,j.location,j.salary,j.source].filter(Boolean).join(' · ')+'</div>'
      +(j.summary?'<div class="summary">'+fmt(j.summary)+'</div>':'')
      +(j.why?'<div class="why"><b>Why:</b> '+fmt(j.why)+'</div>':'')
      +(j.kickoff_prompt?'<details><summary>Start here — Claude Project prompt</summary><div class="inner"><pre class="prompt">'+fmt(j.kickoff_prompt)+'</pre></div></details>':'')
      +'</div>').join('')+'</section>';}
    if(A.length){h+='<section><h2>Articles</h2>'+A.map(a=>
      '<div class="item"><span class="chip">'+fmt(a.date)+'</span> '
      +'<a class="title" style="font-size:15px" target="_blank" rel="noopener" href="'+fmt(a.url)+'">'+fmt(a.title)+'</a>'
      +'<div class="meta">'+fmt(a.feed)+'</div>'
      +(a.note?'<div class="summary" style="font-size:14px">'+fmt(a.note)+'</div>':'')
      +'</div>').join('')+'</section>';}
    box.innerHTML=h||'<section><div class="item">Nothing matches.</div></section>';
  }
  render('');
  input.addEventListener('input',e=>render(e.target.value));
});
"""


def build_grove_page() -> None:
    body = f"""
<div class="masthead">
<div class="eyebrow">The Next Chapter</div>
<h1>The Grove</h1>
<div class="tagline">everything that has ever appeared in an edition -
every job, prompt, and article</div>
</div>
<input class="search" id="q" type="search"
       placeholder="Search jobs, companies, articles... (e.g. Halifax, PE, Irving)">
<div class="count" id="count"></div>
<div id="results"></div>
<script>{GROVE_JS}</script>"""
    (DOCS / "grove.html").write_text(_page("The Grove", body),
                                     encoding="utf-8")


def main() -> None:
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

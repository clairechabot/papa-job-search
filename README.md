# The Next Chapter — job-search automation for Papa

A twice-daily email newsletter that scans the Atlantic Canada market for
senior finance roles (CFO / VP Finance / Director of Finance), scores each
posting against his profile with Claude, and delivers it with an
"AI for the workplace" reading section, follow-up nudges, and a Sunday
networking radar. Plus an on-demand interview-prep brief, and a Claude
Project package (`claude-project/`) that gives him a personal career coach
on claude.ai.

```
fetch.py  ──►  curate.py  ──►  render.py ──► email (SMTP, Gmail)
   │            (Claude)           └─► editions/YYYY-MM-DD-*.html (archive)
   └─ scrapes job boards + RSS, dedups vs history.json
```

- **fetch.py** — pulls every source (Job Bank, Meridia/KBRS, CareerBeacon,
  Adzuna, AI + NS-business RSS), dedups against `history.json` (same job on
  two boards counts once), writes `fetched_data.json`. A broken source
  degrades gracefully — the edition footer reports it.
- **curate.py** — free regex gate (senior finance titles, Atlantic/remote)
  then Claude scores each survivor 1–5 against `profile/candidate.md` with a
  "why it fits" + "watch out" per job, picks 2–3 AI-for-work articles with a
  what-it-means-for-a-CFO note, and writes the day's encouragement. Runs
  without an API key in gate-only mode (no scores).
- **render.py** — email-client-safe HTML, sends via Gmail SMTP, archives to
  `editions/`, then marks jobs seen. `ALLOW_NO_EMAIL=1` for previews.
- **interview_brief.py** — on-demand company one-pager before an interview
  (also a manual GitHub Action).

## Editions

| When (Atlantic) | Content |
|---|---|
| Morning ~07:00 | New jobs, scored + explained; AI-for-work pick; encouragement; follow-up nudges |
| Evening ~19:00 | Same scan (anything new since morning) |
| Sunday evening | + "Nova Scotia radar": business headlines worth a networking note |

## Running locally

```bash
pip install -r requirements.txt
python fetch.py                       # scrape sources
CLAUDE_API_KEY=sk-... python curate.py
ALLOW_NO_EMAIL=1 python render.py     # writes newsletter.html, no send
```

## Setup

See [SETUP.md](SETUP.md) — GitHub secrets, Gmail app password, and the
10-minute Claude Project setup for the career-coach side lives in
[claude-project/SETUP.md](claude-project/SETUP.md).

## Credits

Architecture forked from the Curated Canopy newsletter (fetcher → Claude
curator → renderer → SMTP, history dedup, Atlantic-time cron compensation)
with scraper/gate/scoring patterns from the Ellipsis Athena sourcing platform.

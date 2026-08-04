# The Next Chapter — Vern, the job-search scout

A once-daily evening email from **Vern** that scans the market twice a day
for senior finance roles across four location tiers (Nova Scotia first,
then eastern Canada, remote Canada/US, northeast US), scores every posting
against Marcel's profile with Claude, and links to a full web edition on
GitHub Pages — every job with an AI alignment summary, a collapsible
"Start here" Claude-Project prompt, hiring-team contacts to reach out to,
the recruiter watch, the AI-for-the-workplace reading list, and a
searchable everything-archive (The Grove). `claude-project/` carries the
matching career-coach package (also Vern) for claude.ai.

```
morning:  fetch --scan-only ──► pending_jobs.json          (silent, committed)
~5pm VM:  linkedin_authenticated.py ──► + hiring contacts   (self-hosted runner)
evening:  fetch ──► curate (Vern/Claude) ──► webpage.py ──► docs/ (Pages)
                                       └──► render.py  ──► ONE email (SMTP)
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

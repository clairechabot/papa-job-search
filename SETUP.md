# Setup — one evening, start to finish

## 1. Secrets — the exact list

Repo → **Settings → Secrets and variables → Actions**.

### Secrets tab

| Secret | Value | Required? |
|---|---|---|
| `SMTP_USER` | the Gmail address the newsletter sends FROM (yours) | yes |
| `SMTP_PASS` | 16-char Gmail app password for that account (Google Account → Security → 2-Step Verification → App passwords → create "Vern newsletter") | yes |
| `EMAIL_TO` | `marcel.e.chabot@gmail.com` — comma-add yourself to shadow what he gets | yes |
| `RECIPIENT_NAME` | `Marcel` | no (default Marcel) |
| `CLAUDE_API_KEY` | Anthropic API key (console.anthropic.com). **Rotate the one you pasted in chat after setup.** | yes (else gate-only, no scores) |
| `CANDIDATE_PROFILE` | the FULL private profile markdown (Claire has the file: `PRIVATE-candidate-profile.md`) — overrides the committed, salary-scrubbed `profile/candidate.md` | strongly recommended (public repo) |
| `ADZUNA_APP_ID` | free at developer.adzuna.com | optional |
| `ADZUNA_APP_KEY` | 〃 | optional |

### Variables tab (not secret)

| Variable | Value |
|---|---|
| `CLAUDE_MODEL` | optional; defaults to `claude-opus-5` (cents/day at this volume) |
| `EDITION_URL` | `https://clairechabot.github.io/papa-job-search` (after step 2) |

## 2. GitHub Pages (the full edition / Archive / Grove)

Settings → **Pages** → Source: "Deploy from a branch" → Branch `main`,
folder `/docs` → Save. The site appears at
`https://clairechabot.github.io/papa-job-search/` after the first evening
run commits `docs/`.

## 3. Fill in the private pieces

- Upload the four knowledge files + `voice-sample.md` to the Claude Project
  (see `claude-project/SETUP.md`) — use the PRIVATE filled versions Claire
  received, not the committed templates.
- Add the `CANDIDATE_PROFILE` secret (paste the private profile file).
- Because this repo is **public**: never commit his phone/email, exact
  salary floors, or the private knowledge copies. `applications.json` is
  also public — keep entries to company/role/date, nothing sensitive.

## 4. Test run

Actions → **Morning Scan (silent)** → Run workflow (banks jobs, no email).
Then Actions → **Evening Edition** → Run workflow. Check the email arrives
and the Pages site renders.

## 5. The VM layer (LinkedIn + hiring contacts)

See **VM-SETUP.md** — ~$5/month, unlocks authenticated LinkedIn results and
the "Reach out" contact lines, plus a menu of other upgrades the same VM
can host.

## 6. Interview briefs

Actions → **Interview Brief** → Run workflow → company name. A one-page
prep brief lands in the inbox in ~2 minutes.

## Daily rhythm (what Marcel experiences)

- ~6:00 AM Montreal: silent scan banks the morning's postings
- ~4:55 PM: VM LinkedIn scan adds contacts (if the VM is set up)
- **6:30 PM Montreal**: ONE email from Vern — top jobs scored and
  explained, "Start here" prompts, reach-out contacts, AI reading —
  linking to the full edition, Archive, and Grove on the web. (The
  workflow fires at 5:55 PM local, year-round via a DST guard; GitHub's
  cron jitter + the pipeline itself land it around 6:15-6:30.)

## Troubleshooting

- **No email** — Actions tab → open the failed Evening Edition run.
  `SMTP_PASS` errors = app password wrong/revoked.
- **A source shows "unavailable" in the footer** — bot-walls come and go;
  the proxy fallback usually recovers. Persistent = tweak that scraper.
- **LinkedIn scan says session EXPIRED** — re-run `linkedin_auth.py`
  locally, `scp` the file to the VM (VM-SETUP.md §3).
- **Scores feel off** — sharpen the `CANDIDATE_PROFILE` secret; the
  dealbreakers and strong-fits sections steer Vern the most.

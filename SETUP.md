# Setup — one evening, start to finish

## 1. Create the GitHub repo

Private repo (any name). Push this code to its default branch. Scheduled
workflows run from the default branch.

## 2. Gmail app password (for sending)

1. Google Account → Security → 2-Step Verification (must be on)
2. Security → App passwords → create one named "job newsletter"
3. Copy the 16-character password

## 3. Repository secrets

GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `SMTP_USER` | your Gmail address (the sender) |
| `SMTP_PASS` | the app password from step 2 |
| `EMAIL_TO` | recipients, comma-separated. Start with just yourself for a trial week, then add your dad |
| `RECIPIENT_NAME` | greeting name (e.g. `Papa`) |
| `CLAUDE_API_KEY` | Anthropic API key (console.anthropic.com) — powers scoring, article picks, encouragement, interview briefs |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | optional; free at developer.adzuna.com — adds an aggregator that catches Indeed-only postings |

Optional repo **variable** (Settings → Variables): `CLAUDE_MODEL` — defaults
to `claude-opus-5` (best judgment). Set `claude-sonnet-5` or
`claude-haiku-4-5` to cut cost; scoring runs twice daily on a handful of
jobs, so even Opus is only cents per day.

## 4. Fill in the profile

Edit `profile/candidate.md` with your dad (30 minutes together, worth it —
scoring quality tracks profile quality). Then commit.

## 5. Test run

Actions tab → "Morning Edition" → Run workflow. Check the email arrives and
the jobs make sense. The run also commits `history.json` back, so the next
edition only carries new postings.

## 6. Interview briefs

Actions tab → "Interview Brief" → Run workflow → enter the company name.
A one-page prep brief lands in the inbox in ~2 minutes.

## 7. The application tracker

`applications.json` — add a record when he applies somewhere (or paste the
posting into his Claude Project and ask it to draft the entry). Any
application still `applied`/`waiting` after 7 days gets a follow-up nudge in
the newsletter footer.

## Troubleshooting

- **No email arrived** — Actions tab → open the failed run. `SMTP_PASS`
  errors mean the app password is wrong/revoked. Gmail caps ~500 sends/day
  (we use 2).
- **A source shows "unavailable" in the footer** — job boards bot-wall
  datacenter IPs sometimes; the proxy fallback usually recovers within a
  run or two. Persistent failures: open an issue to tweak that scraper.
- **Same job appeared twice** — cross-board dedup is by normalized
  company+title; boards that hide the employer (CareerBeacon) defeat it
  occasionally. Harmless.
- **Scores feel off** — sharpen `profile/candidate.md` (dealbreakers and
  strong-fits sections steer the model most).

# VM setup — the authenticated LinkedIn layer (and what else the VM can do)

The main newsletter runs entirely on GitHub's free runners. This VM adds the
one thing those runners can't do: **logged-in LinkedIn scraping** — richer
job results, posted salaries, and the "Meet the hiring team" contacts that
power the Reach-out lines. Budget ~$5/month.

## 1. Rent the VM

Any small Ubuntu 22.04+ box: Hetzner CX22 (~€4), DigitalOcean Basic ($6),
or GCP e2-small. 1 vCPU / 2GB RAM is plenty. SSH in.

```bash
sudo apt update && sudo apt install -y python3-pip git
pip3 install playwright && python3 -m playwright install chromium --with-deps
```

## 2. Register it as a GitHub Actions self-hosted runner

Repo → **Settings → Actions → Runners → New self-hosted runner** (Linux x64).
GitHub shows a download + configure block — paste it on the VM. When
`config.sh` asks:

- **labels**: add `linkedin` (this is how `linkedin_scan.yml` targets it)
- everything else: defaults are fine

Then install it as an always-on service:

```bash
sudo ./svc.sh install && sudo ./svc.sh start
```

The runner shows "Idle" on the Settings → Runners page when it's connected.

> Security note for a public repo: GitHub does not run workflows from fork
> PRs on self-hosted runners without your approval, and first-time
> contributors need approval to run any workflow. Keep those defaults
> (Settings → Actions → General → "Require approval for all external
> contributors").

## 3. Give it the LinkedIn session

On **your own computer** (not the VM):

```bash
pip install playwright && playwright install chromium
python linkedin_auth.py        # browser opens; log in; press Enter
scp linkedin-auth.json <user>@<vm-ip>:~/.config/linkedin-auth.json
```

Use Marcel's LinkedIn account (the hiring-team visibility follows his
network). Honest caveat: automated scraping is against LinkedIn's ToS; the
scraper is paced like a human (2–6s between pages, ~12 posting visits/day)
which keeps risk low, but a restriction is possible — if that trade-off
feels wrong, make him a bare secondary account instead (hiring-team info is
still visible, just less warm-path context).

When the session expires (months, usually), the LinkedIn Scan run logs
"session EXPIRED" — just re-run the two commands above.

## 4. Test

Actions tab → **LinkedIn Scan (VM)** → Run workflow. Green run + a
"LinkedIn scan" commit on `pending_jobs.json` means it worked; the evening
edition will carry "Reach out" lines from it.

---

## What else the VM can do for this project (beyond LinkedIn)

You asked — here's the realistic menu, roughly in order of value:

1. **Un-block the bot-walled boards.** CareerBeacon (and sometimes Indeed/
   Glassdoor) 403 GitHub's datacenter IPs. Moving those scrapers to the VM
   runner (same pattern as `linkedin_scan.yml`: scrape → merge into
   `pending_jobs.json` → commit) makes them reliable. CareerBeacon is a
   10-line change when you want it.
2. **allNovaScotia.** THE local business-intel source ($30/mo subscription,
   everyone senior in NS reads it). With a subscription, the VM can log in
   nightly and feed relevant items (executive moves, expansions, M&A) into
   the NS radar — far better networking signal than the public feeds.
3. **A nightly deep-research agent.** Install Claude Code on the VM and cron
   it: for each 4–5★ job, research the company (news, financials,
   leadership) and commit a one-page dossier next to the edition — the
   Interview Brief, but automatic and ahead of time.
4. **Inbox watcher.** With a Gmail app password for Marcel's account, a small
   IMAP script can watch for replies from applications/recruiters, update
   `applications.json` automatically (status: waiting → interview), and
   flag "reply needed" items into the evening email.
5. **Backup + cron redundancy.** GitHub's schedule occasionally skips or
   delays runs; the VM can cron a `workflow_dispatch` trigger via `gh` as a
   belt-and-braces, and rsync `history.json`/`grove.json` nightly.

None of these are built yet — say the word for any of them and it's a small
addition on the same chassis.

# VM setup — complete walkthrough

The newsletter core runs free on GitHub's servers. This VM adds what those
servers can't do: **logged-in LinkedIn scraping** (better results + the
"Meet the hiring team" contacts), and optionally a nightly Claude research
agent and an allNovaScotia feed. Cost: ~$6–9/month. Time: about an hour the
first evening. No prior server experience assumed.

---

## Part 1 — Rent the server (~10 min)

Any provider works; DigitalOcean is the most beginner-friendly:

1. Create an account at digitalocean.com (or hetzner.com for ~€4).
2. **Create → Droplet**. Choose:
   - Region: Toronto (closest to NS)
   - Image: **Ubuntu 24.04 LTS**
   - Size: Basic → Regular → **$6/mo (1 GB RAM)** — enough; the $12 (2 GB)
     one is more comfortable if you add the Claude agent later
   - Authentication: **Password** is fine to start (SSH keys are better if
     you know them)
3. Note the droplet's IP address (e.g. `164.90.x.x`).
4. Open a terminal on your Mac and connect:

```bash
ssh root@YOUR_VM_IP
# type yes, then the password you set
```

You're now typing commands **on the VM**. Everything in Parts 2–4 happens
in this SSH session unless it says "on your Mac".

## Part 2 — Base software (~10 min)

Paste these one block at a time:

```bash
apt update && apt upgrade -y
apt install -y python3-pip python3-venv git curl
```

```bash
# A non-root user for the runner (GitHub refuses to run as root)
adduser --disabled-password --gecos "" vern
usermod -aG sudo vern
echo "vern ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vern
su - vern            # <- from here on you are user "vern"
```

```bash
pip3 install --break-system-packages playwright
python3 -m playwright install chromium
sudo $(which python3) -m playwright install-deps chromium
```

## Part 3 — Connect it to GitHub Actions (~15 min)

This registers the VM as a "self-hosted runner": GitHub sends it the
LinkedIn Scan job on schedule, the VM runs it, commits results back. No
ports to open — the VM dials out to GitHub, never the reverse.

1. In a browser: repo → **Settings → Actions → Runners →
   New self-hosted runner** → Linux / x64.
2. GitHub shows a **Download** block and a **Configure** block with a
   fresh token. Paste the Download block into the VM SSH session (as user
   `vern`), then the Configure block. When `./config.sh` asks questions:
   - runner group: Enter (default)
   - runner name: Enter (default)
   - **additional labels: type `linkedin`** ← this one matters
   - work folder: Enter (default)
3. Make it a permanent background service:

```bash
sudo ./svc.sh install vern
sudo ./svc.sh start
sudo ./svc.sh status     # should say active (running)
```

4. Back in the browser, the Runners page should show your runner as
   **Idle** with the `linkedin` label. Done.

> Public-repo safety: keep the default setting Settings → Actions →
> General → "Require approval for first-time contributors". Then no
> stranger's pull request can ever run code on your VM.

## Part 4 — Give it the LinkedIn session (~10 min)

**On your Mac** (not the VM):

```bash
pip3 install playwright && python3 -m playwright install chromium
cd ~/Downloads && curl -O https://raw.githubusercontent.com/clairechabot/papa-job-search/main/linkedin_auth.py
python3 linkedin_auth.py
```

A Chrome window opens on linkedin.com/login. Log in with **Marcel's
account** (2FA and all), wait until his feed loads, then press Enter in
the terminal. It writes `linkedin-auth.json`. Ship it to the VM:

```bash
ssh root@YOUR_VM_IP "mkdir -p /home/vern/.config && chown vern:vern /home/vern/.config"
scp linkedin-auth.json root@YOUR_VM_IP:/home/vern/.config/linkedin-auth.json
ssh root@YOUR_VM_IP "chown vern:vern /home/vern/.config/linkedin-auth.json && chmod 600 /home/vern/.config/linkedin-auth.json"
rm linkedin-auth.json     # don't leave the session file lying around
```

Why Marcel's account: the "Meet the hiring team" panel and warm-path
context follow his network. Honest caveat: automated access is against
LinkedIn's ToS. The scraper is deliberately slow and small (2–6s between
pages, ~12 posting visits per day) which keeps the risk low, but a
restriction is possible; a bare secondary account is the cautious
alternative if that trade-off feels wrong.

**When it expires** (typically after some months, or if he changes his
password): the LinkedIn Scan run prints `session EXPIRED` — just repeat
Part 4.

## Part 5 — Test it

Repo → **Actions → LinkedIn Scan (VM) → Run workflow**. Within ~5 minutes
you want: a green run, and a new commit named "LinkedIn scan" touching
`pending_jobs.json`. That evening's edition will carry richer LinkedIn
results and "Reach out" contact lines.

If the run never starts: the runner is offline — on the VM,
`sudo ./svc.sh status`, and check the Runners page shows Idle.

---

## Part 6 (optional) — Nightly Claude research agent on your Max account

Claude Code is included in your Claude Max subscription, and it can run on
the VM logged in as you — no API key, no extra cost beyond the
subscription. This is the same pattern the pros use for scheduled agents.

Install and log in (on the VM, as `vern`):

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude /login
```

`/login` prints a URL — open it in the browser **on your Mac**, sign in to
YOUR claude.ai account (Claire's Max), and paste the code it gives you
back into the VM terminal. The login persists on the VM.

What to do with it — the natural first agent is **nightly company
dossiers**: after the evening edition, have Claude research each
apply-worthy company (news, financials, leadership, likely interview
themes) and email/commit a one-pager so Marcel wakes up prepared. A
starting cron (edit with `crontab -e`):

```cron
# 23:30 Atlantic nightly - research tonight's top jobs
30 3 * * * cd /home/vern/dossiers && ./run-dossiers.sh >> dossier.log 2>&1
```

where `run-dossiers.sh` clones/pulls the repo, reads `curated_data`'s
4–5★ jobs from the day's edition in docs/, and calls
`claude -p "Research <company> for a CFO candidate interview... write
dossier.md"` per company. **Ask Claude (this project) to build
`run-dossiers.sh` when you're ready** — it's a small script, and worth
doing after the core loop has run for a week.

Notes: it's your account, so his dossiers run under your usage limits
(nightly 3–5 short researches barely dents Max). Keep `claude` logged in
on the VM only as long as you're comfortable — `claude /logout` removes it.

## Part 7 (optional) — allNovaScotia in the radar

allNovaScotia is subscription-only and famously protective: they pursue
login-sharing and automated access aggressively, and their site is built
to detect it. **Do not point a scraper at their website.**

The safe route: allNovaScotia sends subscribers a **daily headline email**.
If Marcel subscribes ($30/mo, worth it during a NS search):

1. In his Gmail, create a filter: from `allnovascotia.com` → apply label
   `ANS` (and optionally forward to a dedicated address).
2. Ask Claude (this project) to build the **inbox-watcher** upgrade on the
   VM: an IMAP script (Gmail app password for his account) that reads the
   ANS-labelled email each morning and folds executive moves, expansions,
   and M&A items into the evening edition's "Nova Scotia radar" — reading
   mail he legitimately receives, no site scraping, no ToS drama.

The same inbox-watcher, once built, also updates `applications.json`
automatically when companies reply, and flags "reply needed" items into
the newsletter — say the word and it gets built.

---

## Maintenance cheat-sheet

| Symptom | Fix (on the VM) |
|---|---|
| Runner shows offline | `cd ~/actions-runner && sudo ./svc.sh start` |
| LinkedIn "session EXPIRED" in run log | Repeat Part 4 |
| VM feels full | `df -h`; `docker system prune` n/a; clear `~/actions-runner/_work` |
| Ubuntu security updates | `sudo apt update && sudo apt upgrade -y` monthly |
| Rebooted droplet | Runner and cron auto-start; nothing to do |

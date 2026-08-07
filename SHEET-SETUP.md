# The Application Tracker — Google Sheet setup (~20 minutes, once)

The tracker is a Google Sheet in **Marcel's** Google account that fills
itself in. Nobody types rows into it:

- Clicking **☆ Save** on a job in the full edition or the Grove adds it as
  Saved.
- A small script inside his Google account scans his **Gmail** daily:
  application confirmations mark jobs **Applied**, replies from those
  companies mark **Heard back**, rejection wording marks **Rejected**.
- The same script scans his **Calendar**: a meeting with a tracked company
  marks **Interview** with the meeting date.
- The VM reads his **LinkedIn** "Applied" list and recruiter-message inbox
  nightly and feeds those in too (see Part 4).
- The nightly newsletter reads the sheet back: Applied/Saved badges, an
  "In play" section, and a nudge when an application has gone quiet.

Do this at Marcel's computer, signed in to his Google account
(marcel.e.chabot@gmail.com). Nothing here leaves his account: the script
runs inside Google, and no passwords are stored anywhere.

## Part 1 — Create the sheet (3 min)

1. Go to sheets.google.com → **Blank spreadsheet**.
2. Name it (top-left): `Next Chapter — Application Tracker`.
3. Rename the tab at the bottom from "Sheet1" to exactly: `Tracker`
   (double-click the tab name).
4. Paste this into cell **A1** (it fills the whole header row):

   ```
   First seen	Applied on	Last contact on	Contact via	Meeting on	Status	Title	Company	Location	Salary	Score	Source	Job URL	Detected via	Last update	Notes
   ```

5. Share it with Claire: **Share** button → her email → Editor.

## Part 2 — Install the script (7 min)

1. In the sheet: **Extensions → Apps Script**. A code editor opens.
2. Delete the placeholder code, and paste in the entire contents of
   [`tools/apps-script/tracker.gs`](tools/apps-script/tracker.gs) from the
   repo (open the file on GitHub → Raw → select all → copy).
3. Near the top, change this line to any random words you invent (this is
   a shared password between the newsletter and the sheet):

   ```
   var TOKEN = 'CHANGE-ME-any-random-words';
   ```

   Write down what you chose — you need it again in Part 5.
4. Click the 💾 save icon. Name the project `tracker` if asked.

## Part 3 — Turn on the two automations (5 min)

**The webhook (receives Save-button clicks):**

1. Top-right: **Deploy → New deployment**.
2. Gear icon → **Web app**.
3. "Execute as": **Me**. "Who has access": **Anyone**.
4. Click **Deploy**, authorize when Google asks (Advanced → Go to tracker
   → Allow — it's your own script reading your own data).
5. **Copy the Web app URL** (ends in `/exec`). You need it in Part 5.

**The daily Gmail + Calendar scan:**

1. Left sidebar: clock icon (**Triggers**) → **Add Trigger** (bottom right).
2. Function: `dailyScan` · Event source: **Time-driven** ·
   Type: **Day timer** · Time: **7am–8am**.
3. Save; authorize the Gmail/Calendar permissions when asked.

Test it now: back in the editor, pick `dailyScan` in the function dropdown
and press **Run**. If Marcel has any application-confirmation emails from
the last 3 days, rows appear in the sheet.

## Part 4 — Publish the sheet for the newsletter to read (2 min)

1. In the sheet: **File → Share → Publish to web**.
2. First dropdown: the **Tracker** tab (not "Entire Document").
   Second dropdown: **Comma-separated values (.csv)**.
3. **Publish**, confirm, and **copy the URL** it shows.

This URL is read-only and unguessable; it's how the nightly pipeline sees
statuses. (Note: anyone with this exact URL could read the job list — it
contains job titles and statuses, no personal data.)

## Part 5 — Tell the newsletter about it (3 min, Claire, on GitHub)

Repo → **Settings → Secrets and variables → Actions → Variables** tab →
**New repository variable**, three times:

| Variable | Value |
|---|---|
| `SHEET_WEBHOOK_URL` | the Web app URL from Part 3 (ends `/exec`) |
| `SHEET_CSV_URL` | the published-CSV URL from Part 4 |
| `SHEET_TOKEN` | the random words you invented in Part 2 |

Done. From the next evening edition: ☆ Save buttons write to the sheet,
badges and the "In play" section appear, and the daily scans keep statuses
moving on their own.

## Part 6 — Marcel's LinkedIn feed (optional but recommended, 10 min)

Catches applications made on LinkedIn with "Easy Apply" (no email trail)
and recruiter replies in LinkedIn Messaging. On Claire's Windows PC, with
Marcel present to log in:

```
python linkedin_auth.py --account marcel
```

He logs into HIS LinkedIn in the Chrome window (2FA and all), waits for
the feed, presses Enter. Then ship it to the VM:

```
scp linkedin-auth-marcel.json root@137.184.173.202:/home/vern/.config/linkedin-auth-marcel.json
ssh root@137.184.173.202 "chown vern:vern /home/vern/.config/linkedin-auth-marcel.json && chmod 600 /home/vern/.config/linkedin-auth-marcel.json"
del linkedin-auth-marcel.json
```

The nightly LinkedIn Scan workflow picks it up automatically. It reads
ONLY his Applied-jobs list and the conversation list (names and dates,
never message contents). If the session expires, the scan logs a warning
and everything else keeps working; redo this part to refresh.

## Troubleshooting

- **Buttons don't write to the sheet** — check the three repo variables
  for typos; the TOKEN in the script and `SHEET_TOKEN` must match exactly.
- **No rows from the Gmail scan** — in the Apps Script editor, run
  `scanGmail` manually and check View → Executions for errors. The scan
  only looks back 3 days.
- **A wrong company matched** (rare) — delete the row; the scan only
  matches companies already tracked, so noise stays contained.
- **Statuses never move backward** by design: a Save click on an applied
  job changes nothing; Rejected is terminal. To re-open a job, clear its
  Status cell by hand.

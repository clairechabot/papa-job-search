# Claude Project setup — 10 minutes

This gives your dad a persistent "career coach" on claude.ai: every chat he
opens in the project already knows his CV, his targets, and how to handle
the age question.

## Steps

1. On his claude.ai account (a paid plan makes Projects available), go to
   **Projects → Create project**. Name it something he'll like -
   "Next Chapter HQ" or "Chef des finances".
2. Open `instructions.md` (this folder), copy the whole file, and paste it
   into **Project instructions** (the "Set instructions" box).
3. Fill in the four files in `knowledge/` with him - this is the important
   30 minutes, ideally done together over a coffee:
   - `master-cv.md` - full career fact base (the coach's single source of truth)
   - `achievements.md` - quantified wins / STAR story bank
   - `target.md` - what he wants, dealbreakers, salary floor
   - `ns-market.md` - pre-filled Nova Scotia landscape; adjust as he learns
4. Upload all four to the project's **Knowledge** section.
5. First chat, have him try: *"Here's a posting I found - tailor my CV"*
   (paste any posting from the newsletter), or just *"bonjour"* to see the
   check-in ritual work.

## Keeping it useful

- After interviews, have him debrief in the project - the coach turns it
  into lessons and updated stories.
- When facts change (new certification, new target), update the knowledge
  file and re-upload; project knowledge is not editable in place.
- The newsletter and the project pair up: newsletter surfaces the job,
  project tailors the application, `applications.json` tracks it,
  the Interview Brief action preps the meeting.

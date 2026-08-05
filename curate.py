"""Curation: free regex gate -> Vern (Claude) scores against
profile/candidate.md with location tiers, salary floors, title-level rules;
writes per-job summary + why + watch_out, a "start here" kickoff prompt for
3-5 star jobs, AI-article picks, and Vern's daily note.

Two-stage cost control from Ellipsis Athena's enrichment gate: the regex gate
discards obvious non-fits so the LLM only prices plausible ones. Without
CLAUDE_API_KEY the pipeline still works in gate-only mode (no scores).

Usage:  python curate.py [--edition morning|evening]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
IN_FILE = HERE / "fetched_data.json"
OUT_FILE = HERE / "curated_data.json"
PROFILE_FILE = HERE / "profile" / "candidate.md"
HALIFAX = ZoneInfo("America/Halifax")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

TIER_LABELS = {1: "Nova Scotia", 2: "Eastern Canada", 3: "Remote",
               4: "Northeast US", 0: "Out of area"}

# ---------------------------------------------------------------------------
# Stage 1: free regex gate (title universe from profile/candidate.md)
# ---------------------------------------------------------------------------
TITLE_PASS = re.compile(
    r"\b(cfo|cfoo|chief financial|chief administrative officer"
    r"|[sae]?vp,?( of)? finance|v\.?p\.?( of)? finance"
    r"|vice[- ]president,?( of)? finance|finance director|director of finance"
    r"|director,? finance|directeur financier|direction financi[eè]re"
    r"|head of finance|head of treasury|finance lead|controller"
    r"|contr[oô]leur|treasurer"
    r"|secretary[- ]treasurer|finance executive|financial officer"
    r"|senior director,? finance|gm,? finance|operating partner"
    r"|portfolio (company )?cfo|interim cfo|fractional cfo)\b", re.I)

TITLE_BLOCK = re.compile(
    r"\b(assistant|junior|intermediate|intern|co[- ]?op|clerk|bookkeeper"
    r"|payable|receivable|payroll|cook|server|cashier|driver|technician"
    r"|analyst|coordinator|administrator\b)\b", re.I)

WILDCARD = re.compile(r"\b(chief administrative officer|cao\b|secretary[- ]"
                      r"treasurer|interim|fractional|operating partner"
                      r"|michelin)\b", re.I)


def gate(job: dict) -> bool:
    title = job.get("title", "")
    if TITLE_BLOCK.search(title):
        return False  # block wins: "Assistant Corporate Controller" is out
    if not TITLE_PASS.search(title):
        return False
    if job.get("tier", 0) == 0:
        return False
    job["wildcard"] = bool(WILDCARD.search(title))
    return True


# ---------------------------------------------------------------------------
# Stage 2: Vern (Claude) scoring
# ---------------------------------------------------------------------------
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                    "summary": {"type": "string"},
                    "why": {"type": "string"},
                    "watch_out": {"type": "string"},
                    "kickoff_prompt": {"type": "string"},
                    "attachments": {"type": "array",
                                    "items": {"type": "string"}},
                },
                "required": ["index", "score", "summary", "why",
                             "watch_out", "kickoff_prompt", "attachments"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["jobs"],
    "additionalProperties": False,
}

PICKS_SCHEMA = {
    "type": "object",
    "properties": {
        "ai_picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["index", "note"],
                "additionalProperties": False,
            },
        },
        "encouragement": {"type": "string"},
        "one_action": {"type": "string"},
    },
    "required": ["ai_picks", "encouragement", "one_action"],
    "additionalProperties": False,
}

SCORER_SYSTEM = """\
You are Vern, the career scout for one specific candidate. The candidate
profile below is your only source of truth about him - never invent facts.
Apply its location tiers, title universe, and salary rule exactly.

Scoring scale:
5 = apply today: senior finance leadership, tier 1-2 location (or great
    remote), strong sector/PE fit
4 = strong fit, minor mismatch (tier 3-4 location, sector stretch, or a
    slightly-lower title with real P&L scope)
3 = worth a look: plausibly right, needs his judgment
2 = weak fit (too junior, wrong region)
1 = dealbreaker per profile

HARD RULE - salary floors: he will not leave his current job for less than
the profile's floors. If a posting STATES compensation below the floor for
its region, score it 1 regardless of everything else, and quote the number
in watch_out. Never rank a below-floor posting as worth his evening. If no
compensation is stated, score normally and say nothing about salary.

Per job, write:
- "summary": 1-2 sentences - what this job actually is (from title, company,
  location, description snippet) and how it aligns with his goal, calibrated
  to your score ("Mid-size manufacturer seat, hands-on scope - exactly the
  profile you want" vs "Enterprise title but staff role - misaligned").
- "why": 1-2 plain sentences addressed to him ("PE-backed integrator,
  your exact playbook"). Call out stated benefits/share plans here.
- "watch_out": one honest caveat or "" (below-floor salary quoted here;
  "title below your level - confirm full P&L" for notch-down titles).
- "kickoff_prompt": ONLY for scores 3-5, else "". A copy-paste-ready prompt
  addressed to Vern in his Claude Project. It must: (a) name the role,
  company and URL; (b) open with "Run a blunt fit check on this posting
  first - pros and cons against my resume, verdict included"; (c) for score
  3, weight toward "tell me if this is worth an evening"; for 4-5, continue
  "then tailor my CV emphasis for this seat, draft a cover letter in my
  First-100-Days style, and suggest one human route in"; (d) if a hiring
  contact is listed, add "draft a LinkedIn note to <name>, <title>";
  (e) end with: "I'm pasting the posting text below." Keep it under 130
  words, first person, plain text.
- "attachments": ONLY for scores 3-5, else []. The checklist of what he
  must add to the chat himself alongside the prompt: 1-3 short imperative
  items ("Paste the full posting text - open the job link and copy
  everything"). Always include the posting text item. Add others only when
  the prompt genuinely needs them (e.g. a company page or contact profile
  worth pasting). His CV and targets already live in the Project knowledge,
  so never list those unless the prompt asks him to update them.

No em-dashes anywhere. Return every job you were given, by index."""

PICKS_SYSTEM = """\
You are Vern, curating an "AI for the workplace" section for a 62-year-old
CFO (manufacturing/industrial background, applying for operating finance
leadership at mid-size and PE-backed companies). He is relocating to Nova
Scotia to be near family - Nova Scotia leads are the prize, eastern Canada
and remote next, the US northeast acceptable; never frame Nova Scotia as far
afield. Pick the 2-3 articles most
useful for that reader: AI in finance functions, AI strategy executives are
expected to have a view on, adoption in manufacturing/industrial operations.
Skip model-release hype and engineering deep dives. For each pick write
"note": one sentence on what it means for a senior finance leader in his
target fields.

Also write "encouragement": Vern's note at the top of the evening edition,
90-130 words. Vern's character is, quietly, Captain Picard of the
Enterprise: measured, literate, dignified gravitas; a captain addressing a
respected officer, never a cheerleader. The register - not cosplay:
- Complete, unhurried sentences; the occasional classical, literary, or
  seafaring allusion; understatement over exclamation (no exclamation
  marks, ever).
- Deep respect for experience: his decades are a command record, not a
  liability. Duty, patience, and standards are virtues.
- Honest about difficulty the way a captain is: name the long odds calmly,
  then set the course.
- End with ONE concrete order-like action for this week, framed as an
  invitation ("I would suggest...", "Might I recommend..."), and when it
  lands naturally - not every night - close that line with "Make it so."
- Never mention Star Trek, starships, captains, or Picard by name. No
  space metaphors. The personality lives in cadence and bearing only.
- Rotate substance nightly: the value of his operating record, patience in
  a long search, a networking move, tonight's strongest lead, the AI
  reading as an edge, family as the reason the mission matters. Do NOT
  reuse the themes or sentence structures of the recent notes provided.
No em-dashes anywhere.

Separately, write "one_action": a single sentence for the "Tonight in one
minute" digest - the one concrete thing he should do this week, in Vern's
voice, standalone (it also appears outside the note). May differ from the
note's action or restate it more briefly. No em-dashes."""


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])


def _structured(client, system: str, user: str, schema: dict) -> dict | None:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        print("[curate] WARNING: model refused; falling back", file=sys.stderr)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def _job_line(i: int, j: dict) -> str:
    contact = ""
    if j.get("contacts"):
        c = j["contacts"][0]
        contact = f" | hiring contact: {c.get('name')}, {c.get('title', '')}"
    return (f"[{i}] tier={TIER_LABELS.get(j.get('tier'), '?')}"
            f"{' WILDCARD' if j.get('wildcard') else ''} | {j['title']}"
            f" | {j.get('company', '?')} | {j.get('location', '?')}"
            f" | salary: {j.get('salary', 'not stated')}"
            f" | {j.get('snippet', '')[:200]}{contact} | url: {j.get('url', '')}")


def score_jobs(client, jobs: list[dict], profile: str) -> None:
    if not jobs:
        return
    # Batch in chunks of 25 to keep responses well-formed.
    for start in range(0, len(jobs), 25):
        chunk = jobs[start:start + 25]
        listing = "\n".join(_job_line(i, j) for i, j in enumerate(chunk))
        result = _structured(
            client, SCORER_SYSTEM,
            f"CANDIDATE PROFILE:\n{profile}\n\nJOB POSTINGS:\n{listing}",
            SCORE_SCHEMA)
        if not result:
            continue
        by_index = {row["index"]: row for row in result.get("jobs", [])}
        for i, job in enumerate(chunk):
            row = by_index.get(i)
            if row:
                job.update(score=row["score"], summary=row["summary"],
                           why=row["why"], watch_out=row["watch_out"],
                           kickoff_prompt=row["kickoff_prompt"],
                           attachments=row.get("attachments", []))


def pick_ai_articles(client, articles: list[dict],
                     recent_notes: list[str] | None = None,
                     top_jobs: list[str] | None = None) -> tuple[list[dict], str]:
    if not articles:
        return [], ""
    listing = "\n".join(
        f"[{i}] ({a['feed']}) {a['title']} :: {a.get('summary', '')[:200]}"
        for i, a in enumerate(articles[:40]))
    recent = "\n".join(f"- {n}" for n in (recent_notes or [])[-7:]) or "(none yet)"
    tonight = "; ".join((top_jobs or [])[:3]) or "(no standout leads tonight)"
    result = _structured(
        client, PICKS_SYSTEM,
        f"ARTICLES:\n{listing}\n\nRECENT NOTES (do not repeat their themes or "
        f"structures):\n{recent}\n\nTONIGHT'S STRONGEST LEADS (usable as a "
        f"theme): {tonight}",
        PICKS_SCHEMA)
    if not result:
        return [], ""
    picks = []
    for row in result.get("ai_picks", [])[:3]:
        if 0 <= row["index"] < len(articles):
            article = dict(articles[row["index"]])
            article["note"] = row["note"]
            picks.append(article)
    return picks, result.get("encouragement", ""), result.get("one_action", "")


def build_digest(gated: list[dict], total_read: int, one_action: str) -> list[dict]:
    """The 'Tonight in one minute' rows, shared by the email and the full
    edition so the two always agree."""
    scored = [j for j in gated if j.get("score")]
    top = max(scored, key=lambda j: j["score"], default=None)
    apply_n = sum(1 for j in gated if (j.get("score") or 0) >= 4)
    ns = [j for j in gated if j.get("tier") == 1]
    rows = []
    if top and top["score"] >= 3:
        rows.append({"label": "Top pick",
                     "value": f"{top['title']} at {top.get('company', '?')}"
                              f" ({TIER_LABELS.get(top.get('tier'), '?')})."})
    rows.append({"label": "New tonight",
                 "value": f"{total_read} postings read; "
                          f"{apply_n or 'none'} apply-worthy, "
                          f"{len(gated)} cleared the gate."})
    if ns:
        best_ns = max(ns, key=lambda j: j.get("score") or 0)
        rows.append({"label": "Home turf",
                     "value": f"{len(ns)} Nova Scotia posting"
                              f"{'s' if len(ns) != 1 else ''} tonight, led by "
                              f"{best_ns['title']}."})
    rows.append({"label": "One action",
                 "value": one_action or "Open the full edition and give the "
                          "top pick ten unhurried minutes."})
    return rows[:4]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=["morning", "evening"],
                        help="default: by Halifax clock (<12 = morning)")
    args = parser.parse_args()

    data = json.loads(IN_FILE.read_text(encoding="utf-8"))
    now = datetime.datetime.now(HALIFAX)
    edition = args.edition or ("morning" if now.hour < 12 else "evening")

    gated = [j for j in data["jobs"] if gate(j)]
    print(f"[curate] gate: {len(gated)} passed, {len(data['jobs']) - len(gated)} rejected")

    encouragement = ""
    one_action = ""
    ai_picks: list[dict] = []
    if os.environ.get("CLAUDE_API_KEY"):
        client = _client()
        # Privacy option for the public repo: a CANDIDATE_PROFILE secret
        # (full markdown) overrides the committed profile file.
        profile = (os.environ.get("CANDIDATE_PROFILE")
                   or PROFILE_FILE.read_text(encoding="utf-8"))
        score_jobs(client, gated, profile)
        # Nightly variety: Vern sees his last week of notes (stored in
        # history.json, Curated Canopy recent_greetings pattern) plus
        # tonight's best leads, and must not repeat himself.
        history_file = HERE / "history.json"
        hist = (json.loads(history_file.read_text(encoding="utf-8-sig"))
                if history_file.exists() else {})
        top_jobs = [f"{j['title']} at {j.get('company', '?')}"
                    for j in gated if (j.get("score") or 0) >= 4]
        ai_picks, encouragement, one_action = pick_ai_articles(
            client, data["ai_articles"], hist.get("recent_notes", []), top_jobs)
        if encouragement:
            hist["recent_notes"] = (hist.get("recent_notes", [])
                                    + [encouragement])[-7:]
            history_file.write_text(
                json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[curate] Vern scored {len(gated)} jobs, picked {len(ai_picks)} articles")
    else:
        print("[curate] CLAUDE_API_KEY not set: gate-only mode (no scores)")

    OUT_FILE.write_text(json.dumps({
        "curated_at": now.isoformat(),
        "edition": edition,
        "weekday": now.strftime("%A"),
        "jobs": sorted(gated, key=lambda j: -(j.get("score") or 0)),
        "ai_picks": ai_picks,
        "ai_articles": data.get("ai_articles", []),
        "ns_articles": data.get("ns_articles", []),
        "encouragement": encouragement,
        "digest": build_digest(gated, len(data["jobs"]), one_action),
        "stats": {
            "postings_read": len(data["jobs"]),
            "apply": sum(1 for j in gated if (j.get("score") or 0) >= 4),
            "home": sum(1 for j in gated if j.get("tier") == 1),
        },
        "source_status": data.get("source_status", {}),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[curate] wrote {OUT_FILE.name} ({edition} edition)")


if __name__ == "__main__":
    main()

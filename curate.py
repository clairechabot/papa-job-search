"""Curation: cheap regex gate -> Claude scoring against profile/candidate.md.

Two-stage cost control copied from Ellipsis Athena's enrichment gate: the free
regex gate discards obvious non-fits (cooks, cashiers, junior roles) so the
LLM only prices the plausible ones. Scoring rubric style follows the
relevancy-check skill: per-job 1-5 score + "why it fits" + "watch out".

Without CLAUDE_API_KEY the script still works: gate-only mode, score=None,
so the newsletter never silently dies on a missing/expired key.

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

# Overridable so the user can trade cost vs quality without a code change.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

# ---------------------------------------------------------------------------
# Stage 1: free regex gate
# ---------------------------------------------------------------------------
TITLE_PASS = re.compile(
    r"\b(cfo|chief financial|vp finance|v\.p\.? finance|vice[- ]president,? finance"
    r"|finance director|director of finance|director,? finance|directeur financier"
    r"|head of finance|finance lead|controller|contr[oô]leur|treasurer"
    r"|finance executive|financial officer|senior director)\b", re.I)

TITLE_BLOCK = re.compile(
    r"\b(assistant|junior|intermediate|intern|co[- ]?op|clerk|bookkeeper"
    r"|payable|receivable|payroll|cook|server|cashier|driver|technician"
    r"|analyst)\b", re.I)

ATLANTIC = re.compile(r"\b(NS|Nova Scotia|Halifax|Dartmouth|Bedford|Sydney"
                      r"|Truro|Kentville|Wolfville|New Glasgow|Bridgewater"
                      r"|NB|New Brunswick|Moncton|Saint John|Fredericton"
                      r"|PE|PEI|Prince Edward|Charlottetown|Atlantic|Remote)\b", re.I)


def gate(job: dict) -> bool:
    title = job.get("title", "")
    # Block wins even when a pass term is present: "Assistant Corporate
    # Controller" is a dealbreaker per the profile despite "controller".
    if TITLE_BLOCK.search(title):
        return False
    if not TITLE_PASS.search(title):
        return False
    # Sources already scoped to Atlantic Canada skip the location check.
    if job.get("source") in ("Meridia Recruitment (KBRS)", "CareerBeacon"):
        return True
    loc = f"{job.get('location', '')} {job.get('title', '')}"
    return bool(ATLANTIC.search(loc))


# ---------------------------------------------------------------------------
# Stage 2: Claude scoring
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
                    "why": {"type": "string"},
                    "watch_out": {"type": "string"},
                },
                "required": ["index", "score", "why", "watch_out"],
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
    },
    "required": ["ai_picks", "encouragement"],
    "additionalProperties": False,
}

SCORER_SYSTEM = """\
You score job postings for one specific candidate. The candidate profile below
is your only source of truth about them - never invent facts.

Scoring scale:
5 = apply today: senior finance leadership, right region/remote, strong sector fit
4 = strong fit, minor mismatch (sector, hybrid anchor, slightly junior title with senior scope)
3 = worth a look: plausibly senior enough, or great org with an imperfect seat
2 = weak fit (too junior, wrong region, wrong track) - explain in one sentence
1 = dealbreaker per profile

Write "why" as 1-2 plain sentences addressed to the candidate ("Irving-scale
manufacturer, your exact sector"). Write "watch_out" as one honest caveat
("posting reads mid-career; lead with scale of your P&L if you apply") or "".
No em-dashes. Return every job you were given, by index."""

PICKS_SYSTEM = """\
You curate an "AI for the workplace" section for a 62-year-old CFO who wants to
stay sharp on AI in finance and business - a competitive edge against ageism.
Pick the 2-3 most useful articles for that reader: practical AI-in-finance,
AI strategy for executives, workplace adoption. Skip model-release hype and
engineering deep dives. For each pick write "note": one sentence on what it
means for a senior finance leader.

Also write "encouragement": 2-3 sentences for the top of the newsletter. Tone:
a peer who respects him - warm, specific, never saccharine or pitying. Rotate
themes: momentum, the value of his experience, networking nudges, small
concrete actions. No em-dashes."""


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])


def _structured(client, system: str, user: str, schema: dict) -> dict | None:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        print("[curate] WARNING: model refused; falling back", file=sys.stderr)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def score_jobs(client, jobs: list[dict], profile: str) -> None:
    """Annotate jobs in place with score/why/watch_out."""
    if not jobs:
        return
    listing = "\n".join(
        f"[{i}] {j['title']} | {j.get('company', '?')} | {j.get('location', '?')}"
        f" | {j.get('salary', '')} | {j.get('snippet', '')[:200]}"
        for i, j in enumerate(jobs))
    result = _structured(
        client, SCORER_SYSTEM,
        f"CANDIDATE PROFILE:\n{profile}\n\nJOB POSTINGS:\n{listing}",
        SCORE_SCHEMA)
    if not result:
        return
    by_index = {row["index"]: row for row in result.get("jobs", [])}
    for i, job in enumerate(jobs):
        row = by_index.get(i)
        if row:
            job.update(score=row["score"], why=row["why"],
                       watch_out=row["watch_out"])


def pick_ai_articles(client, articles: list[dict]) -> tuple[list[dict], str]:
    if not articles:
        return [], ""
    listing = "\n".join(
        f"[{i}] ({a['feed']}) {a['title']} :: {a.get('summary', '')[:200]}"
        for i, a in enumerate(articles[:40]))
    result = _structured(client, PICKS_SYSTEM, f"ARTICLES:\n{listing}",
                         PICKS_SCHEMA)
    if not result:
        return [], ""
    picks = []
    for row in result.get("ai_picks", [])[:3]:
        if 0 <= row["index"] < len(articles):
            article = dict(articles[row["index"]])
            article["note"] = row["note"]
            picks.append(article)
    return picks, result.get("encouragement", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=["morning", "evening"],
                        help="default: by Halifax clock (<12 = morning)")
    args = parser.parse_args()

    data = json.loads(IN_FILE.read_text(encoding="utf-8"))
    now = datetime.datetime.now(HALIFAX)
    edition = args.edition or ("morning" if now.hour < 12 else "evening")

    gated = [j for j in data["jobs"] if gate(j)]
    rejected = len(data["jobs"]) - len(gated)
    print(f"[curate] gate: {len(gated)} passed, {rejected} rejected")

    encouragement = ""
    ai_picks: list[dict] = []
    if os.environ.get("CLAUDE_API_KEY"):
        client = _client()
        score_jobs(client, gated, PROFILE_FILE.read_text(encoding="utf-8"))
        ai_picks, encouragement = pick_ai_articles(client, data["ai_articles"])
        print(f"[curate] scored {len(gated)} jobs, picked {len(ai_picks)} AI articles")
    else:
        print("[curate] CLAUDE_API_KEY not set: gate-only mode (no scores)")

    OUT_FILE.write_text(json.dumps({
        "curated_at": now.isoformat(),
        "edition": edition,
        "weekday": now.strftime("%A"),
        "jobs": sorted(gated, key=lambda j: -(j.get("score") or 0)),
        "ai_picks": ai_picks,
        "ns_articles": data.get("ns_articles", []),
        "encouragement": encouragement,
        "source_status": data.get("source_status", {}),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[curate] wrote {OUT_FILE.name} ({edition} edition)")


if __name__ == "__main__":
    main()

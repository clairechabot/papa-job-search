"""Job + news source modules.

Each job source exposes `fetch_jobs() -> list[dict]` returning records:
    {source, title, company, location, url, date_posted, salary, snippet}
A source that fails raises — the orchestrator (fetch.py) catches per source so
one broken board never kills the edition.
"""

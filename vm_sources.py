"""Job sources that only work from the VM's IP - runs in the LinkedIn Scan
(VM) workflow, NOT on GitHub-hosted runners.

CareerBeacon 403s GitHub's datacenter ranges outright and the public proxy
relays are unreliable, so the GitHub-hosted evening fetch usually reports it
"unavailable". The droplet's IP has a different reputation; fetching from
here recovers the main Atlantic Canada job board. Results merge into
pending_jobs.json exactly like the authenticated LinkedIn scan - the
evening edition consumes the pool, tags tiers, and dedupes against history.

Failures exit 0 with a warning: this is a recovery layer, never a blocker.

Usage:  python3 vm_sources.py
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
PENDING_FILE = HERE / "pending_jobs.json"
HALIFAX = ZoneInfo("America/Halifax")

sys.path.insert(0, str(HERE))
from history import is_seen, job_fingerprint, load_history  # noqa: E402

VM_SOURCES = [
    ("CareerBeacon", "sources.careerbeacon"),
]


def main() -> None:
    import importlib

    history = load_history()
    pending = {"scanned_at": "", "jobs": [], "source_status": {}}
    if PENDING_FILE.exists():
        pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    pool = {job_fingerprint(j): j for j in pending.get("jobs", [])}

    total_fresh = 0
    for name, module_name in VM_SOURCES:
        try:
            module = importlib.import_module(module_name)
            found = module.fetch_jobs()
        except Exception as e:  # noqa: BLE001 - boundary: external sites
            print(f"[vm-sources] {name}: unavailable ({type(e).__name__})",
                  flush=True)
            pending.setdefault("source_status", {})[f"{name} (VM)"] = (
                f"unavailable: {type(e).__name__}")
            continue
        fresh = 0
        for job in found:
            fp = job_fingerprint(job)
            if is_seen(job, history) or fp in pool:
                continue
            pool[fp] = job
            fresh += 1
        total_fresh += fresh
        pending.setdefault("source_status", {})[f"{name} (VM)"] = (
            f"ok ({len(found)} found, {fresh} new)")
        print(f"[vm-sources] {name}: {len(found)} found, {fresh} new",
              flush=True)

    pending["jobs"] = list(pool.values())
    pending["scanned_at"] = datetime.datetime.now(HALIFAX).isoformat()
    PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"[vm-sources] pending pool now {len(pool)} job(s) "
          f"(+{total_fresh} from VM sources)")


if __name__ == "__main__":
    main()

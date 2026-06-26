"""Step 3 demo: run each example request through the persisted intake flow.

Resets the demo database, ingests every example (parse -> rules -> route, persisting a
request row and its audit trail), then prints each request and its full audit log.

Usage (from backend/, with deps installed):
    python run_examples.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.pipeline import ingest
from app.storage import reset_storage

EXAMPLES_DIR = Path(__file__).parent / "examples"


def main() -> None:
    storage = reset_storage()

    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        candidate = json.loads(path.read_text())
        raw_intake_text = candidate.get("description") or f"Request for {candidate.get('name')}"
        request_id = ingest(raw_intake_text, candidate, storage)

        request = storage.get_request(request_id)
        print(f"\n=== {path.name} ===")
        print(f"  request id: {request['id']}")
        print(f"  name: {candidate.get('name')!r}  category: {request['category']!r}")
        print(f"  status: {request['status']}")
        print("  audit log:")
        for entry in storage.get_audit_log(request_id):
            print(f"    [{entry['created_at']}] {entry['step']}")
            print(f"        {json.dumps(entry['detail'])}")


if __name__ == "__main__":
    main()

"""Step 4 verification: drive the full flow over HTTP against a running server.

Submits the clean example, approves it, prints the published artifacts and the complete
audit trail, then shows the 409 guard by deciding an already-published request.

Usage (server must be running on BASE):
    python verify_step4.py
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
CLEAN_EXAMPLE = Path(__file__).parent / "examples" / "clean_cart_cleared.json"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def wait_for_server(attempts: int = 40) -> None:
    for _ in range(attempts):
        try:
            urllib.request.urlopen(f"{BASE}/health")
            return
        except urllib.error.URLError:
            time.sleep(0.25)
    raise RuntimeError("server did not come up")


def main() -> None:
    wait_for_server()
    candidate = json.loads(CLEAN_EXAMPLE.read_text())
    raw_intake_text = candidate.get("description") or candidate["name"]

    print("== POST /requests (clean example) ==")
    status, created = call(
        "POST", "/requests",
        {"raw_intake_text": raw_intake_text, "definition": candidate},
    )
    print(f"  HTTP {status}: id={created['id']} status={created['status']}")
    request_id = created["id"]

    print("\n== POST /requests/{id}/decision approve ==")
    status, decided = call(
        "POST", f"/requests/{request_id}/decision",
        {"decision": "approve", "note": "looks good"},
    )
    print(f"  HTTP {status}: status={decided['status']}")
    artifact = decided["published_artifact"]
    print("  confluence_doc:", json.dumps(artifact["confluence_doc"], indent=2))
    print("  jira_ticket:", json.dumps(artifact["jira_ticket"], indent=2))

    print("\n== GET /requests/{id} (full audit log) ==")
    status, detail = call("GET", f"/requests/{request_id}")
    print(f"  status={detail['status']}")
    for entry in detail["audit_log"]:
        print(f"  [{entry['created_at']}] {entry['step']}: {json.dumps(entry['detail'])}")

    print("\n== POST decision again on a published request (expect 409) ==")
    status, conflict = call(
        "POST", f"/requests/{request_id}/decision", {"decision": "approve"}
    )
    print(f"  HTTP {status}: {conflict['detail']}")


if __name__ == "__main__":
    main()

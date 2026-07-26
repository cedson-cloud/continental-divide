"""The full flow over HTTP, in-process via FastAPI's TestClient.

Submits the clean example through /requests/raw (which skips the model, so the test
runs offline), approves it, checks the published artifacts and the complete audit
trail, then the 409 guard on deciding an already-published request.
"""

import json
from pathlib import Path

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"


def test_submit_approve_publish_and_409_guard(client):
    candidate = json.loads(CLEAN_EXAMPLE.read_text())

    response = client.post("/requests/raw", json={"definition": candidate})
    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "pending_approval"
    assert created["routed_to_approval"] is True
    assert all(check["passed"] for check in created["checks"])
    request_id = created["id"]

    response = client.post(
        f"/requests/{request_id}/decision",
        json={"decision": "approve", "note": "looks good"},
    )
    assert response.status_code == 200
    decided = response.json()
    assert decided["status"] == "published"
    artifact = decided["published_artifact"]
    assert artifact["confluence_doc"]["id"]
    assert artifact["jira_ticket"]["key"]

    response = client.get(f"/requests/{request_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "published"
    assert [entry["step"] for entry in detail["audit_log"]] == [
        "intake_received",
        "definition_provided",
        "schema_parsed",
        "rules_evaluated",
        "routed",
        "decision_received",
        "published",
    ]

    response = client.post(
        f"/requests/{request_id}/decision", json={"decision": "approve"}
    )
    assert response.status_code == 409
    assert "cannot be decided" in response.json()["detail"]


def test_reject_decision(client):
    candidate = json.loads(CLEAN_EXAMPLE.read_text())
    request_id = client.post("/requests/raw", json={"definition": candidate}).json()["id"]

    response = client.post(
        f"/requests/{request_id}/decision",
        json={"decision": "reject", "note": "not needed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["published_artifact"] is None


def test_unknown_request_is_404(client):
    assert client.get("/requests/9999").status_code == 404

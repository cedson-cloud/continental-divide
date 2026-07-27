"""The governance profile endpoint and the intake fields it governs: destination
validation against the active profile, the required business_value, the new fields
landing on the request row and in the intake_received audit entry, and the proof
that intake enforces the active profile — the same definition gets opposite
outcomes over the API under the two templates."""

import json
from pathlib import Path

from app.governance import DEFAULT_PROFILE

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"
TEMPLATES_DIR = Path(__file__).parents[2] / "governance" / "templates"


def _raw_body(**overrides):
    body = {
        "definition": json.loads(CLEAN_EXAMPLE.read_text()),
        "business_value": "measures cart abandonment",
    }
    body.update(overrides)
    return body


def test_governance_profile_endpoint_shape(client):
    response = client.get("/governance/profile")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "name",
        "source",
        "event_naming",
        "property_naming",
        "pii",
        "categories",
        "destinations",
    }
    assert data["name"] == "segment-ecommerce"
    assert data["event_naming"]["convention"] == "title_case_object_action"
    assert data["property_naming"]["convention"] == "snake_case"
    assert "email" in data["pii"]["blocklist"]
    assert data["destinations"] == [
        "warehouse",
        "product_analytics",
        "crm",
        "engagement",
        "advertising",
    ]
    # Profile contents only: no file paths, no extends chain.
    assert "extends" not in data


def test_valid_destinations_are_accepted_and_stored(client):
    response = client.post(
        "/requests/raw",
        json=_raw_body(destinations=["warehouse", "crm"], needed_by="Q3 launch"),
    )
    assert response.status_code == 200

    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["business_value"] == "measures cart abandonment"
    assert detail["needed_by"] == "Q3 launch"
    assert detail["request_kind"] == "new_event"
    assert detail["destinations"] == ["warehouse", "crm"]

    intake = next(e for e in detail["audit_log"] if e["step"] == "intake_received")
    assert intake["detail"]["business_value"] == "measures cart abandonment"
    assert intake["detail"]["destinations"] == ["warehouse", "crm"]


def test_unknown_destination_is_rejected_with_the_allowed_list(client):
    response = client.post(
        "/requests/raw", json=_raw_body(destinations=["warehouse", "fax_machine"])
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "unknown destinations: fax_machine" in detail
    assert "warehouse" in detail  # the message names what is allowed


def test_empty_profile_destination_list_means_unconstrained(client, monkeypatch):
    # The built-in default declares no destinations, so anything goes.
    assert DEFAULT_PROFILE.destinations == []
    monkeypatch.setattr("app.routes.load_active_profile", lambda: DEFAULT_PROFILE)
    response = client.post(
        "/requests/raw", json=_raw_body(destinations=["anything_at_all"])
    )
    assert response.status_code == 200


def test_same_definition_gets_opposite_outcomes_over_the_api(client, monkeypatch):
    def submit(name):
        definition = json.loads(CLEAN_EXAMPLE.read_text())
        definition["name"] = name
        return client.post(
            "/requests/raw",
            json={"definition": definition, "business_value": "b"},
        ).json()["status"]

    monkeypatch.setattr(
        "app.governance._ACTIVE_PROFILE_PATH", TEMPLATES_DIR / "segment-ecommerce.yaml"
    )
    assert submit("Cart Cleared") == "pending_approval"
    assert submit("cart_cleared") == "rejected"

    monkeypatch.setattr(
        "app.governance._ACTIVE_PROFILE_PATH", TEMPLATES_DIR / "posthog-snake-case.yaml"
    )
    assert submit("cart_cleared") == "pending_approval"
    assert submit("Cart Cleared") == "rejected"


def test_rules_evaluated_audit_entry_names_the_profile(client):
    request_id = client.post("/requests/raw", json=_raw_body()).json()["id"]
    detail = client.get(f"/requests/{request_id}").json()
    entry = next(e for e in detail["audit_log"] if e["step"] == "rules_evaluated")
    assert entry["detail"]["profile"] == "segment-ecommerce"


def test_malformed_active_profile_returns_a_clean_error(client, monkeypatch, tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("event_naming: [unclosed\n")
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", bad)

    for response in (
        client.get("/governance/profile"),
        client.post("/requests/raw", json=_raw_body()),
    ):
        assert response.status_code == 500
        # A clean, fixed message: no file path, nothing from settings.
        assert response.json()["detail"] == (
            "the active governance profile could not be loaded"
        )


def test_business_value_is_required(client):
    body = _raw_body()
    del body["business_value"]
    assert client.post("/requests/raw", json=body).status_code == 422
    assert (
        client.post("/requests/raw", json=_raw_body(business_value="")).status_code
        == 422
    )

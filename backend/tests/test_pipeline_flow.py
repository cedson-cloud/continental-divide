"""Natural-language intake through the persisted pipeline.

Deterministic stub interpreters stand in for the model's output, so the full audit
trail (intake -> model_interpreted -> schema_parsed -> rules_evaluated -> routed ->
... -> published) is reproducible offline without an API key or credits. The pipeline
code exercised here is identical to the HTTP route's.
"""

import json
from pathlib import Path

import pytest

from app.governance import load_profile
from app.interpreter import Interpretation
from app.pipeline import PiiAcknowledgmentRequired, decide, interpret_intake
from app.publisher import get_publisher

MODEL = "claude-sonnet-4-6"
TEMPLATES = Path(__file__).resolve().parents[2] / "governance" / "templates"


def stub_cart(_raw: str, **_) -> Interpretation:
    definition = {
        "name": "Cart Cleared",
        "category": "Core Ordering",
        "description": "Fired when a shopper empties their entire cart in one action.",
        "properties": [{"name": "cart_id", "type": "string", "required": True}],
    }
    return Interpretation(MODEL, definition, json.dumps(definition), None)


def stub_newsletter(_raw: str, **_) -> Interpretation:
    definition = {
        "name": "Newsletter Subscribed",
        "category": "Core Ordering",
        "description": "Fired when someone subscribes to the newsletter.",
        "properties": [{"name": "email", "type": "string", "required": True}],
    }
    return Interpretation(MODEL, definition, json.dumps(definition), None)


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def test_clean_intake_routes_then_approve_publishes(storage):
    rid = interpret_intake(
        "track when a shopper empties their entire cart", storage, interpret_fn=stub_cart
    )

    request = storage.get_request(rid)
    assert request["status"] == "pending_approval"
    assert request["parsed_definition"]["name"] == "Cart Cleared"
    assert _steps(storage, rid) == [
        "intake_received",
        "model_interpreted",
        "schema_parsed",
        "rules_evaluated",
        "routed",
    ]

    result = decide(rid, "approve", storage, get_publisher(), note="looks good")
    assert result is not None
    assert result.confluence_doc["id"]
    assert result.jira_ticket["key"]

    request = storage.get_request(rid)
    assert request["status"] == "published"
    assert request["published_artifact"]["publisher"] == result.publisher
    assert _steps(storage, rid) == [
        "intake_received",
        "model_interpreted",
        "schema_parsed",
        "rules_evaluated",
        "routed",
        "decision_received",
        "published",
    ]


def test_pii_intake_is_flagged_and_gated_on_acknowledgment(storage):
    rid = interpret_intake(
        "track when someone subscribes to our newsletter and capture their email address",
        storage,
        interpret_fn=stub_newsletter,
    )

    request = storage.get_request(rid)
    assert request["status"] == "pending_approval"
    assert request["pii_flagged"] is True
    assert request["pii_details"] == "email -> email"

    with pytest.raises(PiiAcknowledgmentRequired):
        decide(rid, "approve", storage, get_publisher())

    decide(rid, "approve", storage, get_publisher(), pii_acknowledged=True)
    request = storage.get_request(rid)
    assert request["status"] == "published"
    assert "pii_acknowledged" in _steps(storage, rid)


def test_drafting_and_evaluation_record_the_same_profile(storage):
    profile = load_profile(TEMPLATES / "segment-ecommerce.yaml")
    rid = interpret_intake(
        "track when a shopper empties their entire cart",
        storage,
        interpret_fn=stub_cart,
        profile=profile,
    )

    entries = {entry["step"]: entry["detail"] for entry in storage.get_audit_log(rid)}
    assert entries["model_interpreted"]["profile"] == "segment-ecommerce"
    assert entries["model_interpreted"]["profile"] == entries["rules_evaluated"]["profile"]

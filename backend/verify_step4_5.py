"""Step 4.5 verification: natural-language intake through the persisted pipeline.

The HTTP route calls the real Anthropic interpreter (key from ANTHROPIC_API_KEY). This
harness injects deterministic stub interpreters that stand in for the model's output, so
the full audit trail (intake -> model_interpreted -> schema_parsed -> rules_evaluated ->
routed -> ... -> published) is reproducible offline without an API key or credits. The
pipeline code exercised here is identical to the route's.
"""

from __future__ import annotations

import json

from app.interpreter import Interpretation
from app.pipeline import decide, interpret_intake
from app.publisher import get_publisher
from app.storage import reset_storage

MODEL = "claude-sonnet-4-6"


def stub_cart(_raw: str) -> Interpretation:
    definition = {
        "name": "Cart Cleared",
        "category": "Core Ordering",
        "description": "Fired when a shopper empties their entire cart in one action.",
        "properties": [{"name": "cart_id", "type": "string", "required": True}],
    }
    return Interpretation(MODEL, definition, json.dumps(definition), None)


def stub_newsletter(_raw: str) -> Interpretation:
    definition = {
        "name": "Newsletter Subscribed",
        "category": "Core Ordering",
        "description": "Fired when someone subscribes to the newsletter.",
        "properties": [{"name": "email", "type": "string", "required": True}],
    }
    return Interpretation(MODEL, definition, json.dumps(definition), None)


def print_trail(storage, request_id: int) -> None:
    request = storage.get_request(request_id)
    print(f"  request {request['id']}  status: {request['status']}")
    for entry in storage.get_audit_log(request_id):
        print(f"    [{entry['created_at']}] {entry['step']}: {json.dumps(entry['detail'])}")


def main() -> None:
    storage = reset_storage()

    print("== Scenario 1: 'track when a shopper empties their entire cart' ==")
    rid = interpret_intake(
        "track when a shopper empties their entire cart", storage, interpret_fn=stub_cart
    )
    print_trail(storage, rid)
    print("  -> approve")
    decide(rid, "approve", storage, get_publisher(), note="looks good")
    print_trail(storage, rid)

    print(
        "\n== Scenario 2: 'track when someone subscribes to our newsletter "
        "and capture their email address' =="
    )
    rid2 = interpret_intake(
        "track when someone subscribes to our newsletter and capture their email address",
        storage,
        interpret_fn=stub_newsletter,
    )
    print_trail(storage, rid2)


if __name__ == "__main__":
    main()

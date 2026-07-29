"""The semantic duplicate review: catalog construction, prompt builders, and the
advisory pipeline seam. Every test injects a stub for the review — nothing here (or
anywhere in the suite) makes a live Anthropic call."""

import json
from functools import partial

import pytest

from app.catalog import (
    EMPTY_RESULT_SENTENCE,
    DuplicateCandidate,
    DuplicateReview,
    _parse_candidates,
    build_duplicate_system_prompt,
    build_duplicate_user_message,
    catalog_entries,
)
from app.interpreter import Interpretation
from app.models import EventDefinition
from app.pipeline import (
    DuplicateAcknowledgmentRequired,
    decide,
    ingest_raw_definition,
    interpret_intake,
    submit_request,
)
from app.publisher import get_publisher
from app.rules import load_plan

MODEL = "claude-sonnet-4-6"

BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

CANDIDATE = DuplicateCandidate(
    existing_event="Product Added to Wishlist",
    category="Wishlisting",
    reason=(
        "Both fire when a shopper saves a product for later; bookmarking and "
        "wishlisting describe the same behavior under different names."
    ),
    confidence="high",
)


def stub_interpret(_raw, **_):
    return Interpretation(MODEL, BOOKMARKED, json.dumps(BOOKMARKED), None)


def stub_one_candidate(_definition, **_):
    return DuplicateReview(MODEL, [CANDIDATE], '{"candidates": [...]}')


def stub_no_candidates(_definition, **_):
    return DuplicateReview(MODEL)


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _entry(storage, request_id, step):
    return next(
        e for e in storage.get_audit_log(request_id) if e["step"] == step
    )


# --- catalog and prompts ---------------------------------------------------------

def test_catalog_has_28_described_entries():
    entries = catalog_entries()
    assert len(entries) == 28
    assert all(entry.description for entry in entries)


def test_every_plan_event_has_a_nonempty_description():
    # Guards the plan file itself, so an event added without a description fails.
    plan = load_plan()
    for category, events in plan["categories"].items():
        for event in events:
            assert event.get("description"), (
                f"event '{event.get('name')}' in category '{category}' "
                "has no description"
            )


def test_system_prompt_names_every_event_and_permits_an_empty_answer():
    prompt = build_duplicate_system_prompt(catalog_entries())
    for entry in catalog_entries():
        assert entry.name in prompt
    assert EMPTY_RESULT_SENTENCE in prompt


def test_user_message_carries_the_draft():
    message = build_duplicate_user_message(EventDefinition.model_validate(BOOKMARKED))
    assert "Product Bookmarked" in message
    assert "Wishlisting" in message
    assert "product_id" in message


def test_system_prompt_scopes_the_job_to_semantic_duplicates():
    prompt = build_duplicate_system_prompt(catalog_entries())
    assert "ALREADY handled by a deterministic engine" in prompt


def test_system_prompt_states_the_model_is_not_authoritative():
    prompt = build_duplicate_system_prompt(catalog_entries())
    assert "recorded as inference, not fact" in prompt


# --- output parsing --------------------------------------------------------------

def test_parse_candidates_accepts_a_valid_object():
    payload = json.dumps({"candidates": [CANDIDATE.model_dump()]})
    candidates, error = _parse_candidates(payload)
    assert error is None
    assert candidates == [CANDIDATE]


def test_parse_candidates_rejects_non_json():
    candidates, error = _parse_candidates("the draft looks novel to me")
    assert candidates == []
    assert "not valid JSON" in error


def test_parse_candidates_rejects_a_missing_candidates_list():
    candidates, error = _parse_candidates(json.dumps({"duplicates": []}))
    assert candidates == []
    assert '"candidates" list' in error


def test_parse_candidates_rejects_a_malformed_candidate():
    bad = {**CANDIDATE.model_dump(), "confidence": "certain"}
    candidates, error = _parse_candidates(json.dumps({"candidates": [bad]}))
    assert candidates == []
    assert "expected shape" in error


# --- pipeline seam ---------------------------------------------------------------

def test_candidate_is_audited_stored_and_returned(client, storage, monkeypatch):
    monkeypatch.setattr(
        "app.routes.ingest_raw_definition",
        partial(ingest_raw_definition, duplicate_fn=stub_one_candidate),
    )
    response = client.post(
        "/requests/raw",
        json={"definition": BOOKMARKED, "business_value": "counts saved products"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["duplicate_candidates"] == [CANDIDATE.model_dump()]

    request = storage.get_request(body["id"])
    assert request["duplicate_candidates"] == [CANDIDATE.model_dump()]

    audit = _entry(storage, body["id"], "duplicate_review")
    assert audit["detail"]["model"] == MODEL
    assert audit["detail"]["candidates"] == [CANDIDATE.model_dump()]


def test_no_candidates_leaves_behaviour_unchanged(storage):
    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_no_candidates,
    )
    request = storage.get_request(rid)
    assert request["status"] == "draft"
    assert request["duplicate_candidates"] == []
    assert _entry(storage, rid, "duplicate_review")["detail"]["candidates"] == []

    # No candidates, no gate: submission needs no note and approval no acknowledgment.
    submit_request(rid, storage)
    decide(rid, "approve", storage, get_publisher())
    assert storage.get_request(rid)["status"] == "published"


def test_raising_review_never_blocks_routing(storage):
    def stub_raises(_definition, **_):
        raise RuntimeError("model service down")

    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_raises,
    )
    request = storage.get_request(rid)
    assert request["status"] == "draft"
    assert request["duplicate_candidates"] == []
    assert _entry(storage, rid, "duplicate_review_failed")["detail"] == {
        "error": "model service down"
    }
    assert "duplicate_review" not in _steps(storage, rid)


def test_raw_path_skips_the_review_entirely(client, storage):
    # /requests/raw is the deliberately model-free path: no review call is made and
    # neither duplicate audit step is written.
    response = client.post(
        "/requests/raw",
        json={"definition": BOOKMARKED, "business_value": "counts saved products"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    steps = _steps(storage, response.json()["id"])
    assert "duplicate_review" not in steps
    assert "duplicate_review_failed" not in steps


def test_raising_review_still_returns_200_over_http(client, storage, monkeypatch):
    def stub_raises(_definition, **_):
        raise RuntimeError("model service down")

    monkeypatch.setattr(
        "app.routes.interpret_intake",
        partial(interpret_intake, interpret_fn=stub_interpret, duplicate_fn=stub_raises),
    )
    response = client.post(
        "/requests",
        json={
            "raw_intake_text": "track when a shopper bookmarks a product",
            "business_value": "counts saved products",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert "duplicate_review_failed" in _steps(storage, response.json()["id"])


def test_unreadable_review_output_is_recorded_and_routes_normally(storage):
    def stub_unparseable(_definition, **_):
        return DuplicateReview(MODEL, [], "not json", "model output was not valid JSON")

    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_unparseable,
    )
    assert storage.get_request(rid)["status"] == "draft"
    audit = _entry(storage, rid, "duplicate_review")
    assert audit["detail"]["candidates"] == []
    assert audit["detail"]["parse_error"] == "model output was not valid JSON"


def test_rejected_draft_never_invokes_the_review(storage):
    calls = []

    def counting_stub(definition, **_):
        calls.append(definition)
        return DuplicateReview(MODEL)

    rid = ingest_raw_definition(
        "bad name",
        {"name": "add_to_cart", "category": "Core Ordering", "properties": []},
        storage,
        duplicate_fn=counting_stub,
    )
    assert storage.get_request(rid)["status"] == "rejected"
    assert calls == []


def test_approval_with_candidates_requires_acknowledgment(client, storage):
    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_one_candidate,
    )
    submit_request(rid, storage, duplicate_note="bookmarking is a distinct behavior")

    with pytest.raises(DuplicateAcknowledgmentRequired):
        decide(rid, "approve", storage, get_publisher())

    response = client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "approver_name": "Sam"}
    )
    assert response.status_code == 422

    response = client.post(
        f"/requests/{rid}/decision",
        json={
            "decision": "approve",
            "approver_name": "Sam",
            "duplicate_acknowledged": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"

    acknowledged = _entry(storage, rid, "duplicate_acknowledged")
    assert "Sam" in acknowledged["detail"]["message"]
    assert acknowledged["detail"]["candidates"] == ["Product Added to Wishlist"]

"""The semantic catalog review: catalog construction, prompt builders, and the
advisory pipeline seam. Every test injects a stub for the review — nothing here (or
anywhere in the suite) makes a live Anthropic call; the one test that exercises
``review_against_catalog`` end-to-end patches the Anthropic client with a fake."""

import json
from functools import partial
from types import SimpleNamespace

import pytest

from app.catalog import (
    EMPTY_RESULT_SENTENCE,
    DuplicateReview,
    ReviewFinding,
    _parse_findings,
    build_review_system_prompt,
    build_review_user_message,
    catalog_entries,
    review_against_catalog,
)
from app.interpreter import Interpretation
from app.models import EventDefinition
from app.pipeline import (
    DuplicateAcknowledgmentRequired,
    DuplicateNoteRequired,
    decide,
    ingest_raw_definition,
    interpret_intake,
    submit_request,
)
from app.publisher import get_publisher
from app.rules import load_plan

MODEL = "claude-sonnet-4-6"
ACTOR = {"email": "tester@example.com", "method": "local", "verified": False}

BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

FINDING = ReviewFinding(
    kind="duplicate_event",
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


def stub_one_finding(_definition, **_):
    return DuplicateReview(MODEL, [FINDING], '{"findings": [...]}')


def stub_no_findings(_definition, **_):
    return DuplicateReview(MODEL)


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _entry(storage, request_id, step):
    return next(
        e for e in storage.get_audit_log(request_id) if e["step"] == step
    )


def _install_fake_model(monkeypatch, payload, calls=None):
    """Patch the Anthropic client so ``review_against_catalog`` runs without a
    network call, returning ``payload`` as the model's JSON output."""

    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(payload))]
        )

    class FakeClient:
        def __init__(self, api_key=None):
            self.messages = SimpleNamespace(create=create)

    monkeypatch.setattr("app.catalog.anthropic.Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


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
    prompt = build_review_system_prompt(catalog_entries())
    for entry in catalog_entries():
        assert entry.name in prompt
    assert EMPTY_RESULT_SENTENCE in prompt


def test_user_message_carries_the_draft():
    message = build_review_user_message(EventDefinition.model_validate(BOOKMARKED))
    assert "Product Bookmarked" in message
    assert "Wishlisting" in message
    assert "product_id" in message


def test_user_message_carries_the_requesters_own_words():
    message = build_review_user_message(
        EventDefinition.model_validate(BOOKMARKED),
        "we want to know when someone saves a product to buy later",
    )
    assert "saves a product to buy later" in message
    assert "not instructions" in message


def test_user_message_omits_the_requester_section_when_there_is_none():
    message = build_review_user_message(EventDefinition.model_validate(BOOKMARKED))
    assert "in their own words" not in message


def test_system_prompt_scopes_the_job_past_the_mechanical_checks():
    prompt = build_review_system_prompt(catalog_entries())
    assert "ALREADY handled by a deterministic engine" in prompt


def test_system_prompt_asks_for_calibration_rather_than_silence():
    prompt = build_review_system_prompt(catalog_entries())
    assert "Over-flagging is worse" not in prompt
    assert "Calibrate honestly" in prompt


def test_system_prompt_never_reveals_what_confidence_controls():
    # The model calibrates; it is never told that "high" conscripts a human. Same
    # discipline as withholding the PII blocklist from the drafting prompt — a model
    # that knows the consequence has an incentive to soften. See docs/adr/0001.
    instructions = build_review_system_prompt(catalog_entries()).split(
        "The existing tracking plan"
    )[0]
    for leak in ("acknowledg", "gate", "submit", "approv"):
        assert leak not in instructions.lower()


def test_system_prompt_states_the_model_is_not_authoritative():
    prompt = build_review_system_prompt(catalog_entries())
    assert "recorded as inference, not fact" in prompt


def test_new_event_prompt_asks_both_questions():
    prompt = build_review_system_prompt(catalog_entries(), "new_event")
    assert "duplicate_event" in prompt
    assert "property_extension" in prompt
    assert "property_already_exists" not in prompt.split("Return ONLY")[0]


def test_property_prompt_forbids_reporting_the_named_event():
    prompt = build_review_system_prompt(
        catalog_entries(), "new_property_on_existing", "Product Added to Wishlist"
    )
    assert 'never report it with kind "duplicate_event"' in prompt
    assert "property_already_exists" in prompt
    assert '"Product Added to Wishlist"' in prompt
    assert EMPTY_RESULT_SENTENCE in prompt


# --- output parsing --------------------------------------------------------------

def test_parse_findings_accepts_a_valid_object():
    payload = json.dumps({"findings": [FINDING.model_dump()]})
    findings, error = _parse_findings(payload)
    assert error is None
    assert findings == [FINDING]


def test_parse_findings_rejects_non_json():
    findings, error = _parse_findings("the draft looks novel to me")
    assert findings == []
    assert "not valid JSON" in error


def test_parse_findings_rejects_a_missing_findings_list():
    findings, error = _parse_findings(json.dumps({"duplicates": []}))
    assert findings == []
    assert '"findings" list' in error


def test_parse_findings_rejects_a_malformed_finding():
    bad = {**FINDING.model_dump(), "confidence": "certain"}
    findings, error = _parse_findings(json.dumps({"findings": [bad]}))
    assert findings == []
    assert "expected shape" in error


# --- the review itself (Anthropic client faked, no network) ----------------------

def test_property_request_never_returns_its_named_event_as_a_duplicate(monkeypatch):
    # Even a model that ignores the prompt and calls the named event a duplicate
    # cannot get that finding past the deterministic guard.
    payload = {
        "findings": [
            {
                "kind": "duplicate_event",
                "existing_event": "Product Added to Wishlist",
                "category": "Wishlisting",
                "property_names": [],
                "reason": "The draft describes the same wishlist behavior.",
                "confidence": "high",
            },
            {
                "kind": "property_already_exists",
                "existing_event": "Product Added to Wishlist",
                "category": "Wishlisting",
                "property_names": ["wishlist_name"],
                "reason": (
                    "The event already carries wishlist_id; a wishlist_name that "
                    "identifies the same list duplicates its meaning."
                ),
                "confidence": "medium",
            },
        ]
    }
    _install_fake_model(monkeypatch, payload)
    draft = {
        "name": "Product Added to Wishlist",
        "category": "Wishlisting",
        "description": "Adds the wishlist name to the existing event.",
        "properties": [{"name": "wishlist_name", "type": "string", "required": False}],
    }
    review = review_against_catalog(
        EventDefinition.model_validate(draft),
        request_kind="new_property_on_existing",
        existing_event="Product Added to Wishlist",
    )
    assert review.parse_error is None
    assert [f.kind for f in review.findings] == ["property_already_exists"]


def test_property_request_prompt_reaches_the_model(monkeypatch):
    calls = []
    _install_fake_model(monkeypatch, {"findings": []}, calls)
    review = review_against_catalog(
        EventDefinition.model_validate(BOOKMARKED),
        request_kind="new_property_on_existing",
        existing_event="Product Added to Wishlist",
    )
    assert review.findings == []
    assert len(calls) == 1
    assert 'never report it with kind "duplicate_event"' in calls[0]["system"]


def test_intake_sends_the_requesters_words_and_withholds_business_value(
    storage, monkeypatch
):
    # Behaviour is the reviewer's question; motive is not. Two teams instrumenting the
    # same action for different reasons still need one event, so business value is the
    # argument that would talk a model out of a correct finding. See docs/adr/0001.
    calls = []
    _install_fake_model(monkeypatch, {"findings": []}, calls)
    interpret_intake(
        "track it when a shopper bookmarks a product to revisit",
        storage,
        interpret_fn=stub_interpret,
        business_value="the growth team needs it for the Q3 retention target",
    )
    assert len(calls) == 1
    sent = calls[0]["messages"][0]["content"]
    assert "bookmarks a product to revisit" in sent
    assert "Q3 retention target" not in sent
    assert "retention" not in calls[0]["system"]


# --- pipeline seam ---------------------------------------------------------------

def test_finding_is_audited_stored_and_returned(client, storage, monkeypatch):
    monkeypatch.setattr(
        "app.routes.ingest_raw_definition",
        partial(ingest_raw_definition, duplicate_fn=stub_one_finding),
    )
    response = client.post(
        "/requests/raw",
        json={"definition": BOOKMARKED, "business_value": "counts saved products"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["duplicate_candidates"] == [FINDING.model_dump()]

    request = storage.get_request(body["id"])
    assert request["duplicate_candidates"] == [FINDING.model_dump()]

    audit = _entry(storage, body["id"], "duplicate_review")
    assert audit["detail"]["model"] == MODEL
    assert audit["detail"]["findings"] == [FINDING.model_dump()]


def test_an_exact_duplicate_cannot_be_approved_unacknowledged_on_the_raw_path(
    client, storage
):
    # The inversion this seam was built to fix: a name known for certain to exist used
    # to publish with nobody acknowledging it, while a model's hunch stopped the line
    # twice. The raw path makes no model call, so the engine is the only witness.
    duplicate = {**BOOKMARKED, "name": "Product Added", "category": "Core Ordering"}
    created = client.post(
        "/requests/raw",
        json={"definition": duplicate, "business_value": "counts adds"},
    )
    assert created.status_code == 200
    rid = created.json()["id"]
    assert created.json()["status"] == "flagged_duplicate"
    assert storage.get_request(rid)["duplicate_candidates"] in (None, [])

    refused = client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "approver_name": "Sam"}
    )
    assert refused.status_code == 422
    assert "already exists in the tracking plan" in refused.json()["detail"]

    approved = client.post(
        f"/requests/{rid}/decision",
        json={
            "decision": "approve",
            "approver_name": "Sam",
            "findings_acknowledged": True,
        },
    )
    assert approved.status_code == 200
    entry = _entry(storage, rid, "findings_acknowledged")
    assert "already exists in the tracking plan" in entry["detail"]["message"]


def test_a_near_duplicate_cannot_be_approved_unacknowledged_on_the_raw_path(
    client, storage
):
    # The raw path has no requester step, so the note gate in submit_request never runs
    # and the approver is the only human who sees the collision. Gating only the exact
    # tier here left the near tier silent — a deterministic duplicate published with
    # nobody on record, which is the inversion ADR 0001 exists to forbid.
    near = {**BOOKMARKED, "name": "Products Added", "category": "Core Ordering"}
    created = client.post(
        "/requests/raw", json={"definition": near, "business_value": "counts adds"}
    )
    rid = created.json()["id"]
    assert created.json()["status"] == "flagged_duplicate"

    refused = client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "approver_name": "Sam"}
    )
    assert refused.status_code == 422
    assert "written differently" in refused.json()["detail"]

    approved = client.post(
        f"/requests/{rid}/decision",
        json={
            "decision": "approve",
            "approver_name": "Sam",
            "findings_acknowledged": True,
        },
    )
    assert approved.status_code == 200
    entry = _entry(storage, rid, "findings_acknowledged")
    assert "written differently" in entry["detail"]["message"]


def test_a_near_duplicate_name_gates_submission_on_a_note(storage):
    near = {**BOOKMARKED, "name": "Products Added", "category": "Core Ordering"}

    def stub_near(_raw, **_):
        return Interpretation(MODEL, near, json.dumps(near), None)

    rid = interpret_intake(
        "track when products get added", storage, interpret_fn=stub_near,
        duplicate_fn=stub_no_findings,
    )
    assert storage.get_request(rid)["status"] == "draft"
    with pytest.raises(DuplicateNoteRequired) as excinfo:
        submit_request(rid, storage)
    assert "written differently" in str(excinfo.value)

    submit_request(rid, storage, duplicate_note="plural is the bulk-add variant")
    assert storage.get_request(rid)["status"] == "flagged_duplicate"


def test_a_finding_below_high_confidence_is_shown_but_gates_nothing(client, storage):
    hunch = ReviewFinding(
        kind="duplicate_event",
        existing_event="Product Added to Wishlist",
        category="Wishlisting",
        reason="Bookmarking might be wishlisting, but the plan may intend them apart.",
        confidence="low",
    )

    def stub_low(_definition, **_):
        return DuplicateReview(MODEL, [hunch], '{"findings": [...]}')

    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_low,
    )
    # Visible to the requester...
    assert storage.get_request(rid)["duplicate_candidates"] == [hunch.model_dump()]
    # ...but costs nobody a required action, at either gate.
    submit_request(rid, storage)
    response = client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "approver_name": "Sam"}
    )
    assert response.status_code == 200


def test_no_findings_leaves_behaviour_unchanged(storage):
    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_no_findings,
    )
    request = storage.get_request(rid)
    assert request["status"] == "draft"
    assert request["duplicate_candidates"] == []
    assert _entry(storage, rid, "duplicate_review")["detail"]["findings"] == []

    # No findings, no gate: submission needs no note and approval no acknowledgment.
    submit_request(rid, storage)
    decide(rid, "approve", storage, get_publisher())
    assert storage.get_request(rid)["status"] == "published"


def test_review_receives_the_request_kind_and_named_event(storage):
    seen = {}

    def recording_stub(_definition, **kwargs):
        seen.update(kwargs)
        return DuplicateReview(MODEL)

    interpret_intake(
        "add the wishlist name to the wishlist event",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=recording_stub,
        request_kind="new_property_on_existing",
        existing_event="Product Added to Wishlist",
    )
    assert seen["request_kind"] == "new_property_on_existing"
    assert seen["existing_event"] == "Product Added to Wishlist"


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
        "error": "model service down",
        "actor": ACTOR,
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
            "submitter_name": "Ada",
            "submitter_team": "Product",
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
    assert audit["detail"]["findings"] == []
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


def test_approval_with_findings_requires_acknowledgment(client, storage):
    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_one_finding,
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
            "findings_acknowledged": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"

    acknowledged = _entry(storage, rid, "findings_acknowledged")
    assert "Sam" in acknowledged["detail"]["message"]
    assert acknowledged["detail"]["candidates"] == ["Product Added to Wishlist"]


def test_approval_gate_names_property_extension_not_duplicate(client, storage):
    extension = ReviewFinding(
        kind="property_extension",
        existing_event="Product Added",
        category="Core Ordering",
        property_names=["product_id"],
        reason=(
            "Bookmarking captures a property of an add interaction the plan already "
            "tracks on Product Added."
        ),
        confidence="high",
    )

    def stub_extension(_definition, **_):
        return DuplicateReview(MODEL, [extension], '{"findings": [...]}')

    rid = interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_extension,
    )
    # A property_extension finding alone never gates submission on a note.
    submit_request(rid, storage)

    response = client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "approver_name": "Sam"}
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "duplicate" not in detail.lower()
    assert "possible property extensions" in detail

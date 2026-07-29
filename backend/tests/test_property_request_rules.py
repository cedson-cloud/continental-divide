"""The duplicate rule on new_property_on_existing requests.

A property request drafts against the event the requester named, so its drafted
name is supposed to match that event. The deterministic duplicate rule treats
that match as expected — recorded as a passing check, never flagged — while a
match against any other plan event still flags, and the default path (no
request_kind) is untouched.
"""

from app.models import Decision, EventDefinition
from app.pipeline import ingest_raw_definition
from app.rules import evaluate


def _event(name="Product Added", category="Core Ordering", properties=("gift_wrap",)):
    return EventDefinition(
        name=name,
        category=category,
        description="d",
        properties=[{"name": p, "type": "string"} for p in properties],
    )


def _check(evaluation, rule):
    return next(c for c in evaluation.checks if c.rule == rule)


def test_property_request_named_after_its_event_is_not_flagged():
    evaluation = evaluate(
        _event(name="Product Added"),
        request_kind="new_property_on_existing",
        existing_event="Product Added",
    )
    assert evaluation.decision == Decision.pending_approval
    assert evaluation.flags == []
    duplicate = _check(evaluation, "duplicate")
    assert duplicate.passed is True
    assert "the event this property is being added to" in duplicate.detail


def test_property_request_matching_a_different_plan_event_still_flags():
    evaluation = evaluate(
        _event(name="Order Completed"),
        request_kind="new_property_on_existing",
        existing_event="Product Added",
    )
    assert evaluation.decision == Decision.flagged_duplicate
    assert evaluation.flags == [
        "'Order Completed' already exists in the tracking plan"
    ]


def test_name_comparison_strips_surrounding_whitespace():
    evaluation = evaluate(
        _event(name="Product Added"),
        request_kind="new_property_on_existing",
        existing_event="  Product Added  ",
    )
    assert evaluation.decision == Decision.pending_approval
    assert evaluation.flags == []


def test_other_request_kinds_get_no_exemption():
    evaluation = evaluate(
        _event(name="Product Added"),
        request_kind="new_event",
        existing_event="Product Added",
    )
    assert evaluation.decision == Decision.flagged_duplicate


def test_existing_event_alone_gets_no_exemption():
    evaluation = evaluate(_event(name="Product Added"), existing_event="Product Added")
    assert evaluation.decision == Decision.flagged_duplicate


def test_pipeline_passes_kind_and_event_through_to_the_rules(storage):
    request_id = ingest_raw_definition(
        "add gift_wrap to Product Added",
        _event(name="Product Added").model_dump(),
        storage,
        request_kind="new_property_on_existing",
        existing_event="Product Added",
    )
    request = storage.get_request(request_id)
    assert request["status"] == Decision.pending_approval.value

    rules_entry = next(
        e
        for e in storage.get_audit_log(request_id)
        if e["step"] == "rules_evaluated"
    )
    duplicate = next(
        c for c in rules_entry["detail"]["checks"] if c["rule"] == "duplicate"
    )
    assert duplicate["passed"] is True
    assert "the event this property is being added to" in duplicate["detail"]
    assert rules_entry["detail"]["flags"] == []

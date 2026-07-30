"""The two ways out of a naming rejection.

Rename supersedes rather than mutates and costs exactly one model call — the catalog
review — because the original's parsed definition is reused with only the name
replaced. Dispute costs nothing at all: it records a disagreement and changes no
status, no profile, and no file. Interpreters and reviews are stubs throughout;
nothing here makes a live call.
"""

import json
from functools import partial
from pathlib import Path

import pytest

from app.catalog import DuplicateReview, ReviewFinding
from app.governance import load_active_profile
from app.interpreter import Interpretation
from app.pipeline import InvalidTransition, RequestNotFound, interpret_intake
from app.recourse import (
    NameNotOffered,
    RuleNotFailing,
    profile_digest,
    record_rule_dispute,
    rename_and_resubmit,
)

MODEL = "claude-sonnet-4-6"
GOVERNANCE_DIR = Path(__file__).parents[2] / "governance"

REJECTED_NAME = "Back in Stock Alert Requested"
COMPLIANT_NAME = "Back In Stock Alert Requested"

# What the model drafted on request #11: faithful to the intake, and refused by the
# convention on the word "in".
BACK_IN_STOCK = {
    "name": REJECTED_NAME,
    "category": "Browsing",
    "description": "Shopper asked to be emailed when a sold-out product returns.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}


def stub_interpret(_raw, **_):
    return Interpretation(MODEL, BACK_IN_STOCK, json.dumps(BACK_IN_STOCK), None)


def stub_no_findings(_definition, **_):
    return DuplicateReview(MODEL)


class CountingReview:
    """A review stub that records every call, so 'exactly one model call' is an
    assertion rather than a comment."""

    def __init__(self, findings=None):
        self.calls: list[str] = []
        self._findings = findings or []

    def __call__(self, definition, **_):
        self.calls.append(definition.name)
        return DuplicateReview(MODEL, list(self._findings), '{"findings": [...]}')


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _entry(storage, request_id, step):
    return next(e for e in storage.get_audit_log(request_id) if e["step"] == step)


def _rejected(storage, duplicate_fn=stub_no_findings):
    """Request #11, reproduced: a faithful draft the naming rule refuses."""
    rid = interpret_intake(
        "when someone asks to be emailed if a sold-out product comes back in stock",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=duplicate_fn,
        submitter_name="Sam",
        submitter_team="Marketing",
        call_type="track",
        side="Client",
        business_value="win back demand we currently lose to stockouts",
        needed_by="2026-08-15",
        destinations=["engagement"],
    )
    assert storage.get_request(rid)["status"] == "rejected"
    return rid


# --- rename ----------------------------------------------------------------------

def test_rename_creates_a_new_request_linked_in_both_directions(storage):
    rid = _rejected(storage)
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)
    assert nid != rid

    new = storage.get_request(nid)
    original = storage.get_request(rid)
    assert new["parsed_definition"]["name"] == COMPLIANT_NAME
    # Only the name changed: the rest of the definition is the original's, reused
    # rather than re-drafted.
    assert new["parsed_definition"] == {
        **original["parsed_definition"],
        "name": COMPLIANT_NAME,
    }
    assert new["parsed_definition"]["description"] == BACK_IN_STOCK["description"]
    # Intake text and metadata travel with it.
    assert new["raw_intake_text"] == original["raw_intake_text"]
    assert new["submitter_name"] == "Sam"
    assert new["submitter_team"] == "Marketing"
    assert new["business_value"] == "win back demand we currently lose to stockouts"
    assert new["needed_by"] == "2026-08-15"
    assert new["destinations"] == ["engagement"]
    # The rules now pass, so it lands at draft for the requester's own confirmation.
    assert new["status"] == "draft"

    assert _entry(storage, rid, "superseded_by")["detail"] == {
        "new_request_id": nid,
        "new_name": COMPLIANT_NAME,
    }
    assert _entry(storage, nid, "supersedes")["detail"] == {
        "original_request_id": rid,
        "original_name": REJECTED_NAME,
    }


def test_the_audit_entry_records_the_consent_and_the_rule_that_failed(storage):
    rid = _rejected(storage)
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)

    detail = _entry(storage, nid, "renamed_and_resubmitted")["detail"]
    assert detail["original_request_id"] == rid
    assert detail["original_name"] == REJECTED_NAME
    assert detail["new_name"] == COMPLIANT_NAME
    assert detail["failed_rule"] == "event_naming"
    assert detail["profile"] == load_active_profile().name

    # The new request's trail is a normal one apart from that entry — and the rules
    # it re-ran now pass.
    steps = _steps(storage, nid)
    assert steps[:3] == ["intake_received", "renamed_and_resubmitted", "schema_parsed"]
    for step in ("rules_evaluated", "duplicate_review", "routed"):
        assert step in steps
    checks = _entry(storage, nid, "rules_evaluated")["detail"]["checks"]
    naming = next(c for c in checks if c["rule"] == "event_naming")
    assert naming["passed"] is True


def test_the_original_is_never_edited(storage):
    rid = _rejected(storage)
    before = storage.get_request(rid)
    rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)

    after = storage.get_request(rid)
    assert after["status"] == "rejected"
    assert after["parsed_definition"] == before["parsed_definition"]
    assert after["parsed_definition"]["name"] == REJECTED_NAME
    # A rejected request cannot be renamed twice into two live replacements.
    assert _steps(storage, rid).count("superseded_by") == 1


def test_a_name_outside_the_server_derived_set_is_refused(client, storage):
    rid = _rejected(storage)

    # Compliant under the convention, but not a repair of THIS name.
    with pytest.raises(NameNotOffered):
        rename_and_resubmit(rid, "Cart Cleared", storage, duplicate_fn=stub_no_findings)
    # The naive Title-Case repair of a different failure, also never offered here.
    with pytest.raises(NameNotOffered):
        rename_and_resubmit(
            rid, "Item Saved For Later", storage, duplicate_fn=stub_no_findings
        )

    response = client.post(f"/requests/{rid}/rename", json={"new_name": "Cart Cleared"})
    assert response.status_code == 422
    assert storage.get_request(rid)["status"] == "rejected"
    assert "superseded_by" not in _steps(storage, rid)


def test_the_endpoint_offers_the_candidate_set_it_will_accept(client, storage):
    rid = _rejected(storage)
    detail = client.get(f"/requests/{rid}").json()
    assert detail["name_suggestions"] == [COMPLIANT_NAME]

    # A request nothing rejected on naming has nothing to offer.
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)
    assert client.get(f"/requests/{nid}").json()["name_suggestions"] == []


def test_exactly_one_model_call_per_rename_and_it_is_the_review(storage, monkeypatch):
    rid = _rejected(storage)

    def never(*_args, **_kwargs):
        raise AssertionError("interpretation must not re-run on a rename")

    monkeypatch.setattr("app.interpreter.interpret", never)
    monkeypatch.setattr("app.pipeline.interpret", never)

    review = CountingReview()
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=review)

    # One call, and it is the catalog review, on the renamed definition.
    assert review.calls == [COMPLIANT_NAME]
    # Nothing re-drafted: the new request has no model_interpreted entry, and the
    # only model step in its trail is the review.
    steps = _steps(storage, nid)
    assert "model_interpreted" not in steps
    assert steps.count("duplicate_review") == 1


def test_rename_refused_unless_the_naming_rule_rejected_it(client, storage):
    with pytest.raises(RequestNotFound):
        rename_and_resubmit(9999, COMPLIANT_NAME, storage)
    assert (
        client.post("/requests/9999/rename", json={"new_name": COMPLIANT_NAME}).status_code
        == 404
    )

    # A draft the rules accepted is not a rejection to recover from.
    rid = _rejected(storage)
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)
    with pytest.raises(InvalidTransition):
        rename_and_resubmit(nid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)
    response = client.post(f"/requests/{nid}/rename", json={"new_name": COMPLIANT_NAME})
    assert response.status_code == 409


def test_rename_over_http_lands_on_the_new_request(client, storage, monkeypatch):
    rid = _rejected(storage)
    monkeypatch.setattr(
        "app.routes.rename_and_resubmit",
        partial(rename_and_resubmit, duplicate_fn=stub_no_findings),
    )

    response = client.post(f"/requests/{rid}/rename", json={"new_name": COMPLIANT_NAME})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] != rid
    assert body["status"] == "draft"
    assert client.get(f"/requests/{body['id']}").json()["parsed_definition"]["name"] == (
        COMPLIANT_NAME
    )


def test_a_review_finding_on_the_renamed_request_still_reaches_the_requester(storage):
    rid = _rejected(storage)
    review = CountingReview(
        [
            ReviewFinding(
                kind="duplicate_event",
                existing_event="Product Added to Wishlist",
                category="Wishlisting",
                reason="Both fire when a shopper wants to hear about a product later.",
                confidence="medium",
            )
        ]
    )
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=review)
    assert len(storage.get_request(nid)["duplicate_candidates"]) == 1


# --- dispute ---------------------------------------------------------------------

def _snapshot(directory: Path):
    return sorted((p.name, p.stat().st_mtime_ns) for p in directory.iterdir())


def test_dispute_records_the_rule_the_note_and_the_profile_it_disputes(storage):
    rid = _rejected(storage)
    profile = load_active_profile()

    detail = record_rule_dispute(
        rid,
        "event_naming",
        "\"Back in Stock\" is a product concept here, not a verb phrase.",
        storage,
    )
    assert detail == {
        "rule": "event_naming",
        "note": '"Back in Stock" is a product concept here, not a verb phrase.',
        "profile": profile.name,
        "profile_digest": profile_digest(profile),
    }
    # A later reader knows which version of the rules was being argued with.
    assert len(detail["profile_digest"]) == 12
    assert _entry(storage, rid, "rule_disputed")["detail"] == detail


def test_dispute_changes_no_status_and_writes_no_file(client, storage):
    rid = _rejected(storage)
    before_request = storage.get_request(rid)
    before_files = (
        _snapshot(GOVERNANCE_DIR),
        _snapshot(GOVERNANCE_DIR / "templates"),
    )

    response = client.post(
        f"/requests/{rid}/dispute-rule",
        json={"rule": "event_naming", "note": "this rule is wrong for us"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    after_files = (
        _snapshot(GOVERNANCE_DIR),
        _snapshot(GOVERNANCE_DIR / "templates"),
    )
    assert after_files == before_files

    after_request = storage.get_request(rid)
    assert after_request["status"] == "rejected"
    assert after_request["parsed_definition"] == before_request["parsed_definition"]
    # The active profile is unchanged: enforcement and authoring never share a moment.
    assert client.get("/governance/profile").json()["name"] == (
        load_active_profile().name
    )


def test_dispute_must_name_a_rule_that_actually_failed(client, storage):
    rid = _rejected(storage)
    with pytest.raises(RuleNotFailing):
        record_rule_dispute(rid, "category", "the category list is too narrow", storage)
    response = client.post(
        f"/requests/{rid}/dispute-rule",
        json={"rule": "property_naming", "note": "snake_case is wrong for us"},
    )
    assert response.status_code == 422
    assert "rule_disputed" not in _steps(storage, rid)


def test_a_dispute_needs_an_argument_in_it(client, storage):
    rid = _rejected(storage)
    for body in ({"rule": "event_naming"}, {"rule": "event_naming", "note": ""}):
        assert client.post(f"/requests/{rid}/dispute-rule", json=body).status_code == 422
    assert "rule_disputed" not in _steps(storage, rid)


def test_disputes_are_listed_for_the_data_team(client, storage):
    rid = _rejected(storage)
    assert client.get("/disputes").json() == []

    client.post(
        f"/requests/{rid}/dispute-rule",
        json={"rule": "event_naming", "note": "the preposition is part of the noun"},
    )
    disputes = client.get("/disputes").json()
    assert len(disputes) == 1
    assert disputes[0]["request_id"] == rid
    assert disputes[0]["rule"] == "event_naming"
    assert disputes[0]["note"] == "the preposition is part of the noun"
    assert disputes[0]["event_name"] == REJECTED_NAME
    assert disputes[0]["profile_digest"] == profile_digest(load_active_profile())


def test_dispute_and_rename_are_independent_doors(storage):
    """Disagreeing with the rule does not block taking the compliant name, and the
    dispute survives on the original either way."""
    rid = _rejected(storage)
    record_rule_dispute(rid, "event_naming", "wrong for us", storage)
    nid = rename_and_resubmit(rid, COMPLIANT_NAME, storage, duplicate_fn=stub_no_findings)

    assert storage.get_request(nid)["status"] == "draft"
    assert "rule_disputed" in _steps(storage, rid)
    assert storage.get_request(rid)["status"] == "rejected"

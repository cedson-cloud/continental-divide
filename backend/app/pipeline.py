"""Intake-to-routing flow, persisted.

Drives a single request through interpretation, parse, deterministic rules, and routing,
writing one audit entry per state transition as it goes:

    intake_received -> model_interpreted -> schema_parsed | schema_rejected
                    -> rules_evaluated -> routed

The model only drafts (see ``interpreter.py``); the schema, the rules, and the human
approver govern. The structured ``ingest`` path is kept for offline use where the
definition is supplied directly rather than drafted by the model.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from pydantic import ValidationError

from .catalog import DuplicateReview, review_against_catalog
from .governance import GovernanceProfile, load_active_profile
from .interpreter import Interpretation, InterpreterError, interpret
from .models import Decision, EventDefinition
from .notion_publisher import push_request
from .publisher import Publisher, PublishResult
from .rules import evaluate
from .storage import Storage

DECIDABLE_STATUSES = {Decision.pending_approval.value, Decision.flagged_duplicate.value}


class RequestNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


class PiiAcknowledgmentRequired(Exception):
    pass


class DuplicateAcknowledgmentRequired(Exception):
    pass


class DuplicateNoteRequired(Exception):
    pass


class NoMatchingFinding(Exception):
    """The caller named an event that no qualifying stored finding on the request
    points at; the finding is the authority on the target, not the caller."""


class IntakeModelError(Exception):
    """The model service failed while drafting a definition; the request is persisted
    and rejected, and the caller should surface a 502."""

    def __init__(self, request_id: int, message: str) -> None:
        self.request_id = request_id
        super().__init__(message)


def _parse(candidate: dict) -> Tuple[Optional[EventDefinition], Optional[list]]:
    try:
        return EventDefinition.model_validate(candidate), None
    except ValidationError as exc:
        return None, exc.errors(include_url=False)


def _route(
    request_id: int,
    parsed: Optional[EventDefinition],
    parse_errors: Optional[list],
    storage: Storage,
    profile: Optional[GovernanceProfile] = None,
    duplicate_fn: Optional[Callable[..., DuplicateReview]] = None,
    *,
    requires_confirmation: bool = False,
) -> None:
    """Write the schema -> rules -> routed tail of the audit trail and set the final
    status. The request row and the entries that precede ``schema_parsed`` are written
    by the caller. ``profile`` is the governance profile to evaluate under; ``None``
    resolves to the active profile so offline callers enforce the same rules.

    ``requires_confirmation`` holds a request that was not rejected at ``draft``
    instead of its routed decision, so the requester can review it before it enters
    the approval queue. The ``routed`` entry still records the real decision — that
    is how :func:`submit_request` recovers it later.

    ``duplicate_fn`` is the advisory semantic catalog review (see ``catalog.py``).
    ``None`` skips it entirely — no call, no audit entry — which is what the
    model-free paths pass. When it runs, it runs only on drafts the rules did not
    reject, and a failure in it never blocks routing: the error is recorded and the
    request continues."""
    if parsed is None:
        storage.add_audit_entry(request_id, "schema_rejected", {"errors": parse_errors})
        storage.update_request_status(request_id, Decision.rejected.value)
        storage.add_audit_entry(
            request_id,
            "routed",
            {"decision": Decision.rejected.value, "routed_to_approval": False},
        )
        return

    storage.add_audit_entry(
        request_id,
        "schema_parsed",
        {
            "name": parsed.name,
            "category": parsed.category,
            "properties": [p.name for p in parsed.properties],
        },
    )

    if profile is None:
        profile = load_active_profile()
    # The duplicate rule needs to know what was asked for: a property request's
    # name is supposed to match the event it targets. Same two values the catalog
    # review reads below.
    request = storage.get_request(request_id)
    evaluation = evaluate(
        parsed,
        profile,
        request_kind=request.get("request_kind"),
        existing_event=request.get("existing_event"),
    )
    storage.set_pii_flags(request_id, evaluation.pii_flagged, evaluation.pii_details)
    storage.add_audit_entry(
        request_id,
        "rules_evaluated",
        {
            "profile": profile.name,
            "checks": [c.model_dump() for c in evaluation.checks],
            "flags": evaluation.flags,
            "pii_flagged": evaluation.pii_flagged,
            "pii_details": evaluation.pii_details,
        },
    )

    # Advisory semantic catalog review — inference, never a rejection. A draft the
    # rules rejected is not worth a model call, and a review failure must never take
    # down intake: record it and route normally. The review's question depends on
    # what was asked for, so it gets the request kind and named event off the row,
    # plus the requester's own wording as evidence of the behaviour being tracked.
    if duplicate_fn is not None and evaluation.decision is not Decision.rejected:
        try:
            review = duplicate_fn(
                parsed,
                request_kind=request.get("request_kind"),
                existing_event=request.get("existing_event"),
                raw_intake_text=request.get("raw_intake_text"),
            )
        except Exception as exc:
            storage.add_audit_entry(
                request_id, "duplicate_review_failed", {"error": str(exc)}
            )
        else:
            findings = [f.model_dump() for f in review.findings]
            storage.set_duplicate_candidates(request_id, findings)
            storage.add_audit_entry(
                request_id,
                "duplicate_review",
                {
                    "model": review.model,
                    "findings": findings,
                    **({"parse_error": review.parse_error} if review.parse_error else {}),
                },
            )

    if requires_confirmation and evaluation.decision is not Decision.rejected:
        storage.update_request_status(request_id, "draft")
    else:
        storage.update_request_status(request_id, evaluation.decision.value)
    storage.add_audit_entry(
        request_id,
        "routed",
        {
            "decision": evaluation.decision.value,
            "routed_to_approval": evaluation.routed_to_approval,
            "flags": evaluation.flags,
        },
    )


# Only a high-confidence finding costs a human a required action. The rest are shown
# and cost nothing — see docs/adr/0001. Findings written before confidence was acted on
# are treated as high, which is what they were gated as at the time.
def _gating_findings(findings: list, kinds: Optional[set] = None) -> list:
    return [
        f
        for f in findings
        if f.get("confidence", "high") == "high"
        and (kinds is None or f.get("kind", "duplicate_event") in kinds)
    ]


def _engine_duplicates(request_id: int, storage: Storage) -> set:
    """Which deterministic duplicate rules failed, recovered from the audit log.

    The engine's duplicate findings are not stored on the request row —
    ``duplicate_candidates`` is the model's output alone — so ``rules_evaluated`` is
    the record. Same pattern :func:`submit_request` uses to recover its decision from
    the ``routed`` entry: the audit log stays the one source of truth.
    """
    entry = next(
        (
            e
            for e in reversed(storage.get_audit_log(request_id))
            if e["step"] == "rules_evaluated"
        ),
        None,
    )
    if entry is None:
        return set()
    return {
        check["rule"]
        for check in entry["detail"].get("checks", [])
        if check["rule"] in ("duplicate", "near_duplicate") and not check["passed"]
    }


def _push_if_pending(request_id: int, storage: Storage) -> None:
    """Push a request to the Notion approval board if it is at ``pending_approval``.

    Store-first and one-way: the local event is already persisted and is kept regardless.
    No token configured -> skip silently. A real push error (token set) is recorded as
    ``notion_push_failed`` and does not affect the local request.
    """
    request = storage.get_request(request_id)
    if request["status"] != Decision.pending_approval.value:
        return
    try:
        url = push_request(request)
    except Exception as exc:
        storage.add_audit_entry(request_id, "notion_push_failed", {"error": str(exc)})
        return
    if url is not None:
        storage.add_audit_entry(request_id, "notion_pushed", {"url": url})


def interpret_intake(
    raw_intake_text: str,
    storage: Storage,
    interpret_fn: Callable[..., Interpretation] = interpret,
    duplicate_fn: Callable[..., DuplicateReview] = review_against_catalog,
    submitter_name: Optional[str] = None,
    submitter_team: Optional[str] = None,
    call_type: Optional[str] = None,
    side: Optional[str] = None,
    business_value: Optional[str] = None,
    urgent: bool = False,
    urgency_reason: Optional[str] = None,
    needed_by: Optional[str] = None,
    request_kind: Optional[str] = None,
    existing_event: Optional[str] = None,
    destinations: Optional[list] = None,
    profile: Optional[GovernanceProfile] = None,
) -> int:
    """Draft a definition from natural-language text, then run the existing flow.

    Persists the request and writes ``intake_received`` before calling the model, so a
    model failure still leaves an auditable record. A request the rules did not reject
    lands at ``draft`` for the requester to confirm via :func:`submit_request` before
    it enters the approval queue. Returns the request id; raises
    :class:`IntakeModelError` if the model service is unreachable.
    """
    request_id = storage.create_request(
        raw_intake_text=raw_intake_text,
        submitter_name=submitter_name,
        submitter_team=submitter_team,
        call_type=call_type,
        side=side,
        business_value=business_value,
        urgent=urgent,
        urgency_reason=urgency_reason,
        needed_by=needed_by,
        request_kind=request_kind,
        existing_event=existing_event,
        destinations=destinations,
    )
    storage.add_audit_entry(
        request_id,
        "intake_received",
        {
            "raw_intake_text": raw_intake_text,
            "submitter_name": submitter_name,
            "submitter_team": submitter_team,
            "call_type": call_type,
            "side": side,
            "business_value": business_value,
            "urgent": urgent,
            "urgency_reason": urgency_reason,
            "needed_by": needed_by,
            "request_kind": request_kind,
            "existing_event": existing_event,
            "destinations": destinations,
        },
    )

    # Resolve once so the profile that drafts and the profile that evaluates are
    # the same object, not two independent reads of a file that can change.
    if profile is None:
        profile = load_active_profile()

    try:
        result = interpret_fn(
            raw_intake_text,
            profile=profile,
            business_value=business_value,
            request_kind=request_kind,
            existing_event=existing_event,
        )
    except InterpreterError as exc:
        storage.add_audit_entry(
            request_id, "model_error", {"model": exc.model, "reason": str(exc)}
        )
        storage.update_request_status(request_id, Decision.rejected.value)
        storage.add_audit_entry(
            request_id,
            "routed",
            {"decision": Decision.rejected.value, "routed_to_approval": False},
        )
        raise IntakeModelError(request_id, str(exc)) from exc

    storage.add_audit_entry(
        request_id,
        "model_interpreted",
        {
            "model": result.model,
            "profile": profile.name,
            "proposed_definition": result.proposed_definition,
            **({} if result.proposed_definition is not None
               else {"raw_response": result.raw_response, "parse_error": result.parse_error}),
        },
    )

    if result.proposed_definition is None:
        _route(
            request_id,
            None,
            [{"source": "model_output", "msg": result.parse_error}],
            storage,
            profile,
            duplicate_fn,
            requires_confirmation=True,
        )
        return request_id

    parsed, parse_errors = _parse(result.proposed_definition)
    if parsed is not None:
        storage.set_parsed_definition(request_id, parsed.model_dump(), parsed.category)
    _route(
        request_id,
        parsed,
        parse_errors,
        storage,
        profile,
        duplicate_fn,
        requires_confirmation=True,
    )
    return request_id


def ingest_raw_definition(
    raw_intake_text: str,
    candidate_definition: dict,
    storage: Storage,
    # None skips the review: this path is deliberately model-free for offline demos.
    duplicate_fn: Optional[Callable[..., DuplicateReview]] = None,
    submitter_name: Optional[str] = None,
    submitter_team: Optional[str] = None,
    call_type: Optional[str] = None,
    side: Optional[str] = None,
    business_value: Optional[str] = None,
    urgent: bool = False,
    urgency_reason: Optional[str] = None,
    needed_by: Optional[str] = None,
    request_kind: Optional[str] = None,
    existing_event: Optional[str] = None,
    destinations: Optional[list] = None,
    profile: Optional[GovernanceProfile] = None,
) -> int:
    """Route a pre-built definition that skips the model, for demos where a faithful
    model would not author the violation under test (a malformed name, a duplicate).

    The trail records ``definition_provided`` in place of ``model_interpreted``; the rest
    of the pipeline is identical to :func:`interpret_intake`.
    """
    request_id = storage.create_request(
        raw_intake_text=raw_intake_text,
        submitter_name=submitter_name,
        submitter_team=submitter_team,
        call_type=call_type,
        side=side,
        business_value=business_value,
        urgent=urgent,
        urgency_reason=urgency_reason,
        needed_by=needed_by,
        request_kind=request_kind,
        existing_event=existing_event,
        destinations=destinations,
    )
    storage.add_audit_entry(
        request_id,
        "intake_received",
        {
            "raw_intake_text": raw_intake_text,
            "submitter_name": submitter_name,
            "submitter_team": submitter_team,
            "call_type": call_type,
            "side": side,
            "business_value": business_value,
            "urgent": urgent,
            "urgency_reason": urgency_reason,
            "needed_by": needed_by,
            "request_kind": request_kind,
            "existing_event": existing_event,
            "destinations": destinations,
        },
    )
    storage.add_audit_entry(
        request_id, "definition_provided", {"definition": candidate_definition}
    )
    parsed, parse_errors = _parse(candidate_definition)
    if parsed is not None:
        storage.set_parsed_definition(request_id, parsed.model_dump(), parsed.category)
    _route(request_id, parsed, parse_errors, storage, profile, duplicate_fn)
    return request_id


def ingest(
    raw_intake_text: str,
    candidate_definition: dict,
    storage: Storage,
    # None skips the review: this path is deliberately model-free for offline demos.
    duplicate_fn: Optional[Callable[..., DuplicateReview]] = None,
) -> int:
    """Persist and route a request from a structured definition supplied directly.

    Used offline where the definition is given rather than drafted by the model (see
    ``run_examples.py``). The HTTP intake path uses :func:`interpret_intake` instead.
    """
    parsed, parse_errors = _parse(candidate_definition)
    request_id = storage.create_request(
        raw_intake_text=raw_intake_text,
        parsed_definition=parsed.model_dump() if parsed else None,
        category=parsed.category if parsed else None,
    )
    storage.add_audit_entry(
        request_id, "intake_received", {"raw_intake_text": raw_intake_text}
    )
    _route(request_id, parsed, parse_errors, storage, duplicate_fn=duplicate_fn)
    return request_id


def submit_request(
    request_id: int,
    storage: Storage,
    duplicate_note: Optional[str] = None,
    *,
    duplicate_unsure: bool = False,
) -> None:
    """Confirm a draft and move it into the approval queue.

    Only a request currently at ``draft`` can be submitted. The routed decision is
    recovered from the ``routed`` audit entry, so the audit log stays the one source
    of truth for it.

    Two things require the requester to say something: a near-duplicate name found by
    the engine, and a high-confidence ``duplicate_event`` finding from the semantic
    review. Either takes ``duplicate_note`` — the requester's statement of why the
    existing event won't work for them — or ``duplicate_unsure``, which passes the
    question to the approver instead of forcing them to fabricate a difference. The
    ``submitted`` entry records whichever was used. An exact name match is the
    approver's to acknowledge, not the requester's, because there is nothing to
    argue. Other finding kinds, and findings below high confidence, are information
    rather than an accusation and never gate submission. Raises
    :class:`RequestNotFound`, :class:`InvalidTransition`, or
    :class:`DuplicateNoteRequired` for the caller to map to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] != "draft":
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be submitted"
        )
    routed = next(
        e for e in reversed(storage.get_audit_log(request_id)) if e["step"] == "routed"
    )
    decision = routed["detail"]["decision"]
    # Rows written before findings carried a kind are all duplicate candidates.
    duplicate_findings = _gating_findings(
        request.get("duplicate_candidates") or [], {"duplicate_event"}
    )
    reasons = []
    if "near_duplicate" in _engine_duplicates(request_id, storage):
        reasons.append("a name an existing event already uses, written differently")
    if duplicate_findings:
        reasons.append(
            f"{len(duplicate_findings)} possible semantic duplicate(s)"
        )
    if reasons and not duplicate_note and not duplicate_unsure:
        raise DuplicateNoteRequired(
            f"request {request_id} has {' and '.join(reasons)}; a note stating why "
            "the existing event won't work — or duplicate_unsure, passing the "
            "question to the approver — is required to submit"
        )

    storage.add_audit_entry(
        request_id,
        "submitted",
        {
            "decision": decision,
            **({"duplicate_note": duplicate_note} if duplicate_note else {}),
            **(
                {"duplicate_unsure": True}
                if duplicate_unsure and not duplicate_note
                else {}
            ),
        },
    )
    storage.update_request_status(request_id, decision)
    _push_if_pending(request_id, storage)


CONVERTIBLE_FINDING_KINDS = {"property_extension", "property_already_exists"}


def convert_to_property_request(
    request_id: int,
    existing_event: str,
    storage: Storage,
    interpret_fn: Callable[..., Interpretation] = interpret,
    duplicate_fn: Callable[..., DuplicateReview] = review_against_catalog,
) -> int:
    """Supersede a draft with a new request that adds its properties to
    ``existing_event`` instead of introducing a new event.

    The requester has read a stored ``property_extension`` or
    ``property_already_exists`` finding naming ``existing_event`` and agreed with it;
    a caller naming an event no such finding points at is refused. The original is
    never mutated: a new request re-enters model intake with the original's intake
    fields and ``request_kind="new_property_on_existing"``, drafts, evaluates, gets
    its own catalog review, and lands at ``draft`` for its own confirmation. Only
    then is the original marked ``superseded``, with audit entries linking the two
    in both directions. A model failure while drafting leaves the original at
    ``draft`` so conversion can be retried. Returns the new request id; raises
    :class:`RequestNotFound`, :class:`InvalidTransition`,
    :class:`NoMatchingFinding`, or :class:`IntakeModelError` for the caller to map
    to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] != "draft":
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be converted"
        )
    if not any(
        f.get("kind") in CONVERTIBLE_FINDING_KINDS
        and f.get("existing_event") == existing_event
        for f in request.get("duplicate_candidates") or []
    ):
        raise NoMatchingFinding(
            f"request {request_id} has no property finding naming "
            f"'{existing_event}'; conversion must target an event a stored "
            "finding points at"
        )

    new_request_id = interpret_intake(
        request["raw_intake_text"],
        storage,
        interpret_fn=interpret_fn,
        duplicate_fn=duplicate_fn,
        submitter_name=request.get("submitter_name"),
        submitter_team=request.get("submitter_team"),
        call_type=request.get("call_type"),
        side=request.get("side"),
        business_value=request.get("business_value"),
        urgent=bool(request.get("urgent")),
        urgency_reason=request.get("urgency_reason"),
        needed_by=request.get("needed_by"),
        request_kind="new_property_on_existing",
        existing_event=existing_event,
        destinations=request.get("destinations"),
    )

    storage.update_request_status(request_id, "superseded")
    storage.add_audit_entry(
        request_id,
        "superseded_by",
        {"new_request_id": new_request_id, "existing_event": existing_event},
    )
    storage.add_audit_entry(
        new_request_id,
        "supersedes",
        {"original_request_id": request_id, "existing_event": existing_event},
    )
    return new_request_id


WITHDRAWABLE_FINDING_KINDS = {"duplicate_event"}


def withdraw_request(
    request_id: int,
    existing_event: str,
    reason: Optional[str],
    storage: Storage,
) -> None:
    """End a draft because the requester agrees the existing event already covers it.

    The requester has read a stored ``duplicate_event`` finding naming
    ``existing_event`` and agreed with it; this is their path out that doesn't
    require fabricating a difference or abandoning the tab. A caller naming an
    event no such finding points at is refused. Makes no model call and no Notion
    push — the request never entered the approval queue. Raises
    :class:`RequestNotFound`, :class:`InvalidTransition`, or
    :class:`NoMatchingFinding` for the caller to map to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] != "draft":
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be withdrawn"
        )
    # Rows written before findings carried a kind are all duplicate candidates.
    if not any(
        f.get("kind", "duplicate_event") in WITHDRAWABLE_FINDING_KINDS
        and f.get("existing_event") == existing_event
        for f in request.get("duplicate_candidates") or []
    ):
        raise NoMatchingFinding(
            f"request {request_id} has no duplicate finding naming "
            f"'{existing_event}'; withdrawal must target an event a stored "
            "finding points at"
        )

    storage.add_audit_entry(
        request_id,
        "withdrawn",
        {"existing_event": existing_event, "reason": reason},
    )
    storage.update_request_status(request_id, "withdrawn")


FINDING_KIND_LABELS = {
    "duplicate_event": "possible semantic duplicates",
    "property_extension": "possible property extensions",
    "property_already_exists": "possibly pre-existing properties",
}


def _finding_labels(findings: list) -> str:
    """Name the kinds actually present, in a fixed order, without claiming more."""
    kinds = {f.get("kind", "duplicate_event") for f in findings}
    return ", ".join(
        label for kind, label in FINDING_KIND_LABELS.items() if kind in kinds
    )


def decide(
    request_id: int,
    decision: str,
    storage: Storage,
    publisher: Publisher,
    note: Optional[str] = None,
    approver_name: Optional[str] = None,
    pii_acknowledged: bool = False,
    findings_acknowledged: bool = False,
) -> Optional[PublishResult]:
    """Apply a human approve/reject decision and write the audit trail.

    Only a request currently pending approval or flagged as a duplicate can be decided.
    Approving a PII-flagged request requires ``pii_acknowledged``. Approving one whose
    name exactly matches an existing event, or that carries high-confidence agent
    findings, requires ``findings_acknowledged`` — the exact match holds on every
    intake path, including ``POST /requests/raw``, which skips requester confirmation
    and so has no earlier point at which anyone sees the collision. Approve publishes
    and moves to ``published``; reject moves to ``rejected``. Raises
    :class:`RequestNotFound`, :class:`InvalidTransition`,
    :class:`PiiAcknowledgmentRequired`, or :class:`DuplicateAcknowledgmentRequired` for
    the caller to map to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] not in DECIDABLE_STATUSES:
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be decided"
        )
    if decision == "approve" and request["pii_flagged"] and not pii_acknowledged:
        raise PiiAcknowledgmentRequired(
            f"request {request_id} is PII-flagged ({request['pii_details']}); "
            "acknowledgment is required to approve"
        )
    findings = _gating_findings(request.get("duplicate_candidates") or [])
    exact_duplicate = "duplicate" in _engine_duplicates(request_id, storage)
    if decision == "approve" and (findings or exact_duplicate) and not findings_acknowledged:
        reasons = []
        if exact_duplicate:
            reasons.append("a name that already exists in the tracking plan")
        if findings:
            reasons.append(
                f"{len(findings)} agent finding(s) ({_finding_labels(findings)})"
            )
        raise DuplicateAcknowledgmentRequired(
            f"request {request_id} has {' and '.join(reasons)}; acknowledgment is "
            "required to approve"
        )

    storage.add_audit_entry(
        request_id,
        "decision_received",
        {"decision": decision, "approver": approver_name, "note": note},
    )

    if decision == "approve":
        if request["pii_flagged"]:
            storage.add_audit_entry(
                request_id,
                "pii_acknowledged",
                {
                    "message": f"PII acknowledged by {approver_name or 'unknown'}",
                    "pii_details": request["pii_details"],
                },
            )
        if findings or exact_duplicate:
            acknowledged = [_finding_labels(findings)] if findings else []
            if exact_duplicate:
                acknowledged.append("an exact name match in the tracking plan")
            storage.add_audit_entry(
                request_id,
                "findings_acknowledged",
                {
                    "message": (
                        f"{', '.join(acknowledged)} acknowledged by "
                        f"{approver_name or 'unknown'}"
                    ),
                    "candidates": [f["existing_event"] for f in findings],
                },
            )
        storage.update_request_status(request_id, "approved")
        event = EventDefinition.model_validate(request["parsed_definition"])
        result = publisher.publish(event)
        storage.set_publish_result(request_id, result.model_dump())
        storage.update_request_status(request_id, "published")
        storage.add_audit_entry(
            request_id,
            "published",
            {
                "publisher": result.publisher,
                "confluence_doc_id": result.confluence_doc["id"],
                "jira_ticket_key": result.jira_ticket["key"],
            },
        )
        return result

    storage.update_request_status(request_id, Decision.rejected.value)
    storage.add_audit_entry(
        request_id, "rejection_recorded", {"approver": approver_name, "note": note}
    )
    return None

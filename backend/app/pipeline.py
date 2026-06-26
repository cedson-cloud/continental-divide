"""Intake-to-routing flow, persisted.

Drives a single request through parse, deterministic rules, and routing, writing one
audit entry per state transition as it goes. Approval and publish transitions are added
in step 4; the storage helpers they need are already in place.
"""

from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from .models import Decision, EventDefinition
from .publisher import Publisher, PublishResult
from .rules import evaluate
from .storage import Storage

DECIDABLE_STATUSES = {Decision.pending_approval.value, Decision.flagged_duplicate.value}


class RequestNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


def ingest(raw_intake_text: str, candidate_definition: dict, storage: Storage) -> int:
    """Persist a request and its audit trail through to a routing decision.

    ``candidate_definition`` is the structured definition a model would produce from the
    raw text; in step 4 that step calls the Anthropic API. Returns the request id.
    """
    parsed: EventDefinition | None = None
    parse_errors = None
    try:
        parsed = EventDefinition.model_validate(candidate_definition)
    except ValidationError as exc:
        parse_errors = exc.errors(include_url=False)

    request_id = storage.create_request(
        raw_intake_text=raw_intake_text,
        parsed_definition=parsed.model_dump() if parsed else None,
        category=parsed.category if parsed else None,
        status="pending_approval" if parsed else "rejected",
    )

    storage.add_audit_entry(
        request_id, "intake_received", {"raw_intake_text": raw_intake_text}
    )

    if parsed is None:
        storage.add_audit_entry(request_id, "schema_rejected", {"errors": parse_errors})
        storage.update_request_status(request_id, Decision.rejected.value)
        storage.add_audit_entry(
            request_id,
            "routed",
            {"decision": Decision.rejected.value, "routed_to_approval": False},
        )
        return request_id

    storage.add_audit_entry(
        request_id,
        "schema_parsed",
        {
            "name": parsed.name,
            "category": parsed.category,
            "properties": [p.name for p in parsed.properties],
        },
    )

    evaluation = evaluate(parsed)
    storage.add_audit_entry(
        request_id,
        "rules_evaluated",
        {
            "checks": [c.model_dump() for c in evaluation.checks],
            "flags": evaluation.flags,
        },
    )

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
    return request_id


def decide(
    request_id: int,
    decision: str,
    storage: Storage,
    publisher: Publisher,
    note: Optional[str] = None,
) -> Optional[PublishResult]:
    """Apply a human approve/reject decision and write the audit trail.

    Only a request currently pending approval or flagged as a duplicate can be decided.
    Approve publishes and moves to ``published``; reject moves to ``rejected``. Raises
    :class:`RequestNotFound` or :class:`InvalidTransition` for the caller to map to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] not in DECIDABLE_STATUSES:
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be decided"
        )

    storage.add_audit_entry(
        request_id, "decision_received", {"decision": decision, "note": note}
    )

    if decision == "approve":
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
    storage.add_audit_entry(request_id, "rejection_recorded", {"note": note})
    return None

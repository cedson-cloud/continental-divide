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

from .interpreter import Interpretation, InterpreterError, interpret
from .models import Decision, EventDefinition
from .publisher import Publisher, PublishResult
from .rules import evaluate
from .storage import Storage

DECIDABLE_STATUSES = {Decision.pending_approval.value, Decision.flagged_duplicate.value}


class RequestNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


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
) -> None:
    """Write the schema -> rules -> routed tail of the audit trail and set the final
    status. The request row and the entries that precede ``schema_parsed`` are written
    by the caller."""
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


def interpret_intake(
    raw_intake_text: str,
    storage: Storage,
    interpret_fn: Callable[[str], Interpretation] = interpret,
) -> int:
    """Draft a definition from natural-language text, then run the existing flow.

    Persists the request and writes ``intake_received`` before calling the model, so a
    model failure still leaves an auditable record. Returns the request id; raises
    :class:`IntakeModelError` if the model service is unreachable.
    """
    request_id = storage.create_request(raw_intake_text=raw_intake_text)
    storage.add_audit_entry(
        request_id, "intake_received", {"raw_intake_text": raw_intake_text}
    )

    try:
        result = interpret_fn(raw_intake_text)
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
            "proposed_definition": result.proposed_definition,
            **({} if result.proposed_definition is not None
               else {"raw_response": result.raw_response, "parse_error": result.parse_error}),
        },
    )

    if result.proposed_definition is None:
        _route(request_id, None, [{"source": "model_output", "msg": result.parse_error}], storage)
        return request_id

    parsed, parse_errors = _parse(result.proposed_definition)
    if parsed is not None:
        storage.set_parsed_definition(request_id, parsed.model_dump(), parsed.category)
    _route(request_id, parsed, parse_errors, storage)
    return request_id


def ingest(raw_intake_text: str, candidate_definition: dict, storage: Storage) -> int:
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
    _route(request_id, parsed, parse_errors, storage)
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

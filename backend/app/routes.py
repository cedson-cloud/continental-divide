"""HTTP routes for intake, listing, detail, and human decisions.

Every handler goes through the Storage interface and the pipeline helpers; no SQL lives
here. The Anthropic key is not used in this layer.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from .catalog import catalog_entries
from .catalog_view import CatalogView, build_catalog_view
from .config import get_settings
from .governance import (
    EXAMPLE_EVENT_NAMES,
    GovernanceError,
    GovernanceProfile,
    load_active_profile,
)
from .identity import Identity, Unauthenticated, get_verifier
from .governance_draft import (
    GovernanceDraftAnswers,
    build_profile_yaml,
    validate_profile_yaml,
)
from .models import CallType
from .pipeline import (
    CallTypeConflict,
    DuplicateAcknowledgmentRequired,
    DuplicateNoteRequired,
    IntakeModelError,
    InvalidTransition,
    NoMatchingFinding,
    PiiAcknowledgmentRequired,
    PiiReasonRequired,
    PublishFailed,
    RequestNotFound,
    convert_to_property_request,
    decide,
    ingest_raw_definition,
    interpret_intake,
    publish_approved,
    recorded_pii_hits,
    submit_request,
    withdraw_request,
)
from .publisher import get_publisher
from .rate_limit import RateLimiter
from .recourse import (
    NameNotOffered,
    RuleNotFailing,
    name_suggestions,
    open_disputes,
    record_rule_dispute,
    rename_and_resubmit,
)
from .rules import effective_categories, event_name_error
from .storage import Storage, get_storage


def current_identity(request: Request) -> Identity:
    """Every route but /health runs behind this. Read per request, so it fails closed
    the moment AUTH_MODE is unset."""
    try:
        return get_verifier(get_settings()).verify(request.headers)
    except Unauthenticated as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def acting_storage(identity: Identity = Depends(current_identity)) -> Storage:
    return get_storage().acting_as(identity)


router = APIRouter(dependencies=[Depends(current_identity)])

_settings = get_settings()
_limiter = RateLimiter(_settings.rate_limit_max, _settings.rate_limit_window_seconds)


SubmitterTeam = Literal["Product", "Marketing", "Data", "Engineering"]
# The model path drafts track only until its identify and group prompts exist (TASKS
# item 5c). The model-free raw path takes every call type the profile allows.
DraftedCallType = Literal["track"]
# "Unsure" is a real answer: it is stored verbatim and surfaced to the approver as
# an open question rather than forcing a guess at intake.
Side = Literal["Client", "Server", "Unsure"]


RequestKind = Literal["new_event", "new_property_on_existing"]

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_needed_by(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if not _ISO_DATE.match(value):
        raise ValueError("needed_by must be an ISO date (YYYY-MM-DD)")
    return value


def _validate_urgency(model):
    if model.urgent and not (model.urgency_reason or "").strip():
        raise ValueError("urgency_reason is required when urgent is true")
    return model


def _validate_request_kind(model):
    if model.request_kind == "new_property_on_existing" and model.call_type != "track":
        raise ValueError(
            "a property request adds to a track event; identify and group requests "
            "add traits instead"
        )
    return model


class IntakeBody(BaseModel):
    raw_intake_text: str
    business_value: str = Field(min_length=1)
    submitter_name: str = Field(min_length=1)
    submitter_team: SubmitterTeam
    call_type: DraftedCallType = "track"
    side: Side = "Client"
    urgent: bool = False
    urgency_reason: Optional[str] = None
    needed_by: Optional[str] = None
    request_kind: RequestKind = "new_event"
    # Only meaningful when request_kind is new_property_on_existing.
    existing_event: Optional[str] = None
    destinations: list[str] = Field(default_factory=list)

    _needed_by_iso = field_validator("needed_by")(_validate_needed_by)
    _urgency = model_validator(mode="after")(_validate_urgency)


class RawIntakeBody(BaseModel):
    # Submitter fields stay optional here, unlike IntakeBody: /requests/raw is the
    # model-free deterministic demo path and run_examples.py posts to it headlessly.
    definition: dict
    raw_intake_text: Optional[str] = None
    business_value: str = Field(min_length=1)
    submitter_name: Optional[str] = None
    submitter_team: Optional[SubmitterTeam] = None
    call_type: CallType = "track"
    side: Side = "Client"
    urgent: bool = False
    urgency_reason: Optional[str] = None
    needed_by: Optional[str] = None
    request_kind: RequestKind = "new_event"
    existing_event: Optional[str] = None
    destinations: list[str] = Field(default_factory=list)
    # No requester step follows this path, so each PII hit's written reason comes
    # with the definition, keyed by property name (ADR 0003).
    pii_reasons: dict[str, str] = Field(default_factory=dict)

    _needed_by_iso = field_validator("needed_by")(_validate_needed_by)
    _urgency = model_validator(mode="after")(_validate_urgency)
    _request_kind = model_validator(mode="after")(_validate_request_kind)


class SubmitBody(BaseModel):
    duplicate_note: Optional[str] = None
    duplicate_unsure: bool = False
    # Keyed by property name; one per PII hit (ADR 0003).
    pii_reasons: dict[str, str] = Field(default_factory=dict)


class ConvertBody(BaseModel):
    existing_event: str = Field(min_length=1)


class WithdrawBody(BaseModel):
    existing_event: str = Field(min_length=1)
    reason: Optional[str] = None


class RenameBody(BaseModel):
    new_name: str = Field(min_length=1)


class DisputeBody(BaseModel):
    rule: str = Field(min_length=1)
    # A dispute with no argument in it is not a governance record, so the note is
    # required here and not only in the UI.
    note: str = Field(min_length=1)


class DecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    note: Optional[str] = None
    approver_name: Optional[str] = None
    pii_acknowledged: bool = False
    findings_acknowledged: bool = False


class IntakeResponse(BaseModel):
    id: int
    status: str
    routed_to_approval: bool
    checks: list = Field(default_factory=list)
    flags: list = Field(default_factory=list)
    duplicate_candidates: list = Field(default_factory=list)


def _active_profile() -> GovernanceProfile:
    """Load the enforced profile, mapping a bad profile file to a clean 500. The
    message deliberately names no file path and nothing from settings."""
    try:
        return load_active_profile()
    except GovernanceError:
        raise HTTPException(
            status_code=500,
            detail="the active governance profile could not be loaded",
        )


def _validate_call_type(call_type: str, profile: GovernanceProfile) -> None:
    if call_type not in profile.call_types:
        raise HTTPException(
            status_code=422,
            detail=(
                f"call type '{call_type}' is not allowed. The governance profile "
                f"allows: {', '.join(profile.call_types)}"
            ),
        )


def _validate_destinations(destinations: list[str], profile: GovernanceProfile) -> None:
    """Reject destinations outside the profile's list. An empty profile list means
    no constraint, matching how categories behave."""
    allowed = profile.destinations
    if not allowed or not destinations:
        return
    unknown = sorted(set(destinations) - set(allowed))
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown destinations: {', '.join(unknown)}. "
                f"The governance profile allows: {', '.join(allowed)}"
            ),
        )


@router.get("/governance/profile")
def governance_profile() -> dict:
    """The loaded active profile — contents only, never the file path."""
    profile = _active_profile()
    naming = profile.event_naming
    examples = []
    for name in EXAMPLE_EVENT_NAMES:
        reason = event_name_error(
            name,
            convention=naming.convention,
            connectors=naming.connectors,
            particles=naming.particles,
            irregular_past=naming.irregular_past,
        )
        examples.append({"name": name, "passes": reason is None, "reason": reason})
    values, source = effective_categories(profile)
    return {
        "name": profile.name,
        "source": profile.source,
        "event_naming": naming.model_dump(),
        "property_naming": profile.property_naming.model_dump(),
        "pii": profile.pii.model_dump(),
        "categories": {"values": sorted(values), "source": source},
        "destinations": profile.destinations,
        "examples": examples,
    }


# The answers are all short curated choices, so a body anywhere near this cap
# is not from the setup wizard.
_MAX_GOVERNANCE_DRAFT_BYTES = 4096


@router.post("/governance/draft")
def governance_draft(body: GovernanceDraftAnswers, request: Request) -> dict:
    """Build and validate a profile draft entirely in memory. Download-only:
    this route must never write to disk, run git, or touch the network — the
    app has no auth, so any write here would be an unauthenticated write path."""
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > _MAX_GOVERNANCE_DRAFT_BYTES:
        raise HTTPException(status_code=413, detail="request body too large")

    yaml_text = build_profile_yaml(body)
    errors = validate_profile_yaml(yaml_text)
    return {"yaml": yaml_text, "valid": not errors, "errors": errors}


@router.get("/catalog", response_model=CatalogView)
def get_catalog(storage: Storage = Depends(acting_storage)) -> CatalogView:
    """The data dictionary: sample-plan events plus approved requests, each marked
    with its source. Read-only — no writes, no model call, no Notion. This view is
    NOT what the duplicate review reads; that stays catalog_entries() by design."""
    return build_catalog_view(storage, _active_profile())


@router.post("/requests", response_model=IntakeResponse)
def create_request(
    body: IntakeBody, request: Request, storage: Storage = Depends(acting_storage)
) -> IntakeResponse:
    client = request.client.host if request.client else "unknown"
    if not _limiter.allow(client):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    if len(body.raw_intake_text) > _settings.max_intake_chars:
        raise HTTPException(
            status_code=422,
            detail=f"raw_intake_text exceeds MAX_INTAKE_CHARS ({_settings.max_intake_chars})",
        )

    profile = _active_profile()
    _validate_destinations(body.destinations, profile)
    try:
        request_id = interpret_intake(
            body.raw_intake_text,
            storage,
            submitter_name=body.submitter_name,
            submitter_team=body.submitter_team,
            call_type=body.call_type,
            side=body.side,
            business_value=body.business_value,
            urgent=body.urgent,
            urgency_reason=body.urgency_reason,
            needed_by=body.needed_by,
            request_kind=body.request_kind,
            existing_event=body.existing_event,
            destinations=body.destinations,
            profile=profile,
        )
    except IntakeModelError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"could not draft a definition (request {exc.request_id}): {exc}",
        )

    return _intake_response(storage, request_id)


@router.post("/requests/raw", response_model=IntakeResponse)
def create_request_raw(
    body: RawIntakeBody, storage: Storage = Depends(acting_storage)
) -> IntakeResponse:
    raw_intake_text = (
        body.raw_intake_text
        or body.definition.get("description")
        or body.definition.get("name")
        or "raw definition"
    )
    profile = _active_profile()
    _validate_call_type(body.call_type, profile)
    _validate_destinations(body.destinations, profile)
    try:
        request_id = ingest_raw_definition(
            raw_intake_text,
            body.definition,
            storage,
            submitter_name=body.submitter_name,
            submitter_team=body.submitter_team,
            call_type=body.call_type,
            side=body.side,
            business_value=body.business_value,
            urgent=body.urgent,
            urgency_reason=body.urgency_reason,
            needed_by=body.needed_by,
            request_kind=body.request_kind,
            existing_event=body.existing_event,
            destinations=body.destinations,
            profile=profile,
            pii_reasons=body.pii_reasons,
        )
    except (CallTypeConflict, PiiReasonRequired) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _intake_response(storage, request_id)


def _intake_response(storage, request_id: int) -> IntakeResponse:
    saved = storage.get_request(request_id)
    log = storage.get_audit_log(request_id)
    rules_entry = next((e for e in log if e["step"] == "rules_evaluated"), None)
    routed_entry = next((e for e in log if e["step"] == "routed"), None)
    duplicate_entry = next((e for e in log if e["step"] == "duplicate_review"), None)
    return IntakeResponse(
        id=request_id,
        status=saved["status"],
        routed_to_approval=bool(routed_entry and routed_entry["detail"].get("routed_to_approval")),
        checks=rules_entry["detail"]["checks"] if rules_entry else [],
        flags=rules_entry["detail"]["flags"] if rules_entry else [],
        duplicate_candidates=(
            duplicate_entry["detail"].get("findings", []) if duplicate_entry else []
        ),
    )


@router.get("/requests")
def list_requests(storage: Storage = Depends(acting_storage)) -> list:
    rows = storage.list_requests()
    # A draft is not in anyone's queue yet, a superseded request left the queue for
    # its replacement, and a withdrawn one never entered it; all stay reachable by id.
    return [
        {
            "id": row["id"],
            "name": (row.get("parsed_definition") or {}).get("name"),
            "call_type": row.get("call_type") or "track",
            "category": row["category"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
        if row["status"] not in ("draft", "superseded", "withdrawn")
    ]


def _with_catalog_evidence(findings: list) -> list:
    """Attach the named event's own description and full property list, joined
    against the catalog at read time. The stored finding stays the model's output
    alone — engine-derived catalog data lives only in the response, so the panel
    follows the catalog if the catalog changes. An event absent from the catalog
    gets null/empty, not an error."""
    entries = {e.name: e for e in catalog_entries()}
    enriched = []
    for finding in findings:
        entry = entries.get(finding.get("existing_event"))
        enriched.append(
            {
                **finding,
                "existing_event_description": entry.description if entry else None,
                "existing_event_properties": entry.property_names if entry else [],
            }
        )
    return enriched


@router.get("/requests/{request_id}")
def get_request(request_id: int, storage: Storage = Depends(acting_storage)) -> dict:
    request = storage.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"request {request_id} not found")
    request["duplicate_candidates"] = _with_catalog_evidence(
        request.get("duplicate_candidates") or []
    )
    request["audit_log"] = storage.get_audit_log(request_id)
    # Derived at read time, never stored: a rejected name's compliant alternatives,
    # computed by the same function POST /rename validates against, so what the UI
    # offers and what the endpoint accepts cannot drift.
    request["name_suggestions"] = name_suggestions(request, storage)
    # The fields each reason answers for, beside the reasons themselves.
    request["pii_hits"] = recorded_pii_hits(request, storage)
    request["pii_reasons"] = request.get("pii_reasons") or {}
    return request


@router.post("/requests/{request_id}/submit")
def submit_request_route(
    request_id: int,
    body: Optional[SubmitBody] = None,
    storage: Storage = Depends(acting_storage),
) -> dict:
    try:
        submit_request(
            request_id,
            storage,
            duplicate_note=body.duplicate_note if body else None,
            duplicate_unsure=body.duplicate_unsure if body else False,
            pii_reasons=body.pii_reasons if body else None,
        )
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (DuplicateNoteRequired, PiiReasonRequired) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved = storage.get_request(request_id)
    return {"id": request_id, "status": saved["status"]}


@router.post("/requests/{request_id}/withdraw")
def withdraw_request_route(
    request_id: int, body: WithdrawBody, storage: Storage = Depends(acting_storage)
) -> dict:
    # No rate limit: withdrawing makes no model call and no Notion push.
    try:
        withdraw_request(request_id, body.existing_event, body.reason, storage)
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NoMatchingFinding as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved = storage.get_request(request_id)
    return {"id": request_id, "status": saved["status"]}


@router.post("/requests/{request_id}/rename")
def rename_request(
    request_id: int,
    body: RenameBody,
    request: Request,
    storage: Storage = Depends(acting_storage),
) -> dict:
    # A rename costs one model call — the catalog review on the new request — so it
    # draws on the same rate-limit budget as intake and convert.
    client = request.client.host if request.client else "unknown"
    if not _limiter.allow(client):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    try:
        new_request_id = rename_and_resubmit(request_id, body.new_name, storage)
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NameNotOffered as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved = storage.get_request(new_request_id)
    return {"id": new_request_id, "status": saved["status"]}


@router.post("/requests/{request_id}/dispute-rule")
def dispute_rule(
    request_id: int, body: DisputeBody, storage: Storage = Depends(acting_storage)
) -> dict:
    """Record that a rule looks wrong for this team. Amends nothing: no profile
    change, no file write, no status change, no model call — and therefore no rate
    limit. Authoring a convention happens in the governance wizard; this route only
    files the disagreement for the data team to read."""
    try:
        detail = record_rule_dispute(request_id, body.rule, body.note, storage)
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuleNotFailing as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved = storage.get_request(request_id)
    return {"id": request_id, "status": saved["status"], "dispute": detail}


@router.get("/disputes")
def list_disputes(storage: Storage = Depends(acting_storage)) -> list:
    """Read-only: every dispute a requester has filed, for the data team."""
    return open_disputes(storage)


@router.post("/requests/{request_id}/convert")
def convert_request(
    request_id: int,
    body: ConvertBody,
    request: Request,
    storage: Storage = Depends(acting_storage),
) -> dict:
    # A convert re-runs full model intake — a drafting call plus a catalog review —
    # so it draws on the same rate-limit budget as POST /requests.
    client = request.client.host if request.client else "unknown"
    if not _limiter.allow(client):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    try:
        new_request_id = convert_to_property_request(
            request_id, body.existing_event, storage
        )
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NoMatchingFinding as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntakeModelError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"could not draft a definition (request {exc.request_id}): {exc}",
        )

    saved = storage.get_request(new_request_id)
    return {"id": new_request_id, "status": saved["status"]}


@router.post("/requests/{request_id}/decision")
def decide_request(
    request_id: int, body: DecisionBody, storage: Storage = Depends(acting_storage)
) -> dict:
    try:
        result = decide(
            request_id,
            body.decision,
            storage,
            get_publisher(),
            note=body.note,
            approver_name=body.approver_name,
            pii_acknowledged=body.pii_acknowledged,
            findings_acknowledged=body.findings_acknowledged,
        )
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PiiAcknowledgmentRequired as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except DuplicateAcknowledgmentRequired as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PublishFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    saved = storage.get_request(request_id)
    return {
        "id": request_id,
        "status": saved["status"],
        "published_artifact": result.model_dump() if result else None,
    }


@router.post("/requests/{request_id}/publish")
def publish_request(
    request_id: int, storage: Storage = Depends(acting_storage)
) -> dict:
    try:
        result = publish_approved(request_id, storage, get_publisher())
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PublishFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "id": request_id,
        "status": storage.get_request(request_id)["status"],
        "published_artifact": result.model_dump(),
    }

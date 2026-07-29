"""HTTP routes for intake, listing, detail, and human decisions.

Every handler goes through the Storage interface and the pipeline helpers; no SQL lives
here. The Anthropic key is not used in this layer.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .config import get_settings
from .governance import (
    EXAMPLE_EVENT_NAMES,
    GovernanceError,
    GovernanceProfile,
    load_active_profile,
)
from .pipeline import (
    DuplicateAcknowledgmentRequired,
    IntakeModelError,
    InvalidTransition,
    PiiAcknowledgmentRequired,
    RequestNotFound,
    decide,
    ingest_raw_definition,
    interpret_intake,
)
from .publisher import get_publisher
from .rate_limit import RateLimiter
from .rules import effective_categories, event_name_error
from .storage import get_storage

router = APIRouter()

_settings = get_settings()
_limiter = RateLimiter(_settings.rate_limit_max, _settings.rate_limit_window_seconds)


SubmitterTeam = Literal["Product", "Marketing", "Data", "Engineering"]
# track only: EventDefinition is track-shaped and rules.py enforces an event-name
# convention. identify/page/screen need their own shapes and rules (see TASKS.md).
CallType = Literal["track"]
Side = Literal["Client", "Server"]


RequestKind = Literal["new_event", "new_property_on_existing"]


class IntakeBody(BaseModel):
    raw_intake_text: str
    business_value: str = Field(min_length=1)
    submitter_name: Optional[str] = None
    submitter_team: Optional[SubmitterTeam] = None
    call_type: CallType = "track"
    side: Side = "Client"
    needed_by: Optional[str] = None
    request_kind: RequestKind = "new_event"
    # Only meaningful when request_kind is new_property_on_existing.
    existing_event: Optional[str] = None
    destinations: list[str] = Field(default_factory=list)


class RawIntakeBody(BaseModel):
    definition: dict
    raw_intake_text: Optional[str] = None
    business_value: str = Field(min_length=1)
    submitter_name: Optional[str] = None
    submitter_team: Optional[SubmitterTeam] = None
    call_type: CallType = "track"
    side: Side = "Client"
    needed_by: Optional[str] = None
    request_kind: RequestKind = "new_event"
    existing_event: Optional[str] = None
    destinations: list[str] = Field(default_factory=list)


class DecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    note: Optional[str] = None
    approver_name: Optional[str] = None
    pii_acknowledged: bool = False
    duplicate_acknowledged: bool = False


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


@router.post("/requests", response_model=IntakeResponse)
def create_request(body: IntakeBody, request: Request) -> IntakeResponse:
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
    storage = get_storage()
    try:
        request_id = interpret_intake(
            body.raw_intake_text,
            storage,
            submitter_name=body.submitter_name,
            submitter_team=body.submitter_team,
            call_type=body.call_type,
            side=body.side,
            business_value=body.business_value,
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
def create_request_raw(body: RawIntakeBody) -> IntakeResponse:
    raw_intake_text = (
        body.raw_intake_text
        or body.definition.get("description")
        or body.definition.get("name")
        or "raw definition"
    )
    profile = _active_profile()
    _validate_destinations(body.destinations, profile)
    storage = get_storage()
    request_id = ingest_raw_definition(
        raw_intake_text,
        body.definition,
        storage,
        submitter_name=body.submitter_name,
        submitter_team=body.submitter_team,
        call_type=body.call_type,
        side=body.side,
        business_value=body.business_value,
        needed_by=body.needed_by,
        request_kind=body.request_kind,
        existing_event=body.existing_event,
        destinations=body.destinations,
        profile=profile,
    )
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
            duplicate_entry["detail"].get("candidates", []) if duplicate_entry else []
        ),
    )


@router.get("/requests")
def list_requests() -> list:
    storage = get_storage()
    rows = storage.list_requests()
    return [
        {
            "id": row["id"],
            "name": (row.get("parsed_definition") or {}).get("name"),
            "category": row["category"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.get("/requests/{request_id}")
def get_request(request_id: int) -> dict:
    storage = get_storage()
    request = storage.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"request {request_id} not found")
    request["audit_log"] = storage.get_audit_log(request_id)
    return request


@router.post("/requests/{request_id}/decision")
def decide_request(request_id: int, body: DecisionBody) -> dict:
    storage = get_storage()
    try:
        result = decide(
            request_id,
            body.decision,
            storage,
            get_publisher(),
            note=body.note,
            approver_name=body.approver_name,
            pii_acknowledged=body.pii_acknowledged,
            duplicate_acknowledged=body.duplicate_acknowledged,
        )
    except RequestNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PiiAcknowledgmentRequired as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except DuplicateAcknowledgmentRequired as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved = storage.get_request(request_id)
    return {
        "id": request_id,
        "status": saved["status"],
        "published_artifact": result.model_dump() if result else None,
    }

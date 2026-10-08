"""The data dictionary: a read-time composition of the sample plan and approved requests.

This module deliberately does not touch :mod:`catalog`. ``CatalogEntry`` and
``catalog_entries()`` are rendered verbatim into the duplicate-review system prompt,
so widening either would change model behaviour. The dictionary builds its own
response models from the same sources instead — the bundled sample plan and the
requests a human has approved — and marks where each entry came from. It performs
no writes, no model call, and no Notion push.

Two kinds of approved request compose differently. A ``new_event`` request is its
own entry, even when its name collides with an existing one — a rival definition
for the same name is a governance fact the reader must see. A
``new_property_on_existing`` request is not a rival definition, so it never gets
its own entry: its properties merge into the target event with attribution, or —
when the target does not exist — surface as an entry marked ``unresolved_target``.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .governance import GovernanceProfile
from .platforms import plan_named_events
from .rules import load_plan
from .storage import Storage

EventSource = Literal["sample_plan", "approved_request", "system_event"]

# System events belong to no plan category; the dictionary groups them on their own.
SYSTEM_EVENTS_CATEGORY = "System events"

# Statuses that mean a human said yes. `approved` is the moment of decision;
# `published` is the same request after the publisher ran.
_APPROVED_STATUSES = ("approved", "published")


class CatalogViewProperty(BaseModel):
    name: str
    type: str
    # For array properties, the shared shape its items follow (e.g. "product_item").
    # The shape itself is returned once under CatalogView.shapes, never inlined here.
    shape: Optional[str] = None
    source: EventSource = "sample_plan"
    request_id: Optional[int] = None
    # Requests that asked for this property when the target already carried it —
    # the dictionary's view of the review's property_already_exists case. The
    # property renders once; showing it twice would be lying.
    also_requested_by: list[int] = Field(default_factory=list)


class ShapeProperty(BaseModel):
    name: str
    type: str


class SharedShape(BaseModel):
    description: str
    properties: list[ShapeProperty]


class CatalogViewEvent(BaseModel):
    name: str
    category: str
    description: str
    properties: list[CatalogViewProperty]
    source: EventSource
    request_id: Optional[int] = None
    approved_at: Optional[str] = None
    # A property addition whose target event is nowhere in the catalog. It is
    # surfaced rather than dropped: an orphaned property request is a governance
    # fact worth seeing.
    unresolved_target: bool = False
    # For a system event: the name or call the SDK sends, and which SDK sends it.
    sent_as: Optional[str] = None
    sent_by: Optional[str] = None


class CatalogCounts(BaseModel):
    total: int
    from_sample_plan: int
    new_events_from_requests: int
    property_additions_merged: int
    unresolved_targets: int
    system_events: int


class CatalogView(BaseModel):
    events: list[CatalogViewEvent]
    shapes: dict[str, SharedShape] = Field(default_factory=dict)
    counts: CatalogCounts


def _view_properties(
    raw_properties: list,
    *,
    source: EventSource = "sample_plan",
    request_id: Optional[int] = None,
) -> list[CatalogViewProperty]:
    return [
        CatalogViewProperty(
            name=p["name"],
            type=p["type"],
            shape=p.get("items") or None,
            source=source,
            request_id=request_id,
        )
        for p in raw_properties
        if isinstance(p, dict)
    ]


def _sample_plan_events(plan: dict) -> list[CatalogViewEvent]:
    return [
        CatalogViewEvent(
            name=event["name"],
            category=category,
            description=event.get("description", ""),
            properties=_view_properties(event.get("properties", [])),
            source="sample_plan",
        )
        for category, events in plan["categories"].items()
        for event in events
    ]


def _system_events(profile: Optional[GovernanceProfile]) -> list[CatalogViewEvent]:
    if profile is None:
        return []
    named = plan_named_events(profile.platform, profile.event_naming.convention)
    return [
        CatalogViewEvent(
            name=name,
            category=SYSTEM_EVENTS_CATEGORY,
            description=event.records[:1].upper() + event.records[1:],
            properties=[],
            source="system_event",
            sent_as=event.sent_as,
            sent_by=event.sent_by,
        )
        for name, event in named.items()
    ]


def _approved_at(storage: Storage, request_id: int, fallback: Optional[str]) -> Optional[str]:
    for entry in storage.get_audit_log(request_id):
        detail = entry.get("detail") or {}
        if entry["step"] == "decision_received" and detail.get("decision") == "approve":
            return entry["created_at"]
    return fallback


def _request_event(
    storage: Storage,
    row: dict,
    *,
    name: Optional[str] = None,
    unresolved_target: bool = False,
) -> CatalogViewEvent:
    definition = row["parsed_definition"]
    return CatalogViewEvent(
        name=name or definition["name"],
        category=definition.get("category") or row.get("category") or "",
        description=definition.get("description") or "",
        properties=_view_properties(
            definition.get("properties", []),
            source="approved_request",
            request_id=row["id"],
        ),
        source="approved_request",
        request_id=row["id"],
        approved_at=_approved_at(storage, row["id"], row.get("updated_at")),
        unresolved_target=unresolved_target,
    )


def _merge_addition(target: CatalogViewEvent, row: dict) -> None:
    """Fold one approved property addition into its target event. A property name
    the target already carries is never appended twice: the existing row gains the
    request id under also_requested_by instead."""
    existing = {p.name: p for p in target.properties}
    added = _view_properties(
        row["parsed_definition"].get("properties", []),
        source="approved_request",
        request_id=row["id"],
    )
    for prop in added:
        current = existing.get(prop.name)
        if current is not None:
            if row["id"] not in current.also_requested_by:
                current.also_requested_by.append(row["id"])
        else:
            target.properties.append(prop)
            existing[prop.name] = prop


def _shared_shapes(plan: dict, events: list[CatalogViewEvent]) -> dict[str, SharedShape]:
    """Only shapes some property actually references, looked up at the plan's top
    level. A referenced name the plan does not define is left out — the property
    keeps its shape string and the UI simply has nothing to expand."""
    referenced = {p.shape for e in events for p in e.properties if p.shape}
    shapes = {}
    for ref in sorted(referenced):
        shape = plan.get(ref)
        if isinstance(shape, dict) and isinstance(shape.get("properties"), list):
            shapes[ref] = SharedShape(
                description=shape.get("description", ""),
                properties=[
                    ShapeProperty(name=p["name"], type=p["type"])
                    for p in shape["properties"]
                ],
            )
    return shapes


def build_catalog_view(
    storage: Storage, profile: Optional[GovernanceProfile] = None
) -> CatalogView:
    """Compose the dictionary. new_event requests become entries — including on a
    name collision, where both entries are returned. Property additions merge
    into their target instead (or surface as unresolved when it does not exist),
    in request-id order, so a reader sees the event accumulate over time. The
    profile's platform adds its system events, which take property additions too."""
    plan = load_plan()
    sample = _sample_plan_events(plan)
    system = _system_events(profile)

    approved = [
        row
        for row in storage.list_requests()  # ordered by id
        if row["status"] in _APPROVED_STATUSES and row.get("parsed_definition")
    ]
    additions = [
        row for row in approved if row.get("request_kind") == "new_property_on_existing"
    ]
    new_events = [
        _request_event(storage, row)
        for row in approved
        if row.get("request_kind") != "new_property_on_existing"
    ]

    events = sample + system + new_events
    # On a name collision the earliest entry is the merge target — the sample
    # plan, then a system event, before any rival approved definition.
    by_name: dict[str, CatalogViewEvent] = {}
    for event in events:
        by_name.setdefault(event.name, event)

    merged = 0
    unresolved: list[CatalogViewEvent] = []
    for row in additions:
        target_name = row.get("existing_event") or row["parsed_definition"]["name"]
        target = by_name.get(target_name)
        if target is None:
            unresolved.append(
                _request_event(storage, row, name=target_name, unresolved_target=True)
            )
            continue
        _merge_addition(target, row)
        merged += 1

    events = events + unresolved
    return CatalogView(
        events=events,
        shapes=_shared_shapes(plan, events),
        counts=CatalogCounts(
            total=len(events),
            from_sample_plan=len(sample),
            new_events_from_requests=len(new_events),
            property_additions_merged=merged,
            unresolved_targets=len(unresolved),
            system_events=len(system),
        ),
    )

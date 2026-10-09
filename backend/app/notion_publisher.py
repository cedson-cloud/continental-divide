"""One-way push of a validated, pending request to a Notion approval board.

Store-first: the local event is already persisted when this runs. The push is
best-effort and one-way — the app sets Status=Pending and never reads back. The Notion
token is read server-side from :class:`Settings` and never leaves the backend. When no
token is configured, or the app is the public demo (docs/adr/0010), the push is skipped
silently.

Select properties are guarded: a missing value is omitted rather than passed as ``null``
into a Notion select (which the API rejects).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .config import get_settings


@dataclass
class ApprovalRow:
    name: str
    submitter_name: str
    call_type: str
    side: str
    pii_flagged: bool
    pii_details: str
    properties_summary: str
    description: str = ""
    category: Optional[str] = None
    submitter_team: Optional[str] = None
    destinations: List[str] = field(default_factory=list)


def build_properties(row: ApprovalRow, submitted_at: str) -> dict:
    """Map an approval row to Notion page properties. Pure — no network."""
    props = {
        "Event Name": {"title": [{"text": {"content": row.name}}]},
        "Status": {"select": {"name": "Pending"}},
        "Submitter": {"rich_text": [{"text": {"content": row.submitter_name or ""}}]},
        "PII Flagged": {"checkbox": row.pii_flagged},
        "PII Details": {"rich_text": [{"text": {"content": row.pii_details or ""}}]},
        "PII Acknowledged": {"checkbox": False},
        "Description": {"rich_text": [{"text": {"content": row.description or ""}}]},
        "Call Type": {"select": {"name": row.call_type}},
        "Side": {"select": {"name": row.side}},
        "Properties": {"rich_text": [{"text": {"content": row.properties_summary or ""}}]},
        "Submitted At": {"date": {"start": submitted_at}},
    }
    # Guard every optional select: omit rather than pass null into a Notion select.
    if row.submitter_team:
        props["Team"] = {"select": {"name": row.submitter_team}}
    if row.category:
        props["Category"] = {"select": {"name": row.category}}
    if row.destinations:
        props["Destinations"] = {"multi_select": [{"name": d} for d in row.destinations]}
    return props


def row_from_request(request: dict) -> ApprovalRow:
    """Assemble the approval row from a stored event_request (definition + columns)."""
    definition = request.get("parsed_definition") or {}
    properties = definition.get("properties") or []
    properties_summary = ", ".join(f"{p['name']} ({p['type']})" for p in properties)
    return ApprovalRow(
        name=definition.get("name") or "",
        description=definition.get("description") or "",
        category=definition.get("category"),
        submitter_name=request.get("submitter_name") or "",
        submitter_team=request.get("submitter_team"),
        call_type=request.get("call_type") or "track",
        side=request.get("side") or "Client",
        pii_flagged=bool(request.get("pii_flagged")),
        pii_details=request.get("pii_details") or "",
        properties_summary=properties_summary,
    )


def _client():
    settings = get_settings()
    if not settings.notion_token or settings.auth_mode == "demo":
        return None
    from notion_client import Client

    return Client(auth=settings.notion_token)


def push_request(request: dict) -> Optional[str]:
    """Push a stored request to the approval board as a Pending row.

    Returns the Notion page URL, or ``None`` when skipped: no token, or demo mode. Any
    error when a token is set propagates for the caller to record.
    """
    client = _client()
    if client is None:
        return None
    row = row_from_request(request)
    submitted_at = datetime.now(timezone.utc).isoformat()
    page = client.pages.create(
        parent={"database_id": get_settings().notion_approval_db_id},
        properties=build_properties(row, submitted_at),
    )
    return page["url"]

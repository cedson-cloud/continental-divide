"""Publishing behind a thin interface.

On approval the app hands an event definition to a :class:`Publisher`. The default
:class:`MockPublisher` renders a Confluence-style doc and a Jira-style ticket as in-app
data with no network calls. A real Atlassian adapter implements the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from pydantic import BaseModel

from .models import EventDefinition


class PublishResult(BaseModel):
    publisher: str
    confluence_doc: dict
    jira_ticket: dict


class Publisher(ABC):
    @abstractmethod
    def publish(self, event_definition: EventDefinition) -> PublishResult:
        ...


def _slug(name: str) -> str:
    return "-".join(name.lower().split())


class MockPublisher(Publisher):
    name = "mock"

    def __init__(self) -> None:
        self._sequence = 0

    def publish(self, event_definition: EventDefinition) -> PublishResult:
        self._sequence += 1
        seq = self._sequence
        property_rows = [
            {"name": p.name, "type": p.type.value, "required": p.required}
            for p in event_definition.properties
        ]

        confluence_doc = {
            "id": f"PAGE-{seq:03d}",
            "title": f"Event: {event_definition.name}",
            "category": event_definition.category,
            "description": event_definition.description or "",
            "properties": property_rows,
        }
        jira_ticket = {
            "key": f"TRACK-{seq:03d}",
            "summary": f"Implement tracking event: {event_definition.name}",
            "body": (
                f"Category: {event_definition.category}\n"
                f"Properties: {len(property_rows)}\n"
                f"Doc: {confluence_doc['id']}"
            ),
        }
        return PublishResult(
            publisher=self.name,
            confluence_doc=confluence_doc,
            jira_ticket=jira_ticket,
        )


class AtlassianPublisher(Publisher):
    """Stub for real Confluence + Jira publishing. Implement against the Atlassian REST
    APIs with OAuth credentials to enable it; the rest of the app needs no changes."""

    name = "atlassian"

    def publish(self, event_definition: EventDefinition) -> PublishResult:
        raise NotImplementedError(
            "Real Atlassian publishing is not implemented. Provide OAuth credentials and "
            "implement this adapter to create live Confluence pages and Jira tickets."
        )


@lru_cache
def get_publisher() -> Publisher:
    return MockPublisher()

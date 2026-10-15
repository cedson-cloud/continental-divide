"""Platform files: what an analytics platform's SDKs send on their own (ADR 0009, 0011).

A platform is a YAML file under ``platforms/``, not code (ADR 0008). It lists the
platform's libraries; the common fields their events carry; its system events, each
under the plan name a tracking plan shows it by, with the name or call the SDK actually
sends, its properties and any equivalent names; and its reserved names, which the
platform's spec defines but its libraries do not send; and how its libraries are called,
for the snippets an approved definition is rendered to. Every common field, named system
event and reserved name records its sources, and every claim records whether it rests on the docs, on SDK code, or on sources that disagree. Loading
fails loudly on a missing file, malformed YAML, or an invalid schema, the same as
governance profiles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_PLATFORMS_DIR = Path(__file__).resolve().parents[2] / "platforms"

# docs: the vendor's docs say so. sdk_code: read in the vendor's SDK code on GitHub,
# which can be ahead of a release. disputed: the sources disagree; the note says how.
Evidence = Literal["docs", "sdk_code", "disputed"]


class PlatformError(Exception):
    """A platform file could not be loaded or is invalid."""


class Library(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    surface: Literal["browser", "mobile", "server"]
    note: Optional[str] = None


class EventProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # None when the sources checked do not give a type.
    type: Optional[str] = None
    note: Optional[str] = None
    evidence: Evidence = "docs"


def _unique_property_names(properties: Optional[list[EventProperty]], owner: str) -> None:
    names = [p.name for p in properties or []]
    if len(names) != len(set(names)):
        raise ValueError(f"'{owner}' lists a property twice")


class CommonField(BaseModel):
    """A field every event from the listed libraries carries without being asked."""

    model_config = ConfigDict(extra="forbid")

    # Where it lands, in the platform's own terms: context.page.url, $current_url.
    path: str
    plain_name: str
    group: str
    type: Optional[str] = None
    libraries: list[str] = Field(min_length=1)
    note: Optional[str] = None
    evidence: Evidence = "docs"
    sources: list[str] = Field(min_length=1)


class SystemEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None when the event is not one plan event: $autocapture is a stream the plan's
    # actions are built on, and the identity events are calls the plan models already.
    # Also None when the name the plan would use fails the plan's own naming rule.
    plan_name: Optional[str] = None
    sent_as: str
    records: str
    sent_by: str
    equivalents: list[str] = []
    # Library id to whether the library sends it without being configured to.
    default_on: dict[str, bool] = {}
    # None: not listed yet. An empty list: the sources say it carries none of its own.
    properties: Optional[list[EventProperty]] = None
    note: Optional[str] = None
    evidence: Evidence = "docs"
    sources: list[str] = []

    @model_validator(mode="after")
    def _properties_once(self) -> "SystemEvent":
        _unique_property_names(self.properties, self.plan_name or self.sent_as)
        if self.plan_name is not None and not self.sources:
            raise ValueError(f"'{self.plan_name}' cites no source")
        return self


class ReservedName(BaseModel):
    """A name the platform's spec defines for an event its libraries do not send.
    Someone else sends it, a partner or the team itself, so it is never a duplicate
    of an existing event (ADR 0011): it is the name to use."""

    model_config = ConfigDict(extra="forbid")

    name: str
    records: str
    sent_by: str
    properties: Optional[list[EventProperty]] = None
    note: Optional[str] = None
    evidence: Evidence = "docs"
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _properties_once(self) -> "ReservedName":
        _unique_property_names(self.properties, self.name)
        return self


class SnippetSurface(BaseModel):
    """How one library is called, for the snippets an approved definition is rendered
    to (ADR 0008). ``style`` picks the call's shape, which lives in app/snippets.py;
    the library, setup lines and notes it prints come from here. The surface is the
    library's own."""

    model_config = ConfigDict(extra="forbid")

    label: str
    name: str
    library: str
    package: str
    version: str
    # positional: analytics.track(event, properties).
    # params: analytics.track({ userId, event, properties }).
    style: Literal["positional", "params"]
    setup: list[str] = []
    notes: list[str] = []
    checked: str
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _printed_lines_are_single(self) -> "SnippetSurface":
        # Each of these is printed on a line of its own, most of them after "//", so
        # a line break in one would turn the rest of it into code.
        printed = [self.name, self.package, self.version, self.checked, self.sources[0]]
        for line in [*printed, *self.setup, *self.notes]:
            if not line or line != " ".join(line.split()):
                raise ValueError(
                    f"'{self.label}': a printed line is empty, or has a line break "
                    "or extra spaces"
                )
        return self


class Platform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str
    # The docs the file was checked against, and when.
    docs: list[str]
    checked: str
    libraries: list[Library] = []
    common_fields: list[CommonField] = []
    # Things the sources mention that this file does not list yet, so a reader never
    # takes a missing field for one the platform does not send.
    not_listed_yet: list[str] = []
    system_events: list[SystemEvent]
    reserved_names: list[ReservedName] = []
    snippets: list[SnippetSurface] = []

    @model_validator(mode="after")
    def _names_are_unambiguous(self) -> "Platform":
        seen: set[str] = set()
        for event in self.system_events:
            for name in [event.plan_name, *event.equivalents]:
                if name is None:
                    continue
                if name in seen:
                    raise ValueError(f"'{name}' names more than one system event")
                seen.add(name)
        sent = [e.sent_as for e in self.system_events]
        if len(sent) != len(set(sent)):
            raise ValueError("two system events share a sent_as")
        for reserved in self.reserved_names:
            if reserved.name in seen or reserved.name in sent:
                raise ValueError(f"'{reserved.name}' is both reserved and a system event")
            seen.add(reserved.name)
        return self

    @model_validator(mode="after")
    def _libraries_are_known(self) -> "Platform":
        ids = [lib.id for lib in self.libraries]
        if len(ids) != len(set(ids)):
            raise ValueError("two libraries share an id")
        named = [
            *(lib for f in self.common_fields for lib in f.libraries),
            *(lib for e in self.system_events for lib in e.default_on),
            *(s.library for s in self.snippets),
        ]
        unknown = sorted(set(named) - set(ids))
        if unknown:
            raise ValueError(f"unknown library: {', '.join(unknown)}")
        surfaces = {lib.id: lib.surface for lib in self.libraries}
        for snippet in self.snippets:
            if surfaces[snippet.library] == "mobile":
                raise ValueError(
                    f"'{snippet.label}': snippets cover browser and server libraries only"
                )
        paths = [f.path for f in self.common_fields]
        if len(paths) != len(set(paths)):
            raise ValueError("two common fields share a path")
        return self


def render_plan_name(plan_name: str, convention: str) -> str:
    """A plan name as it reads under ``convention``. Plan names are kept in Title Case;
    snake_case lowercases them and joins the words with underscores."""
    if convention == "snake_case_object_action":
        return "_".join(plan_name.lower().split())
    return plan_name


def plan_named_events(platform: Optional[str], convention: str) -> dict[str, SystemEvent]:
    """The platform's system events that have a plan name, keyed by that name written
    in ``convention``. Empty when there is no platform."""
    if platform is None:
        return {}
    return {
        render_plan_name(event.plan_name, convention): event
        for event in load_platform(platform).system_events
        if event.plan_name is not None
    }


def load_platform(name: str, *, directory: Path = _PLATFORMS_DIR) -> Platform:
    path = directory / f"{name}.yaml"
    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise PlatformError(f"platform file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise PlatformError(f"malformed YAML in platform file {path}: {exc}") from exc
    try:
        return Platform.model_validate(data)
    except ValidationError as exc:
        raise PlatformError(f"invalid platform file {path}: {exc}") from exc

"""Platform files: what an analytics platform's SDKs send on their own (ADR 0009).

A platform is a YAML file under ``platforms/``, not code (ADR 0008). For now it lists
the platform's system events: each under the plan name a tracking plan shows it by, the
name or call the SDK actually sends, and any equivalent names that differ in words
rather than spelling. Loading fails loudly on a missing file, malformed YAML, or an
invalid schema, the same as governance profiles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

_PLATFORMS_DIR = Path(__file__).resolve().parents[2] / "platforms"


class PlatformError(Exception):
    """A platform file could not be loaded or is invalid."""


class SystemEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None when the event is not one plan event: $autocapture is a stream the plan's
    # actions are built on, and the identity events are calls the plan models already.
    plan_name: Optional[str] = None
    sent_as: str
    records: str
    sent_by: str
    equivalents: list[str] = []


class Platform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str
    # The docs the system events were checked against, and when.
    docs: list[str]
    checked: str
    system_events: list[SystemEvent]

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

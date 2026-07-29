"""Fixture schema for the eval harness.

A fixture is a claim about engine behaviour with a note naming what it pins down.
Every model forbids extra keys so a typo'd fixture key fails loudly at load with
its own line, instead of silently becoming an unscored expectation.

Expectations are three-state: a ``None`` field is unscored — recorded in the
results, never failed. The live tier extends :class:`DefinitionExpect` with new
optional fields (name_shape, category, property_names, findings) under the same
rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict

from app.governance import GovernanceProfile, load_profile
from app.models import Decision

_GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "governance"


class NameFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    note: str
    profile: str
    name: str
    expect_valid: bool
    expect_fragment: Optional[str] = None


class DefinitionExpect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Optional[Decision] = None
    failed_rules: Optional[list[str]] = None
    pii_flagged: Optional[bool] = None
    flags_present: Optional[bool] = None
    duplicate_check_present: Optional[bool] = None


class DefinitionFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    note: str
    profile: str
    definition: dict
    request_kind: Optional[str] = None
    existing_event: Optional[str] = None
    expect: DefinitionExpect
    xfail_reason: Optional[str] = None


class FixtureSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    names: list[NameFixture]
    definitions: list[DefinitionFixture]


def load_fixtures(path: str | Path) -> FixtureSet:
    data = yaml.safe_load(Path(path).read_text())
    return FixtureSet.model_validate(data)


def resolve_profile(value: str) -> GovernanceProfile:
    """Load the governance profile a fixture pins, resolved against
    ``<repo>/governance/``. Fixtures name a template explicitly and must never
    read ``active.yaml`` — otherwise flipping the active profile silently
    rewrites every expectation."""
    path = (_GOVERNANCE_DIR / value).resolve()
    if path == (_GOVERNANCE_DIR / "active.yaml").resolve():
        raise ValueError(
            "fixtures must pin a template explicitly, never active.yaml"
        )
    return load_profile(path)

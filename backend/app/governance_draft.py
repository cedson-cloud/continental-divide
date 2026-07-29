"""Draft a governance profile from curated setup-wizard answers.

Everything here happens in memory: the YAML is built as a string and validated
through the same Pydantic model the engine loads profiles with. Nothing in this
module reads or writes the filesystem, and it must stay that way — the app has
no auth, so a write path here would be an unauthenticated write into the repo.

Every input is a choice from a curated set. The naming convention must be one of
the two identifiers ``EventNamingConfig`` already accepts, destinations come from
the existing destination list, and PII entries are additive from a curated list.
No user-supplied regex, ever.
"""

from __future__ import annotations

from typing import Literal, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .governance import DEFAULT_PROFILE, GovernanceError, profile_from_dict

BusinessType = Literal["ecommerce", "saas", "marketplace", "media", "fintech"]
CurrentPlatform = Literal["segment", "posthog", "amplitude", "mixpanel", "none"]
CallSide = Literal["client", "server", "both"]
NamingConvention = Literal["title_case_object_action", "snake_case_object_action"]
Destination = Literal[
    "warehouse", "product_analytics", "crm", "engagement", "advertising"
]
PiiAddition = Literal[
    "device_id",
    "latitude",
    "longitude",
    "national_id",
    "passport_number",
    "drivers_license",
    "bank_account",
]

CURATED_DESTINATIONS = get_args(Destination)
CURATED_PII_ADDITIONS = get_args(PiiAddition)

# Matches the source URLs on the committed templates for the same conventions.
_CONVENTION_SOURCES = {
    "title_case_object_action": "https://www.twilio.com/docs/segment/protocols/tracking-plan/best-practices",
    "snake_case_object_action": "https://posthog.com/docs/libraries/python",
}
_CONVENTION_SLUGS = {
    "title_case_object_action": "title-case",
    "snake_case_object_action": "snake-case",
}


class GovernanceDraftAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_type: BusinessType
    current_platform: CurrentPlatform
    call_side: CallSide
    naming_convention: NamingConvention
    destinations: list[Destination] = Field(default_factory=list, max_length=8)
    pii_additions: list[PiiAddition] = Field(default_factory=list, max_length=16)


def profile_name(answers: GovernanceDraftAnswers) -> str:
    return f"{answers.business_type}-{_CONVENTION_SLUGS[answers.naming_convention]}"


def build_profile_yaml(answers: GovernanceDraftAnswers) -> str:
    """Render a standalone profile (no ``extends``, so it validates without any
    file lookup). Word lists and the base PII blocklist come from the built-in
    default; the answers only choose among curated values."""
    naming = DEFAULT_PROFILE.event_naming
    blocklist = list(DEFAULT_PROFILE.pii.blocklist)
    for entry in answers.pii_additions:
        if entry not in blocklist:
            blocklist.append(entry)
    profile = {
        "version": 1,
        "name": profile_name(answers),
        "source": _CONVENTION_SOURCES[answers.naming_convention],
        "event_naming": {
            "convention": answers.naming_convention,
            "connectors": list(naming.connectors),
            "particles": list(naming.particles),
            "irregular_past": list(naming.irregular_past),
        },
        "property_naming": {"convention": "snake_case"},
        "pii": {"mode": "flag", "blocklist": blocklist},
        "categories": [],
        "destinations": list(answers.destinations),
    }
    header = (
        "# Drafted by the governance setup wizard. Nothing is enforced until a human\n"
        "# commits this file to governance/templates/ and points active.yaml at it.\n"
        f"# Answers: business type {answers.business_type}, "
        f"current platform {answers.current_platform}, "
        f"calls from {answers.call_side}.\n"
    )
    return header + yaml.safe_dump(profile, sort_keys=False, default_flow_style=False)


def validate_profile_yaml(text: str) -> list[str]:
    """Empty list means the text loads and validates as a governance profile."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"malformed YAML: {exc}"]
    if not isinstance(data, dict):
        return ["profile must be a YAML mapping"]
    try:
        profile_from_dict(data, label="<draft>")
    except GovernanceError as exc:
        return [str(exc)]
    return []

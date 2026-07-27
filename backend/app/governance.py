"""Governance profiles: the rules-as-configuration layer.

A profile is a human-authored YAML file describing the naming conventions, PII
blocklist, and category list a plan should be vetted against. Profiles can extend
one another (child deep-merged over parent, cycles rejected), so a team template
can override one setting and inherit the rest. Loading fails loudly on a missing
file, malformed YAML, a missing extends target, or an invalid schema — there is no
silent fallback. :data:`DEFAULT_PROFILE` reproduces the built-in constants in
``rules.py``, so a caller that supplies no profile behaves exactly as before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .rules import _CONNECTORS, _IRREGULAR_PAST, _PARTICLES, _PII_BLOCKLIST


class GovernanceError(Exception):
    """A governance profile could not be loaded or is invalid."""


class EventNamingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention: Literal["title_case_object_action", "snake_case_object_action"]
    connectors: list[str]
    particles: list[str]
    irregular_past: list[str]


class PropertyNamingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention: Literal["snake_case"]


class PiiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "block" is reserved for a future mode; only flagging is implemented.
    mode: Literal["flag"]
    blocklist: list[str]


class GovernanceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str
    # URL the convention came from, for humans reading a report.
    source: Optional[str] = None
    # Path to a parent profile, resolved relative to the file that declares it.
    extends: Optional[str] = None
    event_naming: EventNamingConfig
    property_naming: PropertyNamingConfig
    pii: PiiConfig
    # Informational for now: vetting notes categories outside this list but the
    # intake pipeline's category rule is untouched.
    categories: list[str]
    # Where event data is allowed to be sent. Empty = no constraint, matching
    # how categories behave.
    destinations: list[str] = []


DEFAULT_PROFILE = GovernanceProfile(
    version=1,
    name="built-in default",
    event_naming=EventNamingConfig(
        convention="title_case_object_action",
        connectors=sorted(_CONNECTORS),
        particles=sorted(_PARTICLES),
        irregular_past=sorted(_IRREGULAR_PAST),
    ),
    property_naming=PropertyNamingConfig(convention="snake_case"),
    pii=PiiConfig(mode="flag", blocklist=list(_PII_BLOCKLIST)),
    categories=[],
)


# Fixed, illustrative names rendered on /admin. The same list runs under whatever
# convention is active, so the verdicts flip when the profile changes. These are
# not events in any plan.
EXAMPLE_EVENT_NAMES = [
    "Cart Cleared",
    "cart_cleared",
    "Product Added to Wishlist",
    "product_added_to_wishlist",
    "Newsletter Signed Up",
    "SKU Added",
    "Add to Cart",   # was "Add To Cart" — now fails on TENSE under Title Case
    "add_to_cart",   # new — fails on TENSE under snake_case
    "checkout",      # was "Checkout" — fails on word/token count under BOTH
]


def _read_yaml(path: Path) -> dict:
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise GovernanceError(f"governance profile not found: {path}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GovernanceError(f"malformed YAML in governance profile {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise GovernanceError(f"governance profile {path} must be a YAML mapping")
    return data


def _deep_merge(parent: dict, child: dict) -> dict:
    """Child wins; nested mappings merge recursively, everything else replaces."""
    merged = dict(parent)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_raw(path: Path, seen: tuple[Path, ...]) -> dict:
    path = path.resolve()
    if path in seen:
        chain = " -> ".join(str(p) for p in (*seen, path))
        raise GovernanceError(f"extends cycle in governance profiles: {chain}")
    data = _read_yaml(path)
    extends = data.get("extends")
    if extends:
        parent = _load_raw(path.parent / extends, (*seen, path))
        data = _deep_merge(parent, data)
    return data


def load_profile(path: str | Path) -> GovernanceProfile:
    path = Path(path)
    data = _load_raw(path, ())
    try:
        return GovernanceProfile.model_validate(data)
    except ValidationError as exc:
        raise GovernanceError(f"invalid governance profile {path}: {exc}") from exc


_ACTIVE_PROFILE_PATH = Path(__file__).resolve().parents[2] / "governance" / "active.yaml"


def load_active_profile() -> GovernanceProfile:
    """The enforced profile: ``governance/active.yaml`` if present, else the default."""
    if _ACTIVE_PROFILE_PATH.exists():
        return load_profile(_ACTIVE_PROFILE_PATH)
    return DEFAULT_PROFILE

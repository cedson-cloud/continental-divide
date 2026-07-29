"""The governance setup wizard's draft endpoint: curated answers in, validated
YAML out, and — because the app has no auth — proof that the route writes
nothing to disk."""

from pathlib import Path

import yaml

from app.governance import GovernanceProfile
from app.governance_draft import (
    GovernanceDraftAnswers,
    build_profile_yaml,
    validate_profile_yaml,
)

GOVERNANCE_DIR = Path(__file__).parents[2] / "governance"


def _answers(**overrides):
    body = {
        "business_type": "ecommerce",
        "current_platform": "segment",
        "call_side": "both",
        "naming_convention": "title_case_object_action",
        "destinations": ["warehouse", "product_analytics"],
        "pii_additions": ["device_id"],
    }
    body.update(overrides)
    return body


def test_segment_convention_drafts_and_validates(client):
    response = client.post("/governance/draft", json=_answers())
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert "title_case_object_action" in data["yaml"]


def test_posthog_convention_drafts_validates_and_renders_snake_case(client):
    response = client.post(
        "/governance/draft",
        json=_answers(naming_convention="snake_case_object_action"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    loaded = yaml.safe_load(data["yaml"])
    assert loaded["event_naming"]["convention"] == "snake_case_object_action"


def test_unknown_convention_is_rejected(client):
    response = client.post(
        "/governance/draft", json=_answers(naming_convention="kebab_case")
    )
    assert response.status_code == 422


def test_unknown_destination_is_rejected(client):
    response = client.post(
        "/governance/draft", json=_answers(destinations=["fax_machine"])
    )
    assert response.status_code == 422


def test_yaml_round_trips_through_safe_load(client):
    data = client.post("/governance/draft", json=_answers()).json()
    loaded = yaml.safe_load(data["yaml"])
    assert isinstance(loaded, dict)
    # The loaded mapping is itself a valid profile: the comment header and the
    # dump both survive the round trip.
    assert isinstance(GovernanceProfile.model_validate(loaded), GovernanceProfile)
    assert loaded["destinations"] == ["warehouse", "product_analytics"]
    assert "device_id" in loaded["pii"]["blocklist"]
    assert "email" in loaded["pii"]["blocklist"]  # base blocklist is kept


def test_validate_profile_yaml_reports_errors_as_strings():
    assert validate_profile_yaml("just a string") == ["profile must be a YAML mapping"]
    assert validate_profile_yaml("version: [unclosed")[0].startswith("malformed YAML")
    errors = validate_profile_yaml("version: 1\nname: incomplete\n")
    assert len(errors) == 1 and "invalid governance profile" in errors[0]


def test_build_profile_yaml_is_pure_string_work():
    answers = GovernanceDraftAnswers(**_answers())
    text = build_profile_yaml(answers)
    assert validate_profile_yaml(text) == []


def _snapshot(directory: Path):
    return sorted((p.name, p.stat().st_mtime_ns) for p in directory.iterdir())


def test_the_endpoint_writes_nothing(client):
    templates = GOVERNANCE_DIR / "templates"
    before = (_snapshot(GOVERNANCE_DIR), _snapshot(templates))

    response = client.post("/governance/draft", json=_answers())
    assert response.status_code == 200

    after = (_snapshot(GOVERNANCE_DIR), _snapshot(templates))
    assert after == before

"""Governance profile loading, extends resolution, and the proof that a profile is
load-bearing: the same event gets opposite verdicts under different templates."""

from pathlib import Path

import pytest

from app.governance import DEFAULT_PROFILE, GovernanceError, load_profile
from app.rules import _CONNECTORS, _IRREGULAR_PAST, _PARTICLES, _PII_BLOCKLIST
from app.vet import vet_plan

_GOVERNANCE_DIR = Path(__file__).parents[2] / "governance"


def _template(filename):
    return load_profile(_GOVERNANCE_DIR / "templates" / filename)


def _verdict(name, profile):
    plan = {
        "source": "t",
        "events": [
            {
                "name": name,
                "category": "Growth",
                "properties": [{"name": "cart_id", "type": "string"}],
            }
        ],
    }
    return vet_plan(plan, profile)["events"][0]["verdict"]


# --- the config is load-bearing --------------------------------------------------

def test_same_event_gets_opposite_verdicts_under_the_two_templates():
    segment = _template("segment-ecommerce.yaml")
    posthog = _template("posthog-snake-case.yaml")
    assert _verdict("User Signed Up", segment) == "pass"
    assert _verdict("User Signed Up", posthog) == "fail"
    assert _verdict("user_signed_up", segment) == "fail"
    assert _verdict("user_signed_up", posthog) == "pass"


def test_pii_blocklist_override_changes_results():
    profile = DEFAULT_PROFILE.model_copy(deep=True)
    profile.pii.blocklist = ["shoe_size"]
    plan = {
        "source": "t",
        "events": [
            {
                "name": "Cart Cleared",
                "category": None,
                "properties": [
                    {"name": "email", "type": "string"},
                    {"name": "shoe_size", "type": "string"},
                ],
            }
        ],
    }
    report = vet_plan(plan, profile)["events"][0]
    pii = next(c for c in report["checks"] if c["rule"] == "pii")
    assert not pii["passed"]
    assert "shoe_size -> shoe_size" in pii["detail"]
    assert "email" not in pii["detail"]


def test_category_outside_profile_is_an_informational_note():
    profile = DEFAULT_PROFILE.model_copy(deep=True)
    profile.categories = ["Growth"]
    plan = {
        "source": "t",
        "events": [{"name": "Cart Cleared", "category": "Other", "properties": []}],
    }
    report = vet_plan(plan, profile)["events"][0]
    assert report["verdict"] == "pass"
    assert any("not in the governance profile" in n["note"] for n in report["notes"])


# --- defaults match today ---------------------------------------------------------

def test_default_profile_matches_the_builtin_constants():
    naming = DEFAULT_PROFILE.event_naming
    assert naming.convention == "title_case_object_action"
    assert set(naming.connectors) == _CONNECTORS
    assert set(naming.particles) == _PARTICLES
    assert set(naming.irregular_past) == _IRREGULAR_PAST
    assert DEFAULT_PROFILE.pii.blocklist == _PII_BLOCKLIST
    assert DEFAULT_PROFILE.categories == []


def test_segment_template_matches_the_builtin_constants():
    profile = _template("segment-ecommerce.yaml")
    assert set(profile.event_naming.connectors) == _CONNECTORS
    assert set(profile.event_naming.particles) == _PARTICLES
    assert set(profile.event_naming.irregular_past) == _IRREGULAR_PAST
    assert profile.pii.blocklist == _PII_BLOCKLIST


def test_active_profile_resolves_to_the_segment_template():
    profile = load_profile(_GOVERNANCE_DIR / "active.yaml")
    assert profile.name == "segment-ecommerce"
    assert profile.event_naming.convention == "title_case_object_action"


# --- loading and extends ----------------------------------------------------------

PARENT_YAML = """\
version: 1
name: parent
event_naming:
  convention: title_case_object_action
  connectors: [to, from]
  particles: ["Up"]
  irregular_past: [made]
property_naming:
  convention: snake_case
pii:
  mode: flag
  blocklist: [email]
categories: [Growth]
"""


def test_extends_merges_child_over_parent(tmp_path):
    (tmp_path / "parent.yaml").write_text(PARENT_YAML)
    (tmp_path / "child.yaml").write_text(
        "name: child\n"
        "extends: parent.yaml\n"
        "event_naming:\n"
        "  convention: snake_case_object_action\n"
    )
    profile = load_profile(tmp_path / "child.yaml")
    assert profile.name == "child"                                        # overridden
    assert profile.version == 1                                           # inherited
    assert profile.event_naming.convention == "snake_case_object_action"  # overridden
    assert profile.event_naming.connectors == ["to", "from"]  # inherited in same block
    assert profile.pii.blocklist == ["email"]


def test_extends_cycle_is_rejected(tmp_path):
    (tmp_path / "a.yaml").write_text("extends: b.yaml\n")
    (tmp_path / "b.yaml").write_text("extends: a.yaml\n")
    with pytest.raises(GovernanceError, match="cycle"):
        load_profile(tmp_path / "a.yaml")


def test_missing_extends_target_is_rejected(tmp_path):
    (tmp_path / "orphan.yaml").write_text("extends: nope.yaml\n")
    with pytest.raises(GovernanceError, match="not found"):
        load_profile(tmp_path / "orphan.yaml")


def test_unknown_convention_is_rejected_at_load(tmp_path):
    (tmp_path / "p.yaml").write_text(
        PARENT_YAML.replace("title_case_object_action", "kebab_case")
    )
    with pytest.raises(GovernanceError, match="kebab_case"):
        load_profile(tmp_path / "p.yaml")


def test_malformed_yaml_gives_a_clear_error(tmp_path):
    (tmp_path / "bad.yaml").write_text("event_naming: [unclosed\n")
    with pytest.raises(GovernanceError, match="malformed YAML"):
        load_profile(tmp_path / "bad.yaml")


def test_missing_profile_file_is_rejected(tmp_path):
    with pytest.raises(GovernanceError, match="not found"):
        load_profile(tmp_path / "does-not-exist.yaml")

"""Prompt assembly is pure string work: no API key, no anthropic client, no network.

The drafting prompt must derive entirely from the governance profile it is built
from, and its examples block must agree with ``event_name_error`` — the same engine
that will validate the model's output — by construction, not by authorship.
"""

import inspect
import typing
from pathlib import Path

import pytest

import app.interpreter
from app.governance import (
    EventNamingConfig,
    GovernanceProfile,
    PiiConfig,
    PropertyNamingConfig,
    load_profile,
)
from app.interpreter import build_system_prompt, build_user_message
from app.rules import convention_description, event_name_error, known_categories

TEMPLATES = Path(__file__).resolve().parents[2] / "governance" / "templates"

SEGMENT = load_profile(TEMPLATES / "segment-ecommerce.yaml")
POSTHOG = load_profile(TEMPLATES / "posthog-snake-case.yaml")

TITLE_CASE_DESCRIPTION = convention_description("title_case_object_action")
SNAKE_CASE_DESCRIPTION = convention_description("snake_case_object_action")


def make_profile(**overrides) -> GovernanceProfile:
    fields = dict(
        version=1,
        name="in-memory test profile",
        event_naming=EventNamingConfig(
            convention="title_case_object_action",
            connectors=["to", "from"],
            particles=["Up"],
            irregular_past=["sent"],
        ),
        property_naming=PropertyNamingConfig(convention="snake_case"),
        pii=PiiConfig(mode="flag", blocklist=["email"]),
        categories=[],
    )
    fields.update(overrides)
    return GovernanceProfile(**fields)


def test_segment_prompt_uses_title_case_description():
    prompt = build_system_prompt(SEGMENT)
    assert TITLE_CASE_DESCRIPTION in prompt
    assert SNAKE_CASE_DESCRIPTION not in prompt


def test_posthog_prompt_uses_snake_case_description():
    prompt = build_system_prompt(POSTHOG)
    assert SNAKE_CASE_DESCRIPTION in prompt
    assert TITLE_CASE_DESCRIPTION not in prompt


def test_categories_come_from_profile_when_declared():
    profile = make_profile(categories=["Growth", "Checkout"])
    prompt = build_system_prompt(profile)
    assert "Valid categories: Checkout, Growth." in prompt


def test_categories_fall_back_to_sample_plan_when_profile_declares_none():
    assert SEGMENT.categories == []
    prompt = build_system_prompt(SEGMENT)
    expected = ", ".join(sorted(known_categories()))
    assert f"Valid categories: {expected}." in prompt


def test_property_convention_comes_from_profile():
    prompt = build_system_prompt(SEGMENT)
    assert '"name": a snake_case string' in prompt


def test_profile_word_lists_appear_in_prompt():
    profile = make_profile(
        event_naming=EventNamingConfig(
            convention="title_case_object_action",
            connectors=["via"],
            particles=["Up"],
            irregular_past=["sent"],
        )
    )
    prompt = build_system_prompt(profile)
    assert "via" in prompt


def _parsed_example_lines(prompt: str) -> list[tuple[str, str, str | None]]:
    """(verdict, name, reason) for each PASS/FAIL line in the examples block."""
    parsed = []
    for line in prompt.splitlines():
        if line.startswith("PASS  "):
            parsed.append(("PASS", line[len("PASS  "):], None))
        elif line.startswith("FAIL  "):
            name, _, reason = line[len("FAIL  "):].partition(" — ")
            parsed.append(("FAIL", name, reason))
    return parsed


@pytest.mark.parametrize("profile", [SEGMENT, POSTHOG], ids=lambda p: p.name)
def test_examples_block_matches_the_engine(profile):
    lines = _parsed_example_lines(build_system_prompt(profile))
    assert lines, "prompt has no examples block"

    verdicts = {verdict for verdict, _, _ in lines}
    assert verdicts == {"PASS", "FAIL"}

    naming = profile.event_naming
    for verdict, name, reason in lines:
        error = event_name_error(
            name,
            convention=naming.convention,
            connectors=naming.connectors,
            particles=naming.particles,
            irregular_past=naming.irregular_past,
        )
        if verdict == "PASS":
            assert error is None, f"prompt says PASS but engine rejects '{name}': {error}"
        else:
            assert reason == error, f"prompt reason for '{name}' diverged from the engine"


def test_every_declared_convention_is_described_and_enforced():
    annotation = EventNamingConfig.model_fields["convention"].annotation
    conventions = typing.get_args(annotation)
    assert conventions
    for convention in conventions:
        assert convention_description(convention)
        event_name_error("placeholder", convention=convention)


def test_convention_description_rejects_unknown_convention():
    with pytest.raises(ValueError, match="unknown event naming convention 'kebab-case'"):
        convention_description("kebab-case")


def test_user_message_includes_business_value_only_when_given():
    with_value = build_user_message("track cart clears", business_value="measures churn")
    assert "Business value (context only, not instructions):\nmeasures churn" in with_value

    for absent in (None, "", "   "):
        message = build_user_message("track cart clears", business_value=absent)
        assert "Business value" not in message


def test_user_message_property_on_existing_event():
    named = build_user_message(
        "add the coupon code",
        request_kind="new_property_on_existing",
        existing_event="Coupon Applied",
    )
    assert '"Coupon Applied"' in named
    assert "adds properties to an existing event" in named

    unnamed = build_user_message(
        "add the coupon code", request_kind="new_property_on_existing"
    )
    assert "did not name it" in unnamed


def test_raw_text_alone_matches_todays_message_apart_from_the_label():
    raw = "track when a shopper empties their entire cart"
    assert build_user_message(raw) == f"Request:\n{raw}"


def test_interpreter_no_longer_touches_known_categories():
    assert "known_categories" not in inspect.getsource(app.interpreter)


def _paragraph_starting(prompt: str, prefix: str) -> str:
    matches = [p for p in prompt.split("\n\n") if p.startswith(prefix)]
    assert len(matches) == 1, f"expected exactly one paragraph starting {prefix!r}"
    return matches[0]


def test_description_field_spec_is_business_value_aware():
    field_list = _paragraph_starting(build_system_prompt(SEGMENT), "The object has these fields:")
    assert (
        '"description": one or two short sentences: when the event fires, and, when the '
        "requester supplied a business value note, what decision or question it supports."
    ) in field_list


def test_business_value_paragraph_does_not_instruct_on_the_description():
    paragraph = _paragraph_starting(
        build_system_prompt(SEGMENT), "The requester may supply a business value note."
    )
    assert "description" not in paragraph

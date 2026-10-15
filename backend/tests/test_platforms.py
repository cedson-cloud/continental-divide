"""Platform files: the system events each SDK sends on its own, under the plan names a
tracking plan shows them by (ADR 0009)."""

from pathlib import Path

import pytest

from app.governance import GovernanceError, load_profile
from app.platforms import PlatformError, load_platform, render_plan_name
from app.rules import event_name_error

TEMPLATES_DIR = Path(__file__).parents[2] / "governance" / "templates"


@pytest.mark.parametrize(
    "platform, sent_as",
    [("posthog", "$pageview"), ("segment", "a page call")],
)
def test_page_viewed_is_a_system_event_on_both_shipped_platforms(platform, sent_as):
    events = {e.plan_name: e for e in load_platform(platform).system_events}
    assert events["Page Viewed"].sent_as == sent_as


@pytest.mark.parametrize("platform", ["posthog", "segment"])
@pytest.mark.parametrize(
    "convention", ["title_case_object_action", "snake_case_object_action"]
)
def test_every_plan_name_follows_both_conventions_once_rendered(platform, convention):
    for event in load_platform(platform).system_events:
        for name in filter(None, [event.plan_name, *event.equivalents]):
            rendered = render_plan_name(name, convention)
            assert event_name_error(rendered, convention=convention) is None, rendered


def test_a_plan_name_is_rendered_in_the_profile_convention():
    assert render_plan_name("Page Viewed", "title_case_object_action") == "Page Viewed"
    assert render_plan_name("Page Viewed", "snake_case_object_action") == "page_viewed"


def test_a_platform_file_naming_one_event_twice_fails_at_load(tmp_path):
    (tmp_path / "broken.yaml").write_text(
        "version: 1\nname: broken\nchecked: '2026-10-07'\ndocs: []\n"
        "system_events:\n"
        "  - {plan_name: Page Viewed, sent_as: a, records: r, sent_by: s,"
        " sources: ['https://x']}\n"
        "  - {plan_name: Screen Viewed, sent_as: b, records: r, sent_by: s,"
        " sources: ['https://x'], equivalents: [Page Viewed]}\n"
    )
    with pytest.raises(PlatformError, match="'Page Viewed' names more than one"):
        load_platform("broken", directory=tmp_path)


def test_a_missing_platform_file_fails_at_load(tmp_path):
    with pytest.raises(PlatformError, match="platform file not found"):
        load_platform("nowhere", directory=tmp_path)


def test_a_profile_naming_an_unknown_platform_fails_at_load(tmp_path):
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        f"extends: {TEMPLATES_DIR / 'segment-ecommerce.yaml'}\nname: odd\n"
        "platform: nowhere\n"
    )
    with pytest.raises(GovernanceError, match="platform file not found"):
        load_profile(profile)


@pytest.mark.parametrize(
    "template, platform",
    [("segment-ecommerce", "segment"), ("posthog-snake-case", "posthog")],
)
def test_each_shipped_template_names_its_platform(template, platform):
    assert load_profile(TEMPLATES_DIR / f"{template}.yaml").platform == platform


def _every_claim(platform):
    """Each common field, system event and reserved name, with a label for messages."""
    yield from ((f.path, f) for f in platform.common_fields)
    yield from ((e.plan_name or e.sent_as, e) for e in platform.system_events)
    yield from ((r.name, r) for r in platform.reserved_names)


@pytest.mark.parametrize("platform", ["posthog", "segment"])
def test_every_source_is_a_link(platform):
    for label, claim in _every_claim(load_platform(platform)):
        assert all(s.startswith("https://") for s in claim.sources), label


@pytest.mark.parametrize("platform", ["posthog", "segment"])
def test_a_disputed_claim_always_says_how_the_sources_disagree(platform):
    loaded = load_platform(platform)
    claims = [*_every_claim(loaded)]
    claims += [
        (f"{label}.{p.name}", p)
        for label, claim in claims
        for p in getattr(claim, "properties", None) or []
    ]
    for label, claim in claims:
        if claim.evidence == "disputed":
            assert claim.note, f"{label} is disputed with no note"


def test_posthog_sends_application_became_active_from_react_native_only():
    events = {e.plan_name: e for e in load_platform("posthog").system_events}
    foregrounded = events["Application Foregrounded"]
    assert foregrounded.sent_as == "Application Became Active"
    assert set(foregrounded.default_on) == {"posthog-react-native"}
    assert "from_background" in foregrounded.note
    opened = {p.name for p in events["Application Opened"].properties}
    assert "from_background" in opened


def test_segment_experiment_viewed_lists_the_spec_properties_and_no_invented_equivalent():
    events = {e.plan_name: e for e in load_platform("segment").system_events}
    experiment = events["Experiment Viewed"]
    assert experiment.equivalents == []
    assert [p.name for p in experiment.properties] == [
        "experiment_id",
        "experiment_name",
        "variation_id",
        "variation_name",
    ]


def test_lifecycle_defaults_differ_by_segment_library():
    events = {e.plan_name: e for e in load_platform("segment").system_events}
    assert events["Application Opened"].default_on == {
        "analytics-swift": True,
        "analytics-kotlin": False,
        "analytics-react-native": False,
    }


def test_properties_left_out_read_as_not_listed_not_as_none():
    events = {e.plan_name: e for e in load_platform("segment").system_events}
    assert events["Screen Viewed"].properties is None
    assert events["Application Backgrounded"].properties == []


_V2_HEAD = (
    "version: 2\nname: broken\nchecked: '2026-10-15'\ndocs: []\n"
    "libraries:\n  - {id: web-sdk, name: Web, surface: browser}\n"
)


@pytest.mark.parametrize(
    "body, message",
    [
        (
            "common_fields:\n  - {path: a, plain_name: A, group: G,"
            " libraries: [nowhere], sources: ['https://x']}\nsystem_events: []\n",
            "unknown library: nowhere",
        ),
        (
            "system_events:\n  - {plan_name: Page Viewed, sent_as: a, records: r,"
            " sent_by: s, sources: ['https://x']}\nreserved_names:\n"
            "  - {name: Page Viewed, records: r,"
            " sent_by: s, sources: ['https://x']}\n",
            "'Page Viewed' is both reserved and a system event",
        ),
        (
            "system_events:\n  - {plan_name: Page Viewed, sent_as: a, records: r,"
            " sent_by: s, sources: ['https://x'],"
            " properties: [{name: url}, {name: url}]}\n",
            "'Page Viewed' lists a property twice",
        ),
        (
            "system_events:\n  - {plan_name: Page Viewed, sent_as: a, records: r,"
            " sent_by: s}\n",
            "'Page Viewed' cites no source",
        ),
    ],
)
def test_an_inconsistent_platform_file_fails_at_load(tmp_path, body, message):
    (tmp_path / "broken.yaml").write_text(_V2_HEAD + body)
    with pytest.raises(PlatformError, match=message):
        load_platform("broken", directory=tmp_path)

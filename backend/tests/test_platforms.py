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
        "  - {plan_name: Page Viewed, sent_as: a, records: r, sent_by: s}\n"
        "  - {plan_name: Screen Viewed, sent_as: b, records: r, sent_by: s,"
        " equivalents: [Page Viewed]}\n"
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

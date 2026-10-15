"""The data dictionary shows what the platform sends on its own (ADR 0011).

A system event carries the properties its platform file lists, with the evidence
behind each one, and says when they are not listed yet rather than showing none. The
platform's common fields, reserved names and not-listed-yet items come back once,
beside the events, never as events themselves.
"""

from pathlib import Path

from app.catalog_view import build_catalog_view

from .test_catalog_view import _approved_request, _event

POSTHOG = Path(__file__).parents[2] / "governance" / "templates" / "posthog-snake-case.yaml"


def test_a_system_event_carries_the_properties_its_platform_lists(client):
    opened = _event(client.get("/catalog").json(), "Application Opened", "system_event")
    assert opened["properties_listed"] is True
    props = {p["name"]: p for p in opened["properties"]}
    assert set(props) == {
        "from_background",
        "version",
        "build",
        "referring_application",
        "url",
    }
    assert props["from_background"]["type"] == "boolean"
    assert props["from_background"]["source"] == "system_event"
    assert props["version"]["evidence"] == "sdk_code"
    assert props["url"]["note"] == "iOS only."
    assert opened["default_on"] == {
        "analytics-swift": True,
        "analytics-kotlin": False,
        "analytics-react-native": False,
    }
    assert opened["sources"]


def test_unlisted_properties_and_no_properties_read_differently(client):
    body = client.get("/catalog").json()
    screen = _event(body, "Screen Viewed", "system_event")
    backgrounded = _event(body, "Application Backgrounded", "system_event")
    assert screen["properties"] == [] and screen["properties_listed"] is False
    assert backgrounded["properties"] == [] and backgrounded["properties_listed"] is True


def test_a_disputed_event_says_how_its_sources_disagree(client):
    updated = _event(client.get("/catalog").json(), "Application Updated", "system_event")
    assert updated["evidence"] == "disputed"
    assert "instead of Application Opened" in updated["note"]


def test_a_request_for_a_property_the_platform_sends_is_shown_once(client, storage):
    request_id = _approved_request(
        storage,
        "Application Opened",
        properties=[{"name": "from_background", "type": "boolean"}],
        request_kind="new_property_on_existing",
        existing_event="Application Opened",
    )
    opened = _event(client.get("/catalog").json(), "Application Opened", "system_event")
    rows = [p for p in opened["properties"] if p["name"] == "from_background"]
    assert len(rows) == 1
    assert rows[0]["source"] == "system_event"
    assert rows[0]["also_requested_by"] == [request_id]


def test_the_platform_comes_back_once_beside_the_events(client):
    body = client.get("/catalog").json()
    platform = body["platform"]
    assert platform["name"] == "segment"
    assert platform["checked"] == "2026-10-15"
    assert len(platform["common_fields"]) == 40
    assert "analytics.js" in {lib["id"] for lib in platform["libraries"]}
    assert platform["not_listed_yet"]
    reserved = {r["name"] for r in platform["reserved_names"]}
    assert "Push Notification Received" in reserved
    assert not reserved & {e["name"] for e in body["events"]}
    assert body["counts"]["system_events"] == 10


def test_common_field_paths_keep_the_platforms_own_keys(client, monkeypatch):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", POSTHOG)
    platform = client.get("/catalog").json()["platform"]
    assert platform["name"] == "posthog"
    paths = {f["path"] for f in platform["common_fields"]}
    assert {"$current_url", "utm_source", "$app_version"} <= paths


def test_no_profile_means_no_platform(storage):
    view = build_catalog_view(storage, None)
    assert view.platform is None
    assert view.counts.system_events == 0

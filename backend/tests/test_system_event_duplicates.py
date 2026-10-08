"""A custom event that duplicates what the SDK already sends is caught (ADR 0009).

System events join the corpus under their plan names, so asking for `Page Viewed` is an
exact duplicate of an event the platform sends on its own, and its variants are near
duplicates. Nothing here rejects: these are findings for a human, like any duplicate.
"""

from pathlib import Path

import pytest

from app.governance import DEFAULT_PROFILE, load_profile
from app.models import EventDefinition
from app.rules import evaluate

TEMPLATES_DIR = Path(__file__).parents[2] / "governance" / "templates"
SEGMENT = TEMPLATES_DIR / "segment-ecommerce.yaml"
POSTHOG = TEMPLATES_DIR / "posthog-snake-case.yaml"


def _checks(name: str, profile_path: Path | None) -> dict:
    profile = load_profile(profile_path) if profile_path else DEFAULT_PROFILE
    definition = EventDefinition(name=name, category="Browsing", properties=[])
    return {c.rule: c for c in evaluate(definition, profile).checks}


@pytest.mark.parametrize(
    "name, profile, sent_as",
    [
        ("Page Viewed", SEGMENT, "page call"),
        ("page_viewed", POSTHOG, "$pageview"),
        ("screen_viewed", POSTHOG, "$screen"),
        ("Application Opened", SEGMENT, "Application Opened"),
    ],
)
def test_asking_for_a_system_event_by_its_plan_name_is_an_exact_duplicate(
    name, profile, sent_as
):
    checks = _checks(name, profile)
    assert not checks["duplicate"].passed
    assert "system event" in checks["duplicate"].detail
    assert sent_as in checks["duplicate"].detail


@pytest.mark.parametrize(
    "name, profile, plan_name",
    [
        ("Pages Viewed", SEGMENT, "Page Viewed"),
        ("Page Loaded", SEGMENT, "Page Viewed"),
        ("page_loaded", POSTHOG, "page_viewed"),
        ("App Launched", SEGMENT, "Application Opened"),
    ],
)
def test_a_variant_or_listed_equivalent_is_a_near_duplicate(name, profile, plan_name):
    checks = _checks(name, profile)
    assert checks["duplicate"].passed
    assert not checks["near_duplicate"].passed
    assert f"'{plan_name}'" in checks["near_duplicate"].detail
    assert "system event" in checks["near_duplicate"].detail


@pytest.mark.parametrize(
    "name, profile", [("Coupon Shared", SEGMENT), ("coupon_shared", POSTHOG)]
)
def test_an_unrelated_event_is_not_flagged(name, profile):
    checks = _checks(name, profile)
    assert checks["duplicate"].passed and checks["near_duplicate"].passed


def test_a_profile_that_names_no_platform_has_no_system_events():
    checks = _checks("Page Viewed", None)
    assert checks["duplicate"].passed and checks["near_duplicate"].passed


def test_over_http_a_system_event_duplicate_needs_acknowledgment_to_publish(
    client, monkeypatch
):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", SEGMENT)
    created = client.post(
        "/requests/raw",
        json={
            "definition": {
                "name": "Page Viewed",
                "category": "Browsing",
                "properties": [],
            },
            "business_value": "counts page views for the content team",
        },
    ).json()
    assert created["status"] == "flagged_duplicate"
    request_id = created["id"]

    refused = client.post(
        f"/requests/{request_id}/decision", json={"decision": "approve"}
    )
    assert refused.status_code == 422
    assert client.get(f"/requests/{request_id}").json()["status"] == "flagged_duplicate"

    approved = client.post(
        f"/requests/{request_id}/decision",
        json={"decision": "approve", "findings_acknowledged": True},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "published"


def test_a_property_can_be_requested_on_a_system_event(client, monkeypatch):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", SEGMENT)
    created = client.post(
        "/requests/raw",
        json={
            "definition": {
                "name": "Page Viewed",
                "category": "Browsing",
                "properties": [{"name": "page_section", "type": "string"}],
            },
            "business_value": "compares engagement across sections of the site",
            "request_kind": "new_property_on_existing",
            "existing_event": "Page Viewed",
        },
    ).json()

    assert created["status"] == "pending_approval"
    checks = {c["rule"]: c for c in created["checks"]}
    assert checks["duplicate"].get("passed") is True
    assert "this property is being added to" in checks["duplicate"]["detail"]


def test_the_data_dictionary_lists_system_events_and_merges_properties_into_them(
    client, monkeypatch
):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", SEGMENT)
    created = client.post(
        "/requests/raw",
        json={
            "definition": {
                "name": "Page Viewed",
                "category": "Browsing",
                "properties": [{"name": "page_section", "type": "string"}],
            },
            "business_value": "compares engagement across sections of the site",
            "request_kind": "new_property_on_existing",
            "existing_event": "Page Viewed",
        },
    ).json()
    client.post(f"/requests/{created['id']}/decision", json={"decision": "approve"})

    catalog = client.get("/catalog").json()

    events = {e["name"]: e for e in catalog["events"]}
    page_viewed = events["Page Viewed"]
    assert page_viewed["source"] == "system_event"
    assert page_viewed["category"] == "System events"
    assert page_viewed["sent_as"] == "a page call"
    assert [p["name"] for p in page_viewed["properties"]] == ["page_section"]
    assert events["Experiment Viewed"]["source"] == "system_event"
    assert catalog["counts"]["system_events"] == 8
    assert catalog["counts"]["property_additions_merged"] == 1
    assert catalog["counts"]["unresolved_targets"] == 0


def test_the_data_dictionary_names_system_events_in_the_profile_convention(
    client, monkeypatch
):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", POSTHOG)
    events = {e["name"]: e for e in client.get("/catalog").json()["events"]}
    assert events["page_viewed"]["sent_as"] == "$pageview"
    assert "$autocapture" not in events


# --- the vetter ------------------------------------------------------------------

def _vet(profile_path: Path, *names: str) -> dict:
    from app.vet import vet_plan

    events = [{"name": n, "category": "Browsing", "properties": []} for n in names]
    return vet_plan({"source": "acme", "events": events}, load_profile(profile_path))


def _notes(report: dict) -> str:
    return " ".join(n["note"] for n in report["notes"])


@pytest.mark.parametrize(
    "profile, name, sent",
    [
        (SEGMENT, "Page Viewed", "sent as a page call"),
        (SEGMENT, "Application Opened", "sent as Application Opened"),
        (POSTHOG, "page_viewed", "sent as $pageview"),
    ],
)
def test_the_vetter_recognizes_a_system_event_by_its_plan_name(profile, name, sent):
    report = _vet(profile, name)["events"][0]
    assert report["verdict"] == "system"
    assert sent in _notes(report)
    assert "do not also send it as a custom event" in _notes(report)


def test_the_vetter_gives_a_sent_name_its_plan_name():
    report = _vet(POSTHOG, "$pageview")["events"][0]
    assert report["verdict"] == "system"
    assert "show it in the plan as 'page_viewed'" in _notes(report)


def test_the_vetter_flags_a_custom_duplicate_the_plan_does_not_pair_with_one():
    result = _vet(SEGMENT, "Page Loaded", "Pages Viewed", "Coupon Shared")
    assert [r["verdict"] for r in result["events"]] == ["flag", "flag", "pass"]
    assert result["plan_checks"]["system_event_duplicates"] == [
        {"event": "Page Loaded", "system_event": "Page Viewed"},
        {"event": "Pages Viewed", "system_event": "Page Viewed"},
    ]


def test_the_vetter_reports_a_system_event_listed_under_two_names():
    result = _vet(POSTHOG, "$pageview", "page_viewed")
    assert [r["verdict"] for r in result["events"]] == ["system", "system"]
    assert result["plan_checks"]["system_events_listed_twice"] == [
        {"system_event": "page_viewed", "names": ["$pageview", "page_viewed"]}
    ]
    assert result["plan_checks"]["near_duplicates"] == []

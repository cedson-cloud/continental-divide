"""Unit tests for plan-scope vetting: the reused per-name rules, exact and near
duplicate detection, category notes, and defensive handling of foreign property
types."""

from app.vet import vet_plan


def _event(name, category="Growth", properties=("cart_id",)):
    return {
        "name": name,
        "category": category,
        "properties": [{"name": p, "type": "string"} for p in properties],
    }


def _vet(*events, source="acme"):
    return vet_plan({"source": source, "events": list(events)})


def _check(report, rule):
    return next(c for c in report["checks"] if c["rule"] == rule)


def test_clean_plan_passes():
    result = _vet(_event("Cart Cleared"), _event("Order Completed"))
    assert [r["verdict"] for r in result["events"]] == ["pass", "pass"]
    assert result["source"] == "acme"
    assert result["plan_checks"]["exact_duplicates"] == []
    assert result["plan_checks"]["near_duplicates"] == []


def test_rules_source_names_the_reused_functions():
    assert _vet()["rules_source"] == {
        "module": "app.rules",
        "functions": ["event_name_error", "property_name_error", "pii_hit"],
        "plan_scope_checks": ["exact_duplicates", "near_duplicates", "category_notes"],
    }


def test_naming_failure_fails_the_event():
    report = _vet(_event("add_to_cart"))["events"][0]
    assert report["verdict"] == "fail"
    assert not _check(report, "event_naming")["passed"]


def test_pii_flags_but_does_not_fail():
    report = _vet(_event("Newsletter Subscribed", properties=("email",)))["events"][0]
    assert report["verdict"] == "flag"
    assert not _check(report, "pii")["passed"]
    assert _check(report, "event_naming")["passed"]
    assert _check(report, "property_naming")["passed"]


def test_exact_duplicates_flag_clean_events():
    result = _vet(_event("Cart Cleared"), _event("Cart Cleared"))
    assert result["plan_checks"]["exact_duplicates"] == ["Cart Cleared"]
    assert [r["verdict"] for r in result["events"]] == ["flag", "flag"]
    # The same name twice is an exact duplicate, not a near-duplicate cluster.
    assert result["plan_checks"]["near_duplicates"] == []


def test_near_duplicate_cluster():
    result = _vet(
        _event("user_signed_up"),
        _event("userSignedUp"),
        _event("Signup Completed"),
    )
    # The first two normalize to the same string. "Signup Completed" shares the idea
    # but sits well below the 0.85 difflib threshold, so it stays out of the cluster.
    assert result["plan_checks"]["near_duplicates"] == [
        ["user_signed_up", "userSignedUp"]
    ]


def test_unrecognized_property_type_is_a_note_not_a_failure():
    event = {
        "name": "Cart Cleared",
        "category": "Growth",
        "properties": [{"name": "created_at", "type": "datetime"}],
    }
    report = vet_plan({"source": "acme", "events": [event]})["events"][0]
    assert report["verdict"] == "pass"
    assert report["notes"] == [
        {
            "severity": "low",
            "note": "unrecognized property type 'datetime' on 'created_at'",
        }
    ]


def test_category_notes():
    result = _vet(
        _event("Cart Cleared", category="Core Ordering"),
        _event("Order Completed", category="Core Ordering"),
        _event("Coupon Applied", category="Promotions"),
        _event("Page Viewed", category=None),
    )
    assert result["plan_checks"]["category_notes"] == {
        "declared_categories": ["Core Ordering", "Promotions"],
        "single_event_categories": ["Promotions"],
        "uncategorized_events": ["Page Viewed"],
    }


def test_empty_plan():
    result = vet_plan({"source": "acme", "events": []})
    assert result["events"] == []
    assert result["plan_checks"] == {
        "exact_duplicates": [],
        "near_duplicates": [],
        "category_notes": {
            "declared_categories": [],
            "single_event_categories": [],
            "uncategorized_events": [],
        },
    }

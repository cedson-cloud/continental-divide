"""Unit tests for plan-scope vetting: the reused per-name rules, exact and near
duplicate detection, category notes, and defensive handling of foreign property
types."""

import json
from pathlib import Path

from app.governance import load_profile
from app.vet import vet_plan

_REPO_ROOT = Path(__file__).parents[2]
_SAMPLE_PLAN_PATH = _REPO_ROOT / "backend" / "examples" / "vet_sample_plan.json"
_TEMPLATES_DIR = _REPO_ROOT / "governance" / "templates"


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


def test_unnamed_event_fails_structure_not_naming():
    result = vet_plan({"source": "acme", "events": [{"category": "Growth"}]})
    report = result["events"][0]
    assert report["index"] == 0
    assert report["name"] is None
    assert report["verdict"] == "fail"
    structure = _check(report, "structure")
    assert not structure["passed"]
    assert "event at index 0 has no name" in structure["detail"]
    # A name that isn't there cannot violate a naming convention.
    assert not any(c["rule"] == "event_naming" for c in report["checks"])


def test_two_unnamed_events_are_not_duplicates():
    result = vet_plan({"source": "acme", "events": [{}, {"name": "   "}]})
    assert [r["verdict"] for r in result["events"]] == ["fail", "fail"]
    assert result["plan_checks"]["exact_duplicates"] == []
    assert result["plan_checks"]["near_duplicates"] == []


def test_non_string_category_is_a_note_not_a_crash():
    event = {"name": "Cart Cleared", "category": ["Growth"], "properties": []}
    result = vet_plan({"source": "acme", "events": [event]})
    report = result["events"][0]
    assert report["verdict"] == "pass"
    assert report["category"] is None
    assert report["notes"] == [
        {
            "severity": "low",
            "note": "non-string category (list) treated as uncategorized",
        }
    ]
    assert result["plan_checks"]["category_notes"]["uncategorized_events"] == [
        "Cart Cleared"
    ]


def test_unnamed_property_is_a_structure_problem():
    event = {
        "name": "Cart Cleared",
        "category": "Growth",
        "properties": [{"type": "string"}],
    }
    report = vet_plan({"source": "acme", "events": [event]})["events"][0]
    assert report["verdict"] == "fail"
    structure = _check(report, "structure")
    assert not structure["passed"]
    assert "property at index 0 has a missing or empty name" in structure["detail"]
    # Not misreported as a convention violation.
    assert _check(report, "property_naming")["passed"]


def test_similarity_does_not_chain_across_a_cluster():
    # Consecutive names score ~0.9 against each other but the endpoints only 0.6.
    # Complete linkage breaks the run into tight pairs instead of one chained
    # five-name cluster.
    names = ["aaaaaaaaaa", "aaaaaaaaab", "aaaaaaaabb", "aaaaaaabbb", "aaaaaabbbb"]
    result = _vet(*[_event(n) for n in names])
    assert result["plan_checks"]["near_duplicates"] == [
        ["aaaaaaaaaa", "aaaaaaaaab"],
        ["aaaaaaaabb", "aaaaaaabbb"],
    ]


def test_summary_counts_match_the_assigned_verdicts():
    result = _vet(
        _event("Cart Cleared"),                                # pass
        _event("add_to_cart"),                                 # fail: naming
        _event("Newsletter Subscribed", properties=("email",)),  # flag: PII
        _event("Order Completed"),                             # flag: duplicate
        _event("Order Completed"),                             # flag: duplicate
    )
    summary = result["summary"]
    verdicts = [r["verdict"] for r in result["events"]]
    assert summary["events"] == len(verdicts)
    assert summary["pass"] == verdicts.count("pass")
    assert summary["flag"] == verdicts.count("flag")
    assert summary["fail"] == verdicts.count("fail")
    assert summary["pass"] + summary["flag"] + summary["fail"] == summary["events"]


def test_sample_plan_counts_are_pinned_under_both_templates():
    plan = json.loads(_SAMPLE_PLAN_PATH.read_text())
    segment = vet_plan(plan, load_profile(_TEMPLATES_DIR / "segment-ecommerce.yaml"))
    posthog = vet_plan(plan, load_profile(_TEMPLATES_DIR / "posthog-snake-case.yaml"))
    assert segment["summary"] == {"events": 15, "pass": 7, "flag": 3, "fail": 5}
    assert posthog["summary"] == {"events": 15, "pass": 0, "flag": 1, "fail": 14}


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

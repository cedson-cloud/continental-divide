"""Plan-scope vetting for a third-party tracking plan.

Audits a foreign plan with the same per-name rules the intake pipeline uses —
:func:`event_name_error`, :func:`property_name_error`, and :func:`pii_hit` from
``rules.py`` — plus checks that only make sense across a whole plan: exact and near
duplicate names, and category shape. ``evaluate()`` is deliberately not used: its
category and duplicate checks test membership in our sample tracking plan, which is
wrong for a plan being audited against itself.

Parsing is plain json + dict access, not Pydantic: foreign plans carry property types
outside our ``PropertyType`` enum (e.g. "datetime"), recorded as low-severity notes
rather than failures. A ``structure`` check separates malformed input (missing or
unusable event and property names) from convention violations, and structure-failed
names are excluded from duplicate detection — a name that isn't there can neither
violate a convention nor collide with another. Category notes are informational and
do not change verdicts.
Reads only the given JSON file; writes nothing to disk and never touches the database.

Usage: python -m app.vet <plan.json>
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .governance import DEFAULT_PROFILE, GovernanceError, GovernanceProfile, load_profile
from .models import PropertyType
from .rules import event_name_error, pii_hit, property_name_error

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_PROFILE_PATH = _REPO_ROOT / "governance" / "active.yaml"

_KNOWN_PROPERTY_TYPES = frozenset(t.value for t in PropertyType)

_NEAR_DUPLICATE_RATIO = 0.85

_NON_ALNUM = re.compile(r"[^a-z0-9]")

_RULES_SOURCE = {
    "module": "app.rules",
    "functions": ["event_name_error", "property_name_error", "pii_hit"],
    "plan_scope_checks": ["exact_duplicates", "near_duplicates", "category_notes"],
}


# --- per-event checks ------------------------------------------------------------

def _vet_event(event: dict, index: int, profile: GovernanceProfile) -> dict:
    """Per-event checks. ``structure`` separates malformed input from convention
    violations: an unusable event or property name fails ``structure`` and skips
    the convention checks, which cannot apply to a name that isn't there."""
    problems = []
    notes = []

    raw_name = event.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        name = raw_name
    else:
        name = None
        if raw_name is None:
            problems.append(f"event at index {index} has no name")
        elif isinstance(raw_name, str):
            problems.append(f"event at index {index} has a whitespace-only name")
        else:
            problems.append(
                f"event at index {index} has a non-string name "
                f"({type(raw_name).__name__})"
            )

    category = event.get("category")
    if category is not None and not isinstance(category, str):
        notes.append(
            {
                "severity": "low",
                "note": (
                    f"non-string category ({type(category).__name__}) "
                    "treated as uncategorized"
                ),
            }
        )
        category = None
    if profile.categories and category and category not in profile.categories:
        notes.append(
            {
                "severity": "low",
                "note": f"category '{category}' is not in the governance profile's categories",
            }
        )

    properties = [p for p in (event.get("properties") or []) if isinstance(p, dict)]

    bad_props = []
    pii_hits = []
    for prop_index, prop in enumerate(properties):
        prop_name = prop.get("name")
        if not isinstance(prop_name, str) or not prop_name.strip():
            problems.append(
                f"property at index {prop_index} has a missing or empty name"
            )
            continue
        if property_name_error(prop_name, convention=profile.property_naming.convention):
            bad_props.append(prop_name)
        hit = pii_hit(prop_name, blocklist=profile.pii.blocklist)
        if hit:
            pii_hits.append(f"{prop_name} -> {hit}")
        prop_type = prop.get("type")
        if prop_type not in _KNOWN_PROPERTY_TYPES:
            notes.append(
                {
                    "severity": "low",
                    "note": f"unrecognized property type '{prop_type}' on '{prop_name}'",
                }
            )

    checks = [
        {
            "rule": "structure",
            "passed": not problems,
            "detail": "; ".join(problems) if problems else "event shape is well-formed",
        }
    ]
    if name is not None:
        naming = profile.event_naming
        name_err = event_name_error(
            name,
            convention=naming.convention,
            connectors=naming.connectors,
            particles=naming.particles,
            irregular_past=naming.irregular_past,
        )
        checks.append(
            {
                "rule": "event_naming",
                "passed": name_err is None,
                "detail": name_err or f"valid name under {naming.convention}",
            }
        )

    prop_convention = profile.property_naming.convention
    checks.append(
        {
            "rule": "property_naming",
            "passed": not bad_props,
            "detail": (
                f"all property names are {prop_convention}"
                if not bad_props
                else f"not {prop_convention}: {', '.join(bad_props)}"
            ),
        }
    )
    checks.append(
        {
            "rule": "pii",
            "passed": not pii_hits,
            "detail": (
                "no PII tokens in property names"
                if not pii_hits
                else f"flagged: {'; '.join(pii_hits)}"
            ),
        }
    )

    return {
        "index": index,
        "name": name,
        "category": category,
        "checks": checks,
        "notes": notes,
    }


# --- plan-scope checks -----------------------------------------------------------

def _normalize(name: str) -> str:
    return _NON_ALNUM.sub("", name.lower())


def _near(a: str, b: str) -> bool:
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= _NEAR_DUPLICATE_RATIO


def _near_duplicate_clusters(names: list[str]) -> list[list[str]]:
    """Cluster distinct names whose lowercase-alphanumeric forms match exactly or sit
    at or above the difflib ratio threshold. Complete linkage: a name joins a cluster
    only if it clears the bar against every current member, so a run of pairwise-close
    neighbours cannot chain into one sprawling cluster whose endpoints barely relate."""
    unique = list(dict.fromkeys(names))
    normalized = {name: _normalize(name) for name in unique}
    clusters: list[list[str]] = []
    for name in unique:
        for cluster in clusters:
            if all(_near(normalized[name], normalized[member]) for member in cluster):
                cluster.append(name)
                break
        else:
            clusters.append([name])
    return [cluster for cluster in clusters if len(cluster) > 1]


def _category_notes(reports: list[dict]) -> dict:
    by_category = Counter(r["category"] for r in reports if r["category"])
    return {
        "declared_categories": sorted(by_category),
        "single_event_categories": sorted(c for c, n in by_category.items() if n == 1),
        "uncategorized_events": [r["name"] for r in reports if not r["category"]],
    }


# --- vetting ---------------------------------------------------------------------

def vet_plan(plan: dict, profile: GovernanceProfile = DEFAULT_PROFILE) -> dict:
    """Run every event through the reused per-name rules, then the plan-scope checks.

    Verdict per event: "fail" if structure, event naming, or property naming failed,
    else "flag" if PII was hit or the name is touched by a duplicate check, else
    "pass". PII flags but never rejects, matching ``evaluate()``. With no profile,
    the built-in default reproduces the intake pipeline's conventions.
    """
    reports = [
        _vet_event(event, index, profile)
        for index, event in enumerate(plan.get("events") or [])
        if isinstance(event, dict)
    ]
    # Structure-failed events carry no usable name and sit out duplicate detection.
    names = [r["name"] for r in reports if r["name"] is not None]

    exact_duplicates = sorted(n for n, count in Counter(names).items() if count > 1)
    near_duplicates = _near_duplicate_clusters(names)

    flagged_names = set(exact_duplicates) | {
        n for cluster in near_duplicates for n in cluster
    }
    for report in reports:
        hard_failed = any(
            not c["passed"] for c in report["checks"] if c["rule"] != "pii"
        )
        pii_flagged = any(
            not c["passed"] for c in report["checks"] if c["rule"] == "pii"
        )
        if hard_failed:
            report["verdict"] = "fail"
        elif pii_flagged or report["name"] in flagged_names:
            report["verdict"] = "flag"
        else:
            report["verdict"] = "pass"

    verdicts = Counter(r["verdict"] for r in reports)
    return {
        "source": plan.get("source"),
        "profile": profile.name,
        "rules_source": _RULES_SOURCE,
        "summary": {
            "events": len(reports),
            "pass": verdicts["pass"],
            "flag": verdicts["flag"],
            "fail": verdicts["fail"],
        },
        "events": reports,
        "plan_checks": {
            "exact_duplicates": exact_duplicates,
            "near_duplicates": near_duplicates,
            "category_notes": _category_notes(reports),
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.vet")
    parser.add_argument("plan", help="path to a plan JSON file")
    parser.add_argument("--profile", help="path to a governance profile YAML")
    args = parser.parse_args(argv)

    try:
        if args.profile:
            profile, origin = load_profile(args.profile), args.profile
        elif _ACTIVE_PROFILE_PATH.exists():
            profile, origin = load_profile(_ACTIVE_PROFILE_PATH), str(_ACTIVE_PROFILE_PATH)
        else:
            profile, origin = DEFAULT_PROFILE, "built-in default"
    except GovernanceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # A run is never ambiguous about what it enforced.
    print(f"governance profile: {profile.name} ({origin})", file=sys.stderr)
    plan = json.loads(Path(args.plan).read_text())
    print(json.dumps(vet_plan(plan, profile), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

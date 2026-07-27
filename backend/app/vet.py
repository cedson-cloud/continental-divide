"""Plan-scope vetting for a third-party tracking plan.

Audits a foreign plan with the same per-name rules the intake pipeline uses —
:func:`event_name_error`, :func:`property_name_error`, and :func:`pii_hit` from
``rules.py`` — plus checks that only make sense across a whole plan: exact and near
duplicate names, and category shape. ``evaluate()`` is deliberately not used: its
category and duplicate checks test membership in our sample tracking plan, which is
wrong for a plan being audited against itself.

Parsing is plain json + dict access, not Pydantic: foreign plans carry property types
outside our ``PropertyType`` enum (e.g. "datetime"), recorded as low-severity notes
rather than failures. Category notes are informational and do not change verdicts.
Reads only the given JSON file; writes nothing to disk and never touches the database.

Usage: python -m app.vet <plan.json>
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .models import PropertyType
from .rules import event_name_error, pii_hit, property_name_error

_KNOWN_PROPERTY_TYPES = frozenset(t.value for t in PropertyType)

_NEAR_DUPLICATE_RATIO = 0.85

_NON_ALNUM = re.compile(r"[^a-z0-9]")

_RULES_SOURCE = {
    "module": "app.rules",
    "functions": ["event_name_error", "property_name_error", "pii_hit"],
    "plan_scope_checks": ["exact_duplicates", "near_duplicates", "category_notes"],
}


# --- per-event checks ------------------------------------------------------------

def _vet_event(event: dict) -> dict:
    name = str(event.get("name") or "")
    properties = [p for p in (event.get("properties") or []) if isinstance(p, dict)]

    checks = []
    notes = []

    name_err = event_name_error(name)
    checks.append(
        {
            "rule": "event_naming",
            "passed": name_err is None,
            "detail": name_err or "valid Object Action, Title Case name",
        }
    )

    bad_props = []
    pii_hits = []
    for prop in properties:
        prop_name = str(prop.get("name") or "")
        if property_name_error(prop_name):
            bad_props.append(prop_name)
        hit = pii_hit(prop_name)
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

    checks.append(
        {
            "rule": "property_naming",
            "passed": not bad_props,
            "detail": (
                "all property names are snake_case"
                if not bad_props
                else f"not snake_case: {', '.join(bad_props)}"
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
        "name": name,
        "category": event.get("category"),
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
    at or above the difflib ratio threshold against any existing cluster member."""
    unique = list(dict.fromkeys(names))
    normalized = {name: _normalize(name) for name in unique}
    clusters: list[list[str]] = []
    for name in unique:
        for cluster in clusters:
            if any(_near(normalized[name], normalized[member]) for member in cluster):
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

def vet_plan(plan: dict) -> dict:
    """Run every event through the reused per-name rules, then the plan-scope checks.

    Verdict per event: "fail" if event naming or property naming failed, else "flag"
    if PII was hit or the name is touched by a duplicate check, else "pass". PII flags
    but never rejects, matching ``evaluate()``.
    """
    events = [e for e in (plan.get("events") or []) if isinstance(e, dict)]
    reports = [_vet_event(event) for event in events]
    names = [r["name"] for r in reports]

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

    return {
        "source": plan.get("source"),
        "rules_source": _RULES_SOURCE,
        "events": reports,
        "plan_checks": {
            "exact_duplicates": exact_duplicates,
            "near_duplicates": near_duplicates,
            "category_notes": _category_notes(reports),
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m app.vet <plan.json>", file=sys.stderr)
        return 2
    plan = json.loads(Path(argv[0]).read_text())
    print(json.dumps(vet_plan(plan), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

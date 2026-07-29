"""Scoring: turn an engine result and a fixture's expectations into assertions.

Each expectation field scores independently and three-state: ``pass``, ``fail``,
or ``unscored`` when the fixture left it ``None``. Unscored fields are still
recorded with their actual value, so a result file shows what the engine did
even where no claim was made. ``failed_rules`` compares as a set of rule names —
never the ``detail`` strings, which are prose and will churn.

The live tier adds scorers for its own fields (name_shape, category,
property_names, findings) alongside these; nothing here changes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models import Decision, Evaluation

from .schema import DefinitionExpect, NameFixture


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    expected: Any
    actual: Any
    status: Literal["pass", "fail", "unscored"]


def _scored(field: str, expected: Any, actual: Any) -> Assertion:
    if expected is None:
        return Assertion(field=field, expected=None, actual=actual, status="unscored")
    status = "pass" if expected == actual else "fail"
    return Assertion(field=field, expected=expected, actual=actual, status=status)


def score_evaluation(evaluation: Evaluation, expect: DefinitionExpect) -> list[Assertion]:
    failed_rules = sorted({c.rule for c in evaluation.checks if not c.passed})
    return [
        _scored(
            "decision",
            None if expect.decision is None else Decision(expect.decision).value,
            evaluation.decision.value,
        ),
        _scored(
            "failed_rules",
            None if expect.failed_rules is None else sorted(set(expect.failed_rules)),
            failed_rules,
        ),
        _scored("pii_flagged", expect.pii_flagged, evaluation.pii_flagged),
        _scored("flags_present", expect.flags_present, bool(evaluation.flags)),
        _scored(
            "duplicate_check_present",
            expect.duplicate_check_present,
            any(c.rule == "duplicate" for c in evaluation.checks),
        ),
    ]


def score_name(error: str | None, fixture: NameFixture) -> list[Assertion]:
    assertions = [_scored("valid", fixture.expect_valid, error is None)]
    if fixture.expect_fragment is None:
        assertions.append(
            Assertion(field="fragment", expected=None, actual=error, status="unscored")
        )
    else:
        hit = error is not None and fixture.expect_fragment in error
        assertions.append(
            Assertion(
                field="fragment",
                expected=fixture.expect_fragment,
                actual=error,
                status="pass" if hit else "fail",
            )
        )
    return assertions

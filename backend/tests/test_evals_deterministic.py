"""The free tier of the eval harness: it guards engine behaviour with zero API
spend and runs in CI. The live tier guards model behaviour, costs money, and
lives outside pytest.

Each fixture in ``evals/fixtures/deterministic.yaml`` pins one decision and
carries a note naming it, so a claim about engine behaviour ("Newsletter Signed
Up is broken") resolves to a single named test rather than a green suite.
"""

from pathlib import Path

import pytest

from app.models import EventDefinition
from app.rules import evaluate, event_name_error
from evals.schema import load_fixtures, resolve_profile
from evals.score import score_evaluation, score_name

_FIXTURES = load_fixtures(
    Path(__file__).parents[1] / "evals" / "fixtures" / "deterministic.yaml"
)


def _score_name_fixture(fixture):
    naming = resolve_profile(fixture.profile).event_naming
    error = event_name_error(
        fixture.name,
        convention=naming.convention,
        connectors=naming.connectors,
        particles=naming.particles,
        irregular_past=naming.irregular_past,
    )
    return score_name(error, fixture)


def _score_definition_fixture(fixture):
    profile = resolve_profile(fixture.profile)
    definition = EventDefinition.model_validate(fixture.definition)
    evaluation = evaluate(
        definition,
        profile,
        request_kind=fixture.request_kind,
        existing_event=fixture.existing_event,
    )
    return score_evaluation(evaluation, fixture.expect)


def _assert_no_failures(assertions):
    failures = [a for a in assertions if a.status == "fail"]
    assert not failures, "\n" + "\n".join(
        f"{a.field}: expected={a.expected!r} actual={a.actual!r}" for a in failures
    )


_NAME_PARAMS = [pytest.param(f, id=f.id) for f in _FIXTURES.names]

_DEFINITION_PARAMS = [
    pytest.param(
        f,
        id=f.id,
        marks=[pytest.mark.xfail(reason=f.xfail_reason, strict=True)]
        if f.xfail_reason
        else [],
    )
    for f in _FIXTURES.definitions
]


@pytest.mark.parametrize("fixture", _NAME_PARAMS)
def test_name_fixture(fixture):
    _assert_no_failures(_score_name_fixture(fixture))


@pytest.mark.parametrize("fixture", _DEFINITION_PARAMS)
def test_definition_fixture(fixture):
    _assert_no_failures(_score_definition_fixture(fixture))


def test_every_fixture_scores_something():
    for fixture in _FIXTURES.names:
        assertions = _score_name_fixture(fixture)
        assert any(a.status != "unscored" for a in assertions), fixture.id
    for fixture in _FIXTURES.definitions:
        assertions = _score_definition_fixture(fixture)
        assert any(a.status != "unscored" for a in assertions), fixture.id

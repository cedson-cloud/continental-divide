# Evals

An eval harness in two tiers. Each fixture pins one engine decision and carries
a note naming it, so a claim about behaviour ("Newsletter Signed Up is broken")
resolves to a single named fixture instead of a green suite. A green suite says
"nothing broke"; a fixture says "this specific claim is false."

## The two tiers

**Deterministic (this tier, free).** Fixtures in `fixtures/deterministic.yaml`
run the rules engine directly — no model call, no API key, zero spend. The
loader is `backend/tests/test_evals_deterministic.py`, so the tier runs with
`pytest` in CI. It guards engine behaviour: naming, category, property naming,
PII, duplicates, routing.

**Live (later, ~$0.21/run).** Sends plain-language requests through the model
and scores the drafted definitions. It guards model behaviour, costs money, and
lives outside pytest: a script that writes JSONL results to `results/` and
prints a delta against the committed baseline. Nothing in this tier exists yet;
the schema and scorer here are shaped so it adds fields without changing them.

They are separate because they answer different questions and fail for
different reasons. An engine regression is a code bug and should block CI; a
drift in model output is a prompt or model-version question and should never
cost API spend on every test run to detect.

## What is scored, and what deliberately is not

Expectations are three-state: a field left unset is unscored — recorded in the
results, never failed. Decision, failed rules (as a set of rule names, never
the prose details), PII flags, and duplicate checks are scored exactly.

The description prose is recorded and diffed, never scored. It is the only
field with no closed vocabulary, so string equality makes every prompt tweak
read as a regression, and a judge model adds a second nondeterministic system
to debug.

Fixtures pin a governance template explicitly and never read `active.yaml` —
otherwise flipping the active profile silently rewrites every expectation.

# Continental Divide — Tasks

Working roadmap for the build. Keep this clean: it travels with the repo, and the repo is going public.

## Done

- Core build (steps 1–6): intake → validate → approve → publish, with the append-only audit log. Committed and verified end-to-end against the real Anthropic API.
- PII handling changed from auto-reject to flagged-and-gated (approval requires acknowledgment, recorded in the audit log).
- Status enum on the lifecycle: `pending_approval` → `approved` → `published`, or → `rejected`.
- Submitter name and team added to the request model.
- Notion publisher: `app/notion_publisher.py` pushes pending requests one-way to the Notion approval board, with the submitter/team/call-type/side intake fields and a guard that skips empty selects. Mocked unit tests, no network in the suite.
- Pytest suite and CI across rules, governance, vetting, pipeline, API, and Notion mapping. GitHub Actions runs the backend tests and the frontend build on every push. MIT LICENSE; database renamed to `continental_divide.db`.
- **Plan-scope vetting** (`app/vet.py`): audits an existing third-party tracking plan by reusing `event_name_error`, `property_name_error`, and `pii_hit` from `rules.py` rather than reimplementing them. Adds checks that only make sense across a whole plan — structure, exact and near duplicates (complete linkage), category notes — and emits engine-computed summary counts. `evaluate()` is deliberately not used: its category and duplicate checks test membership in our sample plan, which is wrong for auditing someone else's.
- **Governance as configuration** (`governance/`): YAML profiles with `extends` inheritance, cycle detection, and load-time validation. Two event-naming conventions (`title_case_object_action`, `snake_case_object_action`), templates for Segment and PostHog, and `active.yaml` selecting the enforced profile. `rules.py` gained keyword-only parameters defaulting to its existing constants, so the intake path was unchanged.
- **Tracking-plan vetting agent** (`.claude/agents/tracking-plan-vetter.md`): normalizes a foreign plan, runs the vetting CLI under the active profile, and reports engine verdicts separately from model judgment (rename suggestions, and semantic duplicates the lexical clustering cannot catch).

## Next

- [ ] **Wire the intake path to the governance profile.** `vet.py` reads the active profile; `evaluate()` still uses the built-in defaults. Set `active.yaml` to a non-default convention and the app and the vetting agent will disagree — the failure the shared-rules design exists to prevent. Highest priority.
- [ ] **Publish failure handling.** On the approve path, a publisher error should record a `publish_failed` audit entry instead of stranding the request at `approved`.
- [ ] **Concurrent-decision guard.** Add a compare-and-swap on status so a request can't be decided twice concurrently.
- [ ] **Harden `POST /requests/raw`.** Apply the rate limit and a size cap, as the model-backed intake route already does.
- [ ] **Guided rename-and-resubmit.** A naming failure should offer the compliant name and a one-click resubmit, with consent recorded in the audit trail, instead of a terminal rejection before a human ever sees it.
- [ ] **"Not sure" on client vs. server.** Route the question to the approver rather than forcing a guess at intake.
- [ ] **A `why` on every event request.** Purpose, business value, and where it fires. Segment's own tracking-plan guidance asks for this, and it is what makes the catalog useful to someone who did not submit the event.
- [ ] **Support identify, page, and screen calls.** EventDefinition is track-shaped and rules.py enforces a track event-naming convention; traits and page calls need their own shapes and their own rules. The intake UI was narrowed to track rather than advertise support that does not exist.
- [ ] **Fold `vet.py` onto `governance.load_active_profile()`.** The CLI keeps a private copy of the "resolve active.yaml, else default" logic. Two copies of the same resolution is the drift this design exists to prevent.
- [ ] **Guard `load_active_profile()` at every call site.** `/governance/profile` handles `GovernanceError`; `_validate_destinations` does not, so a malformed `active.yaml` breaks live intake with an unhandled exception. The profile is read per request, so a bad edit takes effect immediately.

## Later

- [ ] **Admin view of the active profile.** Read-only display of the enforced rules and their history. Rules live in git, so `git log` supplies the history at no cost.
- [ ] **Setup flow that authors a profile.** Pick a template, then override, from a curated list of known conventions — never free-form regex.
- [ ] **Re-vet on rule change.** When a profile changes, report which existing events no longer comply.
- [ ] **Platform specs as data** (`platforms/*.yaml`): call shape, identity model, and source URL for Segment, PostHog, and Hightouch. The three SDKs differ structurally, not cosmetically, so one template with a swapped function name will not work. The app, the agent, and any skill must read one file or they will drift.
- [ ] **Code snippets per SDK**, generated from those specs and syntax-checked in CI. A wrong snippet is worse than no snippet, because it gets shipped.
- [ ] **Categories in one place.** `evaluate()` reads them from `sample_tracking_plan.json`; `vet.py` reads them from the profile. The sample plan is a fixture and should not also be configuration.
- [ ] **`pii.mode: block`.** Reserved in the schema, not implemented.
- [ ] **Notion board categories drift from the sample plan.** Notion auto-creates missing options, so nothing breaks, but the demo looks inconsistent.
- [ ] **`properties` as a non-list is silently skipped** in `vet.py`, and the event then reports that all property names are snake_case — a passing check on properties nobody examined.

## Before this repo goes public

- [x] Review the full git history of this repo, not just the current tree, for anything that shouldn't ship: credentials, tokens, key files, client references.
- [x] Confirm `backend/.env` was never committed (`git log --all -- backend/.env` should return nothing).
- [ ] Update the README: it describes neither governance profiles nor the vetting agent.
- [ ] Confirm the README and the code match before flipping visibility.
- [ ] Confirm the governance templates stay generic. A client's conventions, PII list, or destination list must never be committed here.

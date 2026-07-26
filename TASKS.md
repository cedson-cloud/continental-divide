# Continental Divide — Tasks

Working roadmap for the build. Keep this clean: it travels with the repo, and the repo is going public.

## Done

- Core build (steps 1–6): intake → validate → approve → publish, with the append-only audit log. Committed and verified end-to-end against the real Anthropic API.
- PII handling changed from auto-reject to flagged-and-gated (approval requires acknowledgment, recorded in the audit log).
- Status enum on the lifecycle: `pending_approval` → `approved` → `published`, or → `rejected`.
- Submitter name and team added to the request model.
- Notion publisher: `app/notion_publisher.py` pushes pending requests one-way to the Notion approval board, with the submitter/team/call-type/side intake fields and a guard that skips empty selects. Mocked unit tests, no network in the suite.

## Next

- [ ] **Publish failure handling.** On the approve path, a publisher error should record a `publish_failed` audit entry instead of stranding the request at `approved`.
- [ ] **Concurrent-decision guard.** Add a compare-and-swap on status so a request can't be decided twice concurrently.
- [ ] **Harden `POST /requests/raw`.** Apply the rate limit and a size cap, as the model-backed intake route already does.
- [ ] **Tracking-plan vetting agent.** Rebuild it as an in-repo `.claude/agents/` definition.

## Before this repo goes public

- [x] Review the full git history of this repo, not just the current tree, for anything that shouldn't ship: credentials, tokens, key files, client references.
- [x] Confirm `backend/.env` was never committed (`git log --all -- backend/.env` should return nothing).
- [ ] Confirm the README and the code match before flipping visibility.
# Continental Divide — Tasks

Working roadmap for the build. Keep this clean: it travels with the repo, and the repo is going public.

## Done

- Core build (steps 1–6): intake → validate → approve → publish, with the append-only audit log. Committed and verified end-to-end against the real Anthropic API.
- PII handling changed from auto-reject to flagged-and-gated (approval requires acknowledgment, recorded in the audit log).
- Status enum on the lifecycle: `pending_approval` → `approved` → `published`, or → `rejected`.
- Submitter name and team added to the request model.

## Next

- [ ] **Notion publisher.** Add the `notion-client` dependency and `app/notion_publisher.py`. One-way push of an approved request to the Notion approval board, reading `NOTION_TOKEN` and `NOTION_APPROVAL_DB_ID` from settings. Fold the intake-page UI inputs (submitter name, required team, plus call type and side) in here. Add a defensive guard so a missing team is skipped rather than sent as a null select. One DB reset for the new columns.

## Before this repo goes public

- [ ] Review the full git history of this repo, not just the current tree, for anything that shouldn't ship: credentials, tokens, key files, client references.
- [ ] Confirm `backend/.env` was never committed (`git log --all -- backend/.env` should return nothing).
- [ ] Confirm the README and the code match before flipping visibility.
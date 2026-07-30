# CLAUDE.md — Continental Divide

## What this is

Continental Divide is an event-tracking request-and-governance tool. Someone asks for a new analytics event in plain language, a model drafts a structured definition, deterministic rules govern it (naming, PII, category, duplicate), the requester confirms the draft before it enters the approval queue, an approver approves or rejects, and on approval a publisher writes it out. Every step lands in an append-only audit log. It's a Bristlecone Echo demo asset that proves the intake → validate → confirm → approve → publish pattern with a full audit trail.

This is a clean-room build. It contains no client code, data, or rules. Never reintroduce client-specific material into this repo.

**Private repo today. A public version is planned, and git history is permanent, so keep every commit clean from the start: no client names, no client data, no real credentials in tracked files.**

## Stack

- Backend: Python, FastAPI, Pydantic v2
- Frontend: Next.js, React, TypeScript
- Database: SQLite behind a Storage interface (Postgres-swappable, so keep queries portable). The audit log is append-only, enforced by DB triggers.
- Model calls: Anthropic Python SDK, server-side only
- Publishing: MockPublisher behind a Publisher interface, with a documented Atlassian (Confluence + Jira) stub, plus a one-way push to a Notion approval board

Default to this stack. If a task needs something outside it, say so and name the alternative before adding it.

## Project layout

```
continental-divide/
  backend/
    app/              FastAPI app, Pydantic models, routes, rules, services
    data/             SQLite database, and throwaway scripts (gitignored)
    examples/         sample requests
    tests/            pytest suite
    requirements.txt
    run_examples.py
    .env              secrets, gitignored (never committed)
  frontend/           Next.js app
  .env.example        template for backend/.env
  .gitignore
  README.md
  TASKS.md
  CLAUDE.md
```

## Commands

> Confirm the exact uvicorn module path and the frontend script against the repo. The ports and the localhost rule below are fixed.

- Backend dev server runs on port `8000`
- Frontend dev server runs on port `3000`
- Use `localhost`, not `127.0.0.1`. CORS is configured for `localhost`.
- Backend deps: `pip install -r requirements.txt` (from `backend/`)
- Tests: `pytest` (from `backend/`)
- Call `.venv/bin/uvicorn` directly rather than activating the venv.
- Give me terminal commands one line at a time. VS Code's Python extension injects venv activation into multi-line pastes and eats commands.
- Throwaway and probe scripts go in `backend/data/`, which is already gitignored, so `git status` stays clean.

## How the flow works

- A request comes in: plain language through the model, or `POST /requests/raw`, which bypasses the model for deterministic rule demos.
- The model drafts a structured event definition.
- Deterministic rules govern it: naming, PII (flagged and gated on acknowledgment, not auto-rejected), category, duplicate.
- A non-rejected request from the model path stops at `draft`. The requester reviews it and submits; only then does it enter the approval queue and push one-way to the Notion approval board. Submission requires a written note when the engine found a near duplicate, or the semantic review left a *high-confidence* duplicate candidate. Lower-confidence findings are shown and cost the requester nothing.
- The model-free `POST /requests/raw` path skips confirmation and routes straight to `pending_approval`.
- A human approves or rejects. Status moves `draft` → `pending_approval` → `approved` → `published`, or → `rejected`.
- On approval, MockPublisher publishes.
- Every step writes to the append-only audit log.

Naming convention: the sample plan follows Segment's public Ecommerce V2 spec. Event names use Object Action in Title Case, per Segment's Track spec.

## Architecture rules

These are settled. Raise them with me before changing any of them.

- **`rules.py` is deterministic and non-LLM by design.** Naming, PII, category and mechanical duplicate checks are regex and set membership. Never put a model call in it.
- **Duplicate detection has three tiers, and no tier rejects.** The engine reports an exact name match as fact and a near duplicate — the same name in different case, separators, or a plural — as deterministic judgment. The agent reports semantic ones as inference. Semantic review lives in `catalog.py`, is advisory only, and can never reject a request. Nothing reaches `published` without a human acknowledging any tier that fired. See `docs/adr/0001` and `CONTEXT.md` for the vocabulary.
- **An advisory model call must never be able to block intake.** If a review raises, record the failure and route normally.
- **Status and Decision are separate.** `Decision` is the routing outcome. Statuses include values that are not `Decision` members — `draft`, `approved`, `published`. Don't add values to the `Decision` enum.
- **The model captures, it does not enforce.** If a requester specifies an event name, record it verbatim and let the engine reject it. Never silently correct a request.
- **The drafting prompt derives from the active governance profile**, not from hardcoded strings. The PII blocklist is deliberately withheld from it, so the model cannot quietly avoid drafting a blocked property.
- **One authority per field.** Two instructions about the same thing in one prompt is not redundancy, it is a silent bug.
- **`backend/tests/test_rules.py` is a frozen backward-compatibility canary.** Do not edit it.

## Working agreements

- I read code and direct builds. I'm not an engineer. Lean on me for product and data judgment, not syntax.
- **I handle git. Do not commit or push, ever.**
- **Never weaken or bypass the append-only audit log.** It's enforced by DB triggers, and that's deliberate.
- Don't rewrite code I didn't ask you to touch.
- Match the style already in the file you're editing.
- Don't add comments that just restate what the code does.
- When there are multiple reasonable approaches, name them briefly, recommend one, move on.
- When adding a dependency or service, justify it in one line and name the alternative.
- When I report an error, ask for what you need (logs, the calling code, versions) instead of guessing.
- Prefer small, reviewable changes over large rewrites. Work one task at a time.
- Explain architecture choices in three sentences or fewer. Expand only if I ask.
- End substantial work by naming the artifacts I can check on disk — a function name, a file path, a test count that must increase. Report the collected test count before and after.
- Any README or docs copy you write should be plain and durable. Avoid "leverage," "delve," "robust," "seamless," and "game-changer."

## Security and cost (important)

- **Secrets live in `backend/.env`, which is gitignored. `.env.example` is the committed template.** Never hardcode a secret or paste one into source, tests, or examples.
- Env vars include `ANTHROPIC_API_KEY`, the model name, `NOTION_TOKEN`, and `NOTION_APPROVAL_DB_ID`. Don't echo, log, or write any of them to disk.
- The model is pinned in `backend/.env`. Don't change it without asking.
- The Anthropic SDK path is the one place dev work costs money. Use it deliberately and flag anything that would loop API calls.
- `run_examples.py` does not reach Notion — it calls `ingest()`, and the push fires only from `submit_request`. It does call `reset_storage()`, which deletes the SQLite file: running it destroys the local request history and audit log.
- There is no auth on the app, and `POST /requests/raw` has no rate limit or size cap. Both are fine on localhost and blocking before anything is hosted.

## Agent skills

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root, both created lazily rather than upfront. See `docs/agents/domain.md`.

Division of labor, one authority per question:

- **`CLAUDE.md`** — the rules an agent works under. Points to `CONTEXT.md` rather than restating it.
- **`CONTEXT.md`** — vocabulary only. What a domain term means, and which synonyms to avoid.
- **`docs/adr/`** — why a decision was made, and what it ruled out.
- **`TASKS.md`** — what work remains.
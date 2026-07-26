# CLAUDE.md — Continental Divide

## What this is

Continental Divide is an event-tracking request-and-governance tool. Someone asks for a new analytics event in plain language, a model drafts a structured definition, deterministic rules govern it (naming, PII, category, duplicate), a human approves or rejects, and on approval a publisher writes it out. Every step lands in an append-only audit log. It's a Bristlecone Echo demo asset that proves the intake → validate → approve → publish pattern with a full audit trail.

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
    data/             SQLite database
    examples/         sample requests
    tests/            pytest suite
    requirements.txt
    run_examples.py
    .env              secrets, gitignored (never committed)
  frontend/           Next.js app
  .env.example        template for backend/.env
  .gitignore
  README.md
  CLAUDE.md
```

## Commands

> Confirm the exact uvicorn module path and the frontend script against the repo. The ports and the localhost rule below are fixed.

- Backend dev server runs on port `8000`
- Frontend dev server runs on port `3000`
- Use `localhost`, not `127.0.0.1`. CORS is configured for `localhost`.
- Backend deps: `pip install -r requirements.txt` (from `backend/`)
- Tests: `pytest` (from `backend/`)

## How the flow works

- A request comes in: plain language through the model, or `POST /requests/raw`, which bypasses the model for deterministic rule demos.
- The model drafts a structured event definition.
- Deterministic rules govern it: naming, PII (flagged and gated on acknowledgment, not auto-rejected), category, duplicate.
- A human approves or rejects. Status moves `pending_approval` → `approved` → `published`, or → `rejected`.
- On approval, MockPublisher publishes and the request is pushed one-way to the Notion approval board.
- Every step writes to the append-only audit log.

Naming convention: the sample plan follows Segment's public Ecommerce V2 spec. Event names use Object Action in Title Case, per Segment's Track spec.

## Working agreements

- I read code and direct builds. I'm not an engineer, so explain architecture choices and anything non-obvious. Lean on me for product and data judgment, not syntax.
- **I handle git. Do not commit or push, ever.**
- **Never weaken or bypass the append-only audit log.** It's enforced by DB triggers, and that's deliberate.
- Don't rewrite code I didn't ask you to touch.
- Match the style already in the file you're editing.
- Don't add comments that just restate what the code does.
- When there are multiple reasonable approaches, name them briefly, recommend one, move on.
- When adding a dependency or service, justify it in one line and name the alternative.
- When I report an error, ask for what you need (logs, the calling code, versions) instead of guessing.
- Prefer small, reviewable changes over large rewrites. Work one task at a time.
- Any README or docs copy you write should be plain and durable. Avoid "leverage," "delve," "robust," "seamless," and "game-changer."

## Security and cost (important)

- **Secrets live in `backend/.env`, which is gitignored. `.env.example` is the committed template.** Never hardcode a secret or paste one into source, tests, or examples.
- Env vars include `ANTHROPIC_API_KEY`, the model name, `NOTION_TOKEN`, and `NOTION_APPROVAL_DB_ID`. Don't echo, log, or write any of them to disk.
- The model is pinned in `backend/.env`. Don't change it without asking.
- The Anthropic SDK path is the one place dev work costs money. Use it deliberately and flag anything that would loop API calls.
- `TASKS.md` holds what's next.
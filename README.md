# Continental Divide

A small demo that walks one analytics-event request through **intake → schema + rules
validation → human approval → publish**, with a persistent, timestamped audit log shown
in the UI.

This is a clean-room rebuild from a public pattern. It contains no proprietary code, data,
names, or rules — only generic dummy data and a sample tracking plan safe to publish.

## How it works

1. **Intake** — submit a raw, natural-language request for a new event.
2. **Structure** — a model returns a structured event definition as JSON, parsed against a
   Pydantic v2 model. Parse failure → request is `rejected` with the validation errors recorded.
3. **Rules** — deterministic checks: snake_case names, a PII property blocklist, category must
   exist in the sample tracking plan, and duplicate-name detection (routes to approval with a flag).
4. **Validate-by-example** — a sample payload is generated from the definition and re-validated
   against the Pydantic model; the UI shows pass/fail. No code execution, no sandbox.
5. **Approval** — a human approves or rejects from a queue.
6. **Publish** — on approve, a `Publisher` (mock by default) renders a Confluence-style doc and
   a Jira-style ticket in-app. Every transition writes to the audit log.

## Stack

- **Backend:** Python + FastAPI, Pydantic v2, SQLite (single file), Anthropic Python SDK
  (server-side only).
- **Frontend:** Next.js (App Router) + React + TypeScript, one flow.
- **Storage:** behind a thin interface; SQLite by default. Tables: `event_request`, `audit_log`.
- **Publishing:** behind a `Publisher` interface; `MockPublisher` default. A real Atlassian
  adapter is left as a documented stub (no OAuth).

## Layout

```
backend/    FastAPI app, Pydantic models, rules, storage, publisher, sample data
frontend/   Next.js App Router UI
```

## Setup

> Detailed run/deploy notes are filled in at step 6. The outline:

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env      # then edit .env
uvicorn app.main:app --reload   # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                     # http://localhost:3000
```

## Configuration

Copy `.env.example` to `.env` and set values. Key variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | API key, **server-side only** | _(required)_ |
| `ANTHROPIC_MODEL` | Reasoning model id | `claude-sonnet-4-6` |
| `DATABASE_PATH` | SQLite file path | `backend/data/tracking_guardian.db` |
| `MAX_INTAKE_CHARS` | Intake length cap | `2000` |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SECONDS` | Rate limit on `POST /requests` | `10` / `60` |

## Security notes

- The Anthropic key is read server-side only and is never sent to the browser bundle.
- `.gitignore` excludes `.env` and the SQLite data directory. Never commit `.env`.
- `POST /requests` hits a paid API: intake length is capped and the endpoint is rate-limited.

## Build status

- [x] 1. Repo scaffold (FastAPI + Next) + env + .gitignore + .env.example + README skeleton
- [ ] 2. Pydantic models + sample tracking plan + deterministic rules
- [ ] 3. Storage interface (SQLite) + tables + audit-logging helper
- [ ] 4. FastAPI routes (intake/validate, decision/publish, queries) + MockPublisher
- [ ] 5. Single-flow Next.js UI
- [ ] 6. Run/deploy notes

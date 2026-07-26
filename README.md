# Continental Divide

A request-and-governance tool for analytics event tracking. Anyone can ask for a new
event to be tracked. Nothing gets published until it passes the rules and a human signs off.

I built the first version of this pattern for a client and wanted a clean, open version
I could share. Continental Divide takes a plain-language request for a new tracking event,
turns it into a typed and validated definition, routes it for approval, and on approval
publishes the documentation and opens a ticket. Every step is recorded.

The name is the idea. A continental divide is the line that decides which way the water
flows. This tool is the line a tracking request has to cross, and it decides what gets through.

## How it works

1. **Intake:** someone describes the event they want to track, in plain language.
2. **Draft and validate:** a model turns that into a structured event definition. It
   conforms to the schema or fails loudly, with the reasons shown. The model only drafts —
   deterministic rules then check naming, block PII, and catch duplicates against the
   tracking plan, and the model cannot talk its way past them.
3. **Approve:** a clean request routes to a human for one-click approval or rejection.
4. **Publish:** on approval, the tool publishes the event documentation and opens a
   tracking ticket. Out of the box this uses a mock publisher, so the whole flow runs
   with no external accounts.

A timestamped, append-only audit log records every step — what was requested, what the
model proposed, which rules passed or failed, and who decided.

## Stack

- Backend: Python + FastAPI, Pydantic v2 for typed, validated outputs
- Frontend: Next.js + React (TypeScript)
- Drafting: Anthropic API, server-side only
- Storage: SQLite for the audit log and request history, behind a storage interface
- Publishing: pluggable. A mock publisher ships by default, with a documented stub for a
  real Atlassian (Confluence and Jira) adapter

## Running it locally

### Prerequisites

- Python — 3.9 works, 3.11+ recommended.
- Node.js LTS.
- An Anthropic API key (see Real-key setup below). The app runs without one, but the
  intake step needs it.

### Start it

Two terminals — the backend on port 8000, the frontend on port 3000.

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # creates backend/.env, then add your key (next section)
uvicorn app.main:app --reload    # http://localhost:8000
```

```bash
# Terminal 2 — frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                      # http://localhost:3000
```

Then open **http://localhost:3000** — use `localhost`, not `127.0.0.1`. The backend
pins CORS to `http://localhost:3000`, so loading the UI from `127.0.0.1:3000` makes the
browser's API calls fail.

### Real-key setup

The intake step calls the Anthropic API server-side to draft a definition from the
plain-language request.

1. Get a key from the Anthropic Console (https://console.anthropic.com).
2. Put it in `backend/.env` as `ANTHROPIC_API_KEY=sk-ant-...`.
3. Never commit it. `backend/.env` is gitignored; only `.env.example` is tracked.

The key is read server-side only and never reaches the browser or any API response.
Without a key, `POST /requests` returns a 502 with a "could not draft a definition"
message and records a `model_error` step in the audit log — the request is still
persisted, and the rest of the app (queue, detail, approve/reject, the raw-definition
demo path below) still runs.

## Demo walkthrough

Four paths, each proving a different part of the contract. The first two go through the
model; the last two use a small demo affordance on the intake page ("load a raw
definition, skips the model step") so the rule cases fire deterministically without
depending on what the model writes.

- **Natural language, clean** — "track when a shopper empties their entire cart". The
  model drafts `Cart Cleared`, every rule passes, it routes to approval; approve it and
  it publishes a mock Confluence doc and Jira ticket. The happy path, end to end.
- **Natural language, PII** — "track when someone subscribes to our newsletter and
  capture their email address". The model faithfully proposes an `email` property, and the
  PII rule rejects it. The point: the model drafts what was asked for, the rules govern.
- **Raw naming violation** — a pre-built `add_to_cart` definition. The naming rule
  rejects it for not being Object Action, Title Case. A well-behaved model won't author a
  malformed name from plain English, so this path skips the model to exercise the rule.
- **Raw duplicate** — a pre-built `Order Completed` definition, which already exists in
  the tracking plan. It's flagged as a duplicate and routed to a human rather than
  auto-rejected.

Open any request's detail page and read the audit timeline. That timeline is the point of
the tool: it reconstructs exactly what happened and why, in order, and the audit rows
cannot be edited or deleted.

## Deploy notes

Not deployed yet — these are notes for later, not a deployment guide.

The shape is two services plus a database: the FastAPI backend, the Next.js frontend, and
a datastore for the audit log and request history.

- **SQLite is local-only.** The default storage writes to a single SQLite file. Any host
  with an ephemeral filesystem (most container platforms) won't persist the audit log
  across restarts — which defeats the point of the tool. A real deploy needs a durable
  database: implement a Postgres backend behind the existing `Storage` interface (the app
  talks to that interface, not to SQLite directly) and point the backend at it.
- **The intake endpoint is a cost and abuse surface.** `POST /requests` calls a paid API
  on every request. The built-in rate limit and intake-length cap are a floor, not a
  public-facing control. Before exposing it, add authentication and a usage cap.
- **Environment variables.** Backend: `ANTHROPIC_API_KEY` (required for intake),
  `ANTHROPIC_MODEL`, `DATABASE_PATH`, `MAX_INTAKE_CHARS`, `RATE_LIMIT_MAX`,
  `RATE_LIMIT_WINDOW_SECONDS`. Frontend: `NEXT_PUBLIC_API_BASE` (the backend's URL).

## Status

The full flow works end to end: plain-language intake, model drafting, deterministic
rules, human approval with PII acknowledgment, mock publishing, and a one-way push of
pending requests to a Notion approval board — all recorded in the append-only audit log.
A pytest suite covers the rules, the pipeline, the HTTP flow, and the Notion mapping,
and CI runs the suite plus a frontend type-check and build on every push. Not deployed
anywhere yet; see the deploy notes above.

## Clean room

This is a clean-room rebuild. It carries no client code, data, names, or rules from any
prior engagement. The sample tracking plan follows Segment's public Ecommerce V2 spec and
uses generic example data; the naming convention follows Segment's public Track spec.
Everything here is safe to publish. Secrets live in environment variables only and are
never committed.

## About

Continental Divide is a Bristlecone Echo asset. Bristlecone Echo helps organizations build
better data foundations: cleaner tracking, clearer governance, and customer and operational
insight they can act on. Roots before branches.

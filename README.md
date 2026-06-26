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

1. **Intake:** someone submits a new event they want to track, in plain language.
2. **Validate:** the request becomes a structured event definition. It conforms to the
   schema or fails loudly, with the reasons shown. Deterministic rules then check naming,
   block PII, and catch duplicates against the tracking plan.
3. **Approve:** a clean request routes to a human for one-click approval or rejection.
4. **Publish:** on approval, the tool publishes the event documentation and opens a
   tracking ticket. Out of the box this uses a mock publisher, so the whole flow runs
   with no external accounts.

A timestamped audit log records every step, so you can see what was requested, what was
decided, and why.

## Stack

- Backend: Python + FastAPI, Pydantic v2 for typed, validated outputs
- Frontend: Next.js + React (TypeScript)
- Reasoning: Anthropic API, server-side only
- Storage: SQLite for the audit log and request history
- Publishing: pluggable. A mock publisher ships by default, with a documented stub for a
  real Atlassian (Confluence and Jira) adapter

## Running it locally

You'll need Python and Node installed.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env     # then add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.

## Build status

- [x] 1. Project scaffold: FastAPI + Next.js, env, .gitignore, README
- [x] 2. Schema, deterministic rules, and the sample tracking plan
- [x] 3. SQLite storage with an append-only audit log
- [x] 4. FastAPI routes + mock publisher (intake through publish over HTTP)
- [x] 4.5. Natural-language intake (server-side model drafts the definition)
- [ ] 5. Next.js UI for the single flow
- [ ] 6. Run and deploy notes

## Cost and safety

Intake turns plain language into a structured definition with a server-side Anthropic
call. That makes `POST /requests` a **cost surface**: a deployed, public intake endpoint
spends API tokens on every request. The endpoint is rate-limited and intake length is
capped (`RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SECONDS` / `MAX_INTAKE_CHARS`), but before
exposing it publicly add authentication and tighter quotas. The `ANTHROPIC_API_KEY` is
read server-side only and never reaches the browser or any response. The model only
drafts — the schema, the deterministic rules, and a human approver still govern.

## Clean room

This is a clean-room rebuild. It carries no client code, data, names, or rules from any
prior engagement. The sample tracking plan and example requests are generic and safe to
publish. Secrets live in environment variables only and are never committed.

## About

Continental Divide is a Bristlecone Echo asset. Bristlecone Echo helps organizations build
better data foundations: cleaner tracking, clearer governance, and customer and operational
insight they can act on. Roots before branches.

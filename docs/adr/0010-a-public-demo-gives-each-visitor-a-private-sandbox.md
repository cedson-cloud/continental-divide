# A public demo gives each visitor a private sandbox

Status: accepted

Amends ADR 0004. The single-organization instance remains the design for a real deployment and
is parked behind this one. This does not reopen multi-tenancy: a sandbox is a separate
database, not a tenant inside a shared one.

The project has to be something a stranger can try from a link, not only something they watch
in a recording. ADR 0004 left Vercel open "for a public, read-only demo on sample data." This
goes further: visitors make requests, and the model drafts them. That means spending money on
behalf of people nobody has verified, so the controls below are what make it safe to host.

## What a visitor gets

- **No sign-in.** On the first visit the backend issues a random workspace id in a signed,
  HttpOnly cookie.
- **A workspace is its own SQLite file**, seeded with the sample plan, with the same schema
  and the same append-only triggers. Visitors are isolated by construction: no query can
  reach another visitor's rows, because they live in another file.
- **The visitor holds every role.** Every approval is a self-approval and is marked as one
  (ADR 0004). Every audit entry records the actor as an anonymous demo visitor, unverified.
- **Five requests per workspace, however they are created** — drafted, raw, renamed or
  converted. Drafts, renames and conversions call the model; the raw path does not, but
  counting it bounds the size of the file. Viewing, deciding and exporting are not counted.
- **A CSV export** of the workspace's plan, so a visitor leaves with something.
- **A workspace is discarded 7 days after its last use.**

## Expiry and the audit log

The audit log stays append-only. Expiry deletes the whole workspace file; no `DELETE` ever runs
against `audit_log`, and no trigger gains an exception. The demo says on screen that a sandbox
and its history are discarded after 7 days. Those are the demo's terms. On a real instance
(ADR 0004), nothing expires.

## Spend

- **Per workspace:** five requests. Clearing cookies gets a new workspace, so this is a
  courtesy limit, not the spend control.
- **Per instance:** a daily model-spend cap, counted on the server from token usage. At the cap,
  drafting stops with a plain message and an audit entry, the semantic review fails advisory
  (ADR 0004's rule that an advisory call never blocks intake), and the model-free path and every
  screen without a model call keep working.
- **Workspace creation is rate limited per client IP**, read from the forwarded header the
  frontend host sets. If the real client IP cannot be read reliably through the rewrite, the
  limit falls back to a global creation rate. It slows a script; the daily cap is what stops
  one.
- **A separate Anthropic key for the demo**, with a monthly limit set in the Anthropic console.
  A ceiling that holds even if the app's own count is wrong.
- **A size cap on every write route**, `POST /requests/raw` included.

## Hosting shape

- The frontend runs on Vercel. The backend runs on Render (or Fly) as a single instance with a
  persistent disk for the workspace files.
- Vercel rewrites `/api/*` to the backend, so the browser sees one origin and the workspace
  cookie is first-party.
- The Notion push is off. Publishing uses MockPublisher only.
- The demo backend holds two secrets: the demo Anthropic key and the cookie-signing key.

## Considered and rejected

- **One shared public board.** Anyone could post anything for the next visitor to read, and
  approve each other's requests.
- **Sign in with GitHub.** A verified identity, but a wall in front of the people the demo is
  for.
- **Everything on Vercel, with Postgres.** One platform, but the storage layer and the audit
  log's triggers would have to move to Postgres first. Revisit if the demo outgrows one disk.
- **Every workspace in one shared database, keyed by a column.** Expiry would then need a
  `DELETE` on `audit_log` or an exception in its triggers, which is what the log exists to
  prevent. One leaked `WHERE` clause would also show one visitor another's requests.

## Consequences

- `acting_storage` in `routes.py` becomes the one place a request is bound to a workspace.
  `get_storage()` stays as it is for localhost and tests.
- `AUTH_MODE` gains a `demo` value, alongside the local adapter.
- The cookie is signed with the standard library's `hmac`. No new dependency.
- Running cost: about $7–10 a month for the backend host. Model spend is bounded by the daily
  cap and the console limit.
- The README's localhost-only warning is rewritten to describe the demo's controls and the
  limits that remain.

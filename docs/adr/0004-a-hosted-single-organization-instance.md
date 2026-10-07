# A hosted single-organization instance, authenticated at the edge and verified in the app

Status: accepted

Supersedes the PRD's "No auth, no multi-tenancy, localhost only" anti-scope line and the
"Hosting the app anywhere" row under Killed, with reasons. Multi-tenancy stays out.

Hosting was killed because the app had no auth, and the honest answer then was to say so
rather than half-solve it. An instance now runs for one organization, so auth has to be
whole. One instance serves one organization, with its own database. A second organization
gets a second instance.

## Identity

- **At the edge**, an identity-aware proxy (Cloudflare Access, one-time PIN to an
  allowlisted email) stands in front of the app.
- **In the app**, the backend verifies the proxy's signed token on every request: signature
  against the account's published public keys, plus issuer and audience. The app does not
  trust the proxy simply because the proxy exists, because the hosting provider's own URLs
  stay reachable and bypass it. The token check is what makes those URLs safe.
- **A bare email header is never trusted.** Anyone can send one. A test pins this.
- **Roles** — requester, approver, admin — come from an allowlist in deployment
  configuration, never the repo.
- **The audit log records the verified identity** as the actor. Typed names stop being
  evidence of who did something.

## Self-approval

One person may hold every role in a small organization. Self-approval is therefore allowed,
and always marked. The marker is derived from data — the requester's verified identity
equals the approver's — never typed. ADR 0001's gates still fire: a self-approver writes
the note and gives the acknowledgment, and the record shows one person did both.

## Hosting shape

- Two services on Render: the Next.js frontend, and the FastAPI backend with a persistent
  disk for SQLite. A service with a disk runs as a single instance and has a few seconds of
  downtime on deploy, so nobody deploys during a working session.
- One hostname. Next.js forwards `/api/*` to the backend, so there is no cross-origin call
  and the proxy's token reaches the backend.
- The instance holds definitions only. No customer or end-user data passes through it.

## Rate limits and spend

- Rate limits key on the verified user. Behind two proxies, the client IP is the proxy's,
  so a per-IP limit is meaningless.
- Model spend is capped per instance. At the cap, the semantic review fails advisory — the
  failure is recorded and the request routes normally, per the existing rule that an
  advisory call never blocks intake. Drafting fails visibly, with an audit entry. The
  model-free path stays open.

## Backups and restores

The audit log is append-only, and a restore rewinds it. That cannot be hidden, so it is
recorded.

- An admin-only download makes a consistent copy of the database (the SQLite backup API or
  `VACUUM INTO`, never a raw file copy) and writes an audit entry.
- After a restore, the first entry written states the snapshot time and that every entry
  after it was lost.
- Entries made on localhost before the instance had auth carry that fact. They were
  entered locally, before authentication, and say so.

Profile saves, backups, and restores belong to no request, and the request audit log
requires one. They go to a second append-only table for instance-level entries, under the
same no-update and no-delete triggers. The request audit log is not altered. Every entry in
either table records who acted and how that identity was verified.

## Considered and rejected

- **Trusting an identity header set by the proxy.** Rejected: the provider URLs bypass the
  proxy, and a header is trivially forged.
- **Building login into the app.** More to build, and it puts password or session storage
  in a project that otherwise holds none.
- **Vercel for this instance.** The proxy needs DNS proxying, which Vercel advises against;
  there is no persistent disk for SQLite; and the `vercel.app` URL bypasses the proxy.
  Vercel stays open for a public, read-only demo on sample data.

## Consequences

- New dependency: PyJWT, for token verification. The alternative is Authlib, which does
  more than this needs.
- Localhost has no proxy. A local identity is used only when explicitly configured, never
  as a fallback, and every entry made under it is marked as such. It lands before hosting,
  so entries made on localhost record who made them from the start.
- `approver_name` stops being the record of who approved on a hosted instance.
- The README's localhost-only warning stands until a hosted instance exists, then is
  rewritten to state the controls that exist and the limits that remain.

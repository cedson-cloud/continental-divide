# Continental Divide

Event-tracking request and governance. A requester asks for an analytics event in plain
language, a model drafts it, deterministic rules govern it, humans confirm and approve it,
and a publisher writes it out — with every step on an append-only audit log.

## Language

### What the system decides

**Reject**:
To end a request because a rule it cannot satisfy failed. Only the deterministic engine
may reject. No duplicate check of any kind rejects.
_Avoid_: Deny, fail, block

**Flag**:
To attach a finding to a request and make it visible, without changing where the request
can go next. A flag costs nobody an action.
_Avoid_: Warn, alert

**Gate**:
To require a named human action — a written note, or an acknowledgment — before a request
may move to its next status. A gate delays; it never ends a request.
_Avoid_: Block, hold, stop

**Block**:
Ambiguous between reject, flag, and gate, and has meant all three in conversation. Use the
specific term.
_Avoid_: this word entirely

### Kinds of duplicate

**Exact duplicate**:
A drafted event whose name is already in the corpus, character for character. Fact.
_Avoid_: Mechanical duplicate, hard duplicate

**Near duplicate**:
A drafted event whose name is one already in the corpus, written differently — differing
only in case, separators, or a plural, and sharing the same action verb — or a name its
platform lists as equivalent to a system event's plan name. Deterministic, but a judgment:
where the line falls is a choice.
_Avoid_: Lexical duplicate, fuzzy match, near-miss

**Semantic duplicate**:
A drafted event a model believes means the same thing as one in the corpus, under a
different name. Inference.
_Avoid_: Conceptual duplicate, soft duplicate

**Finding**:
One reported duplicate of any kind, carrying the event it points at and an argument a
human can disagree with. The unit a requester or approver acts on.
_Avoid_: Candidate, match, hit, suggestion

**Fact vs inference**:
The distinction governing what a duplicate may demand. Exact duplicates are fact; near
duplicates are deterministic judgment; semantic duplicates are inference. None of the
three may reject.

### What we compare against

**Corpus**:
The set of events a drafted request is checked for duplicates against.
_Avoid_: Catalog, plan, index

**Tracking plan**:
A published, governed set of event definitions belonging to an organization. The bundled
sample plan is one; a customer's own plan is another.
_Avoid_: Schema, spec, taxonomy

### Requests

**Draft**:
A request that passed the rules but has not yet been confirmed by its requester, so it is
in nobody's queue.
_Avoid_: Pending, unsubmitted

**Governance profile**:
The conventions, categories, and PII blocklist a request is evaluated under.
_Avoid_: Config, ruleset, policy

**Profile version**:
One saved state of a governance profile. Every request is judged by exactly one, and
records which.
_Avoid_: Revision, snapshot

**Drift**:
An approved event that no longer passes the rules of the current profile version. Drift
is reported, never fixed automatically.
_Avoid_: Violation, regression, stale event

**Proposed event**:
A draft the system suggested rather than one a requester asked for. It goes through the
same loop as any other draft.
_Avoid_: Suggestion, generated event, candidate

**Proposal batch**:
The set of proposed events produced from one intake.
_Avoid_: Bulk request, import

**Actor**:
The person an audit entry says took the step, and how that was established: verified
against a signed token, or claimed by local configuration and marked unverified. Every
audit entry names one. A typed name on a form is not an actor.
_Avoid_: User, approver name, author

**Self-approval**:
An approval whose actor also made or submitted the request, compared by email. Derived
from the audit log, never typed. Allowed, and always marked; when the request's entries
name no actor, the marker says unknown rather than no.
_Avoid_: Auto-approval, own approval

**Impact**:
Whether an event matters to the whole business or to one team. Chosen by a person, never
by the model, and it never blocks.
_Avoid_: Priority, severity

### What an event definition holds

**Call type**:
What kind of thing a definition records: `track` (something a person did), `identify`
(who the person is), or `group` (the organization they belong to).
_Avoid_: Event type, method

**Trait**:
A fact about a person or an organization, carried on an `identify` or `group` call.
_Avoid_: Attribute, user property (for traits; a track call carries properties)

**Canonical ID**:
The one stable identifier a plan uses for a person. Never an email address.
_Avoid_: User ID (ambiguous across tools), distinct ID, primary key

**Surface**:
Where a call is made from — a browser, a server, or another platform.
_Avoid_: Platform (a surface's code comes from a platform), channel, source

**Trigger**:
The moment on a surface that causes a call to fire.
_Avoid_: Hook, when

**System event**:
An event an analytics tool's SDK records on its own: a page or screen view, an app
lifecycle event. The plan shows it under a **plan name** that follows the plan's
convention (`Page Viewed`), not the name the SDK sends (`$pageview` in PostHog, a `page`
call in Segment). A platform file lists them, and they are always in the corpus of a
profile that names that platform.
_Avoid_: Auto event, built-in event

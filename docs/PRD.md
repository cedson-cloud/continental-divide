# Continental Divide — Product Requirements

## What it is

> Continental Divide turns "I need to know something about our users" (asked in
> plain English by anyone in a business) into a spec-compliant, human-approved,
> documented tracked event, and gives each role the artifact it actually needs.

The README's first line must be that sentence. A section of this document that
doesn't serve it is wrong.

Amended 2026-07-30: the README opens with the sentence **minus its final clause**,
because "gives each role the artifact it actually needs" is not true while
engineering's output does not exist — see the role table below. Restoring that
clause to the README's first line is part of done for the snippet work, and is the
check that the four-role claim has been earned rather than asserted.

## The loop and its four roles

This is a loop with four roles, and each role has an output.

| Role | Their output | Status |
| :--- | :--- | :--- |
| **Requester** — anyone in the org | A well-formed request they didn't need expertise to write | Built — the `/request/new` wizard, `POST /requests` |
| **Data team** — approver | A decision they can make fast, with evidence, on the record | Built — the `/queue`, the rules engine, agent review, the audit log |
| **Engineering** | Accurate, spec-correct code for the SDK they actually use | Not built — no generator, no platform specs |
| **The business** | A data dictionary — what is tracked, what it means, where it goes | Built — `GET /catalog` and the `/catalog` browser |

Three of the four outputs exist. Engineering's is the gap: there is no snippet
generation and no platform specs, so the one role that has to write the code is
the one role handed nothing. That end of the loop is worth more than any further
depth in the middle, which is already the thickest part of the app.

## Enforce or author — the seam

Both, with an explicit seam between them.

| Moment | Behaviour |
| :--- | :--- |
| **At intake — enforcement** | The active profile is law. The engine rejects what violates it, deterministically, and the model has no vote. No auto-loosening, ever |
| **At intake — but survivable** | A rejection is never terminal. It offers a compliant name the engine itself vouches for, a one-click resubmit, and consent recorded in the audit log |
| **At intake — the dissent door** | *"This rule looks wrong for us."* Records the disagreement, stamped with the profile version in force when it was raised, and routes it to a data-team review queue. It amends nothing — no profile change, no file write, no status change, no model call |
| **Authoring — a separate, deliberate act** | The data team amends the profile on its own screen. In the repo, the YAML is committed and `git log` is the history; on a hosted instance, each save is an audited profile version ([ADR 0006](adr/0006-governance-profiles-are-versioned-and-edited-in-the-app.md)). Never the same screen as intake, never the same moment |

### What this decides about naming rejections

A rejection under the active profile stands. The rules engine is not loosened
behind a data team's back. Instead:

1. The rejection is survivable, and the requester can flag the rule.
2. The convention gains a profile knob — `verb_position: before_connector |
   rightmost`. A team that wants a given name legal **authors** its way there and
   owns the trade-off — word order stops being enforced — in its own versioned
   YAML.

The rule holds, the human decides, the decision is versioned. The same
fact-versus-inference split the rules engine already draws, one level up.

The two intake-side doors are built. `verb_position` is not: it appears nowhere in
the profile schema or the rules engine, so today a team that disagrees with a
naming rejection can dissent but cannot yet author its way out. It is v1.1
authoring work, not required for v1.

## Anti-scope

Each line kills work.

- **It does not design your tracking plan.** It *captures* a request and holds it
  to a standard. Anything the tool proposes is labelled as proposed and needs the
  same human approval as anything else. This is the constraint the whole
  architecture exists to protect.
- **It does not move data.** Not a CDP, not a pipeline, not an ETL. It emits specs
  and code, not events.
- **It is not a linter.** Validation is table stakes. The product is telling
  someone something they did not already know — that the thing they want already
  exists.
- **No `page` or `screen`.** v1 was `track` only; `identify` and `group` joined
  in [ADR 0003](adr/0003-identify-and-group-join-track.md), which also sets where personal-data traits may go.
  A platform's own page and screen events are existing events a request can refer to
  and collide with ([ADR 0009](adr/0009-a-platforms-system-events-are-existing-events.md));
  they are not call types.
- **No free-form regex for naming conventions, ever.** This does not extend to the
  PII blocklist. A PII entry is a lowercase token substring-matched against
  property names — no compile step, no injection surface. Free-form PII tokens are
  fine. Free-form naming regex is not.
- **No auto-convert, no auto-fix, no auto-amend.** Explain, then confirm.
- **No multi-tenancy.** One instance serves one organization. Auth and hosting left
  anti-scope in [ADR 0004](adr/0004-a-hosted-single-organization-instance.md): authenticated at the edge, verified in the app. Until a
  hosted instance exists, the README's localhost-only warning stands. The public demo
  gives each visitor a separate database ([ADR 0010](adr/0010-a-public-demo-gives-each-visitor-a-private-sandbox.md)):
  that is isolation, not tenancy.
- **No embeddings** until a catalog passes roughly 500 events. One model call
  against a catalog this size is correct today.
- **Not a Notion product.** Notion is one publish target among several, not the
  system of record.

## v1 = done

A stranger can use it:

1. `git clone`, follow the README, reach a working app on the first try.
2. Walk one event through the whole loop — request → rules → agent review →
   approve → snippet → dictionary entry — without asking anyone for help.
3. Hit a naming rejection and get out of it.
4. Read six ADRs and understand why each seam is where it is.
5. See an honest known-issues list, including "no auth."

Plus, so the loop can be shown without a clone: a short recorded walkthrough,
README screenshots at the moments that carry the argument — the catalog hit, the
three doors on a duplicate finding, the snippet, the dictionary entry — and a
README that makes the argument to someone who will never run it.

**Explicitly not part of done:** every critique resolved, all three SDKs supported,
hosted anywhere, or any role fully served.

### The 60-second story

> *Someone in marketing asked, in plain English, for something they wanted to
> measure. The tool told them it already existed and they took the existing event —
> no new event was created, and the audit trail records why. When they asked for
> something genuinely new, the data team approved it in one screen, engineering got
> working code for their actual SDK, and the whole company got a dictionary entry
> explaining what it means.*

Every clause is a demo beat. One of them does not exist yet: engineering's code.

## The cut list

### Required for v1

| Item | Why it's v1 |
| :--- | :--- |
| **Data dictionary / catalog view** — `GET /catalog` plus a browsable route | The business's output. The data already exists; this is a surface, not a build |
| **Code snippets per SDK**, generated from a platform spec and syntax-checked in CI | Engineering's output, and half the thesis |
| **Platform specs as data** (`platforms/*.yaml`) | Prerequisite for snippets and canonical names |
| **Guided rename-and-resubmit, plus the "this rule looks wrong" flag** | The requester-facing defect |
| **A PII flag must not render as a hard failure** | Two red marks where only one is blocking is a lie about severity |
| **README rewrite, six ADRs, cold-clone doc** | Without written decisions, every seam reads as accidental |
| **Recorded walkthrough and README screenshots** | Without these, nothing is showable without a clone |
| **Frontend test coverage, and a check script that runs both suites** | Collection is not execution |
| **Governance wizard: free-form PII, and show the inherited blocklist** | Not fit for a data team without it |
| **Event picker / autocomplete** instead of free-text existing-event | Cheap once the catalog endpoint exists |

### After v1

Live eval tier · `source: requested | suggested` properties · the structured event
display · approver-side convert or send-back for `duplicate_unsure` · canonical-name
allowlist · `verb_position` profile knob · starter-plan batch intake (see [Deferred, not killed — starter plan
generation](#deferred-not-killed--starter-plan-generation)) ·
MCP server · PostHog publish and reconcile · admin profile history · re-vet on rule
change · agent-review prose tightening.

Several of these were pulled forward for the first hosted instance — the live eval
tier, batch intake, profile history, and re-vetting on rule change. Their order and
status live in [TASKS → Parked: first hosted instance](../TASKS.md#parked-first-hosted-instance).

### Deferred, not killed — starter plan generation

Generating a first base tracking plan from scratch looks like a violation of [it
does not design your tracking plan](#anti-scope). It isn't, in one specific form.

A starter plan is not the tool authoring a plan. It is the tool **making a batch of
requests on the organization's behalf** — N proposed events, each labelled as
proposed, each entering the *same* intake → rules → agent review → human approval
loop, each individually approvable or rejectable, each with its own audit trail.
The `source: requested | suggested` field planned for properties extends to whole
events.

The seam does the work again, and the demo is better than the original: *it
proposed fourteen events for an ecommerce business, the rules rejected two of them,
and a human approved nine.* Deferred on scope, **not killed** — and recorded here
so it can't return later as a scope violation.

### Killed, with reasons

| Item | Reason |
| :--- | :--- |
| `page` / `screen` support | Triples the rules surface, zero demo payoff. *`identify` and `group` were revived in [ADR 0003](adr/0003-identify-and-group-join-track.md); a platform's page and screen system events count as existing events ([ADR 0009](adr/0009-a-platforms-system-events-are-existing-events.md))* |
| ~~Hosting the app anywhere~~ | **Revived in [ADR 0004](adr/0004-a-hosted-single-organization-instance.md)**, which supplies the auth this row was waiting for. Original reason: no auth. Say so in the README instead of half-solving it |
| Embeddings for duplicate detection | Wrong below roughly 500 events |
| ~~Screenshot-driven event design~~ | **Revived in a bounded form in [ADR 0007](adr/0007-screenshot-intake-proposes-people-decide.md)**: a capped batch feeding the existing loop, one draft per proposed event. Original reason: unbounded scope, adds an image-input surface, and [batch intake](#deferred-not-killed--starter-plan-generation) gets the same demo beat more cheaply |
| Governance wizard writing to git server-side, or opening a PR | An unauthenticated write path into a repo. Download-only is safer *and* better — the data team commits the file and thereby owns it. *Still killed: [ADR 0006](adr/0006-governance-profiles-are-versioned-and-edited-in-the-app.md) lets an admin save profile versions to the instance's database, never to git* |
| `pii.mode: block` | Reserved in schema, never needed. Flag-and-acknowledge is the designed behaviour |
| Chasing an empty critique list | Not a definition of done |

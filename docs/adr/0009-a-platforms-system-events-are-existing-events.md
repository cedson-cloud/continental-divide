# A platform's system events are existing events

Status: accepted

Amends ADR 0003 ("`page` and `screen` stay out"), ADR 0005 (what the corpus holds), and
ADR 0001's near-duplicate tier. Supersedes none of them.

Analytics SDKs record some events on their own. PostHog's browser SDK sends `$pageview` on
every page load; Segment's analytics.js sends a `page` call by default; both platforms'
mobile SDKs send lifecycle events such as `Application Opened`. A team that does not know
this asks for `Page Viewed` as a custom event, and from then on two events count the same
thing. Every report built on one disagrees with every report built on the other. This is
one of the commonest ways a tracking plan goes wrong, and the tool could not see it:
system events were in nobody's corpus.

## The decision

- **A system event has a plan name.** The plan shows each system event under a name that
  follows its own convention — `Page Viewed`, `Screen Viewed`, `Application Opened` — not
  the name the SDK sends. A `$`-prefixed name in a plan confuses the people who consume
  the data. The name sent appears only as "sent as" and in the wiring instructions.
- **Plan names are the same on every platform.** `Page Viewed` is PostHog's `$pageview`
  and Segment's `page` call. Where the platform supports it, the wiring instructions say
  how to show the plan name in the tool: in PostHog, an action named `Page Viewed` on
  `$pageview` (actions rename an event and apply retroactively).
- **A platform file lists the platform's system events** (ADR 0008: a platform is a file,
  not code). Each entry gives the plan name, the name or call the SDK sends, what it
  records, which SDK sends it, and any **equivalent names** that differ in words rather
  than spelling (`Page Loaded`, `App Launched`). The file records the docs it was checked
  against and the date.
- **A governance profile names its platform.** The platform is part of what a request is
  judged against, so it is versioned with the profile (ADR 0006). A profile that names no
  platform has no system events.
- **The active platform's system events join the corpus under their plan names,**
  whatever the instance's seed. An instance whose seed is empty (ADR 0005) still knows
  that `Page Viewed` exists. The data dictionary marks them as system events.
- **Collisions use the tiers that already exist.** A request named `Page Viewed` is an
  exact duplicate of an existing event, and the requester is shown that the SDK already
  sends it; converting the request into a property on that event is the natural next
  step. `page_viewed` and `Pages Viewed` are near duplicates by the existing
  normalization. A listed equivalent name is a near duplicate too: deterministic judgment,
  where the list is the line. ADR 0001's gates apply unchanged, and no tier rejects.
- **A system event can take a property request,** under its plan name. The property goes
  through every property rule. How a property reaches the event on each platform is
  recorded in the platform file and rendered by the snippet generator (ADR 0008).
- **The vetter recognizes system events by plan name and by sent name,** using the
  profile's platform. A `$`-prefixed name gets the `system` verdict and a note giving its
  plan name. A plan name gets the `system` verdict and a note that the SDK sends it, so it
  must not also be sent as a custom event. A plan that lists both names for one system
  event lists it twice.

`page` and `screen` stay out as **call types**. ADR 0003's reasons hold: each would add a
rules surface. A platform's page and screen events are existing events that a request can
refer to and collide with.

Not every system event gets a plan name. `$autocapture` is a stream of interactions, not
one event: the plan's events are the actions defined on it. `$identify`, `$create_alias`
and `$groupidentify` are the identify and group calls the plan already models (ADR 0003).

## The semantic review waits

The semantic reviewer is shown the corpus in its prompt. Adding system events to it
changes the prompt, so that part waits for the live eval tier, as ADR 0005 requires. Until
then the engine finds these collisions and the model does not see system events.

## Considered and rejected

- **Show the sent name in the plan.** `$pageview` means nothing to someone reading a
  dashboard, and it differs by platform.
- **Leave it to the semantic review.** Inference, and only as good as the model on the day.
  The commonest duplicate in practice should not depend on a model noticing it.
- **Widen the near-duplicate tier to character similarity.** ADR 0001 rejected that: it
  cannot tell which token defines the event.
- **Reject the custom event.** No duplicate tier rejects (ADR 0001). There are rare,
  legitimate reasons to send both, and the requester can make the argument on the record.
- **Add `page` and `screen` call types.** See ADR 0003.

## Consequences

- `CONTEXT.md`: **system event** is redefined around the plan name; **near duplicate**
  gains listed equivalent names.
- The PRD's "No `page` or `screen`" line and its Killed row point here.
- Two platform files ship: PostHog's and Segment's. Item 12's snippet templates extend the
  same files.
- A profile change that switches platform changes the corpus. Drift (ADR 0006) reports
  approved events that newly collide; nothing is changed automatically.
- Some system events exist only on one platform (`Page Left` is PostHog's `$pageleave`;
  Segment has no equivalent and infers a page exit from the next `page` call).

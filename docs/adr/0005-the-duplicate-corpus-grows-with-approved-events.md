# The duplicate corpus grows with approved events

Status: accepted

Supersedes ADR 0002.

ADR 0002 recorded that every duplicate tier compares against the bundled sample plan and
nothing else, so the tool had no memory of its own decisions: approve an event today and
the same request next month is found novel and published a second time. It left four
questions open. This ADR answers them.

## The corpus

The corpus is an instance's **seed** plus every request whose status is `approved` or
`published`.

- **The seed may be empty.** The public demo seeds with the bundled sample plan. An
  organization's instance may start with nothing and build its corpus as it approves
  events.
- **Drafts and requests in flight do not join.** A finding raised against a draft that is
  later withdrawn cannot be taken back: the append-only audit log keeps it. Approved and
  above is the cut ADR 0002 suggested.
- **A proposal batch is checked against itself.** When one intake produces several
  proposed events (ADR 0007), the engine runs its exact and near checks across the batch
  as well as against the corpus. Two proposed events in one batch are both in flight, so
  neither would otherwise see the other.

## The prompt change waits for the live eval tier

The semantic reviewer is shown the corpus in its system prompt. Widening the corpus changes
that prompt, and with it model behaviour. The live eval tier lands first, so the change can
be measured rather than assumed.

## No process-lifetime cache

The sample plan and the lists built from it are cached for the life of the process. A
corpus that changes whenever a request is approved cannot be, so those caches go.

## Considered and rejected

- **Including requests in flight.** See above: a false finding becomes permanent.
- **Seeding every instance with the sample plan.** An organization's plan is not an
  ecommerce sample. Findings against events it never had would teach requesters to ignore
  findings.

## Consequences

- The data dictionary and the corpus now hold the same events. ADR 0002's surprising
  divergence is gone.
- Two identical requests a week apart can route differently. That is the point, but a
  routing decision can then only be explained by what the corpus held at the time, and the
  audit entry has to say.
- With an empty seed there is no sample plan to borrow categories from. A profile on such
  an instance must declare its categories.
- Still open: two overlapping requests that are both in flight miss each other until one is
  approved. A re-check at approval time would catch it and is not decided here. Also open:
  whether an approved event later retired through a rename (ADR 0006) keeps its old name in
  the corpus.

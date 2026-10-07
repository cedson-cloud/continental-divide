# Screenshot intake proposes; people decide

Status: accepted

Revives the deferred starter-plan batch intake, and overturns the "Screenshot-driven event
design" row under Killed, with reasons, in a bounded form.

Describing an event in words assumes the requester already knows what to track. Often
they have a screen and a question instead. A second way in, **Show me**, takes a few
screenshots of the product and an optional note, and proposes events for them.

## The decision

- **Bounded.** Up to five frames and about eight proposed events per batch. One proposal
  call, then one review call per proposed event.
- **Each proposed event is its own draft.** It is marked as proposed, linked to its
  **proposal batch**, and goes through the full loop: rules, review, requester
  confirmation, approval. Nothing is approved in bulk.
- **The model proposes; it does not enforce.** Proposed names are recorded as drafted and
  judged by the engine, like any other. The model may suggest the why and the question an
  event answers. It never sets impact.
- **Frames are stored and hashed.** Each frame is kept on the instance's disk, and its
  SHA-256 goes into the audit log, so any proposed event can be traced back to the frame
  it came from.
- **On-screen text is untrusted data.** Text inside a screenshot is content to describe,
  never an instruction to follow.
- **Public fixtures use fictional mock frames only.**

## Why this is not the tool designing the plan

The original kill reason was unbounded scope plus an image-input surface, and that batch
intake buys the same demo more cheaply. Both still hold, which is why the form is narrow:
a capped batch that feeds the existing loop one draft at a time. The output is a set of
requests a human confirms one by one, not a plan.

## Consequences

- An image-input surface exists. A frame can show more than the requester meant to share.
  Frames stay on the instance's disk, go nowhere except the model call, and are deleted
  with the instance.
- A batch is checked against itself for exact and near duplicates (ADR 0005).
- Spend per batch is bounded: one call plus one per proposed event.

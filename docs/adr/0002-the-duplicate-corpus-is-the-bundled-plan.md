# The duplicate corpus is the bundled sample plan, and the data dictionary deliberately shows more

Status: accepted, with the expansion open

ADR 0001 settles who may report a duplicate and what each tier may demand. This one
settles the other axis: **what we compare against.** Today all three tiers compare against
the bundled `sample_tracking_plan.json` and nothing else, while the data dictionary shows
that plan *plus* every approved request. The two sets differ on purpose, and a reader who
assumes otherwise will misjudge what the tool guarantees.

## What the corpus excludes

Nothing writes to `sample_tracking_plan.json`. `publisher.py` emits an artifact and pushes
to Notion, and stops there. So the corpus omits two populations:

- **Events this tool published.** Approve `Wishlist Product Added` today and the plan still
  holds its original 28 events. The same request next month is checked against the same 28,
  found novel, and published a second time. The tool has no memory of its own decisions.
- **Requests in flight.** Two teams filing overlapping requests in the same week are both
  absent from the plan, so exact, near, and semantic all miss — even though
  `storage.list_requests()` returns every row with its parsed definition.

Both are the same omission, and it means the tool detects duplicates against its seed
catalog rather than against reality. The demo works because the catalog is a static
fixture.

## Why the dictionary and the corpus diverge

`catalog_view.py` composes the sample plan with approved requests and marks the source of
each entry. It deliberately does not touch `catalog.py`, because `catalog_entries()` is
rendered verbatim into the duplicate-review system prompt — widening it would change model
behaviour, and that is a prompt decision, not a display decision.

That divergence is the right call for now, but it is the surprising part. The reader of a
data dictionary that lists published events will reasonably assume duplicate checks cover
them. They do not.

## Consequences

- The core value proposition degrades the moment someone actually uses the tool. This is
  stated in the UI rather than hidden.
- The three tiers of ADR 0001 are only as good as this set. Sharper detection over a frozen
  28-event fixture is a better demo, not a more useful tool.
- Sequencing: the tiers land first. A wider corpus feeding gates that do not fire changes
  nothing, so the gates come first and the corpus second.

## What the expansion still has to decide

- **Published events into the review corpus** changes a prompt and needs the live eval tier
  to measure the effect, so it waits on that.
- **In-flight drafts** are the harder question. Flagging a request against a draft that is
  later withdrawn is a false positive with nothing to un-ring it, and the append-only audit
  log means the flag is permanent. Approved-and-above may be the right cut.
- **Caching.** `known_event_names()` and `catalog_entries()` are both `@lru_cache`. A corpus
  that changes as requests are approved cannot be cached for the process lifetime.
- **Deployment.** A real deployment reads the customer's own plan, not the bundled sample.
  Not required for v1, but the corpus should not be built in a way that assumes one file.

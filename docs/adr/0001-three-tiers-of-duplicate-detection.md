# Duplicate detection has three tiers, and the model never computes what the engine can

Status: accepted

Duplicate events are the failure this tool exists to prevent, and they arrive in three
different shapes: the same name, a name a character away, and a different name for the
same behaviour. We had been treating this as a two-sided seam — the engine reports fact,
the model reports inference — which left the middle shape unowned. This ADR splits
duplicate detection into three tiers, assigns each an authority, and fixes what each one
is allowed to demand of a human.

## The tiers

| Tier | Authority | May reject | Demands of a human |
| --- | --- | --- | --- |
| Exact | Fact — the name is in the corpus | No | Approver must acknowledge before approving |
| Near | Deterministic judgment — same name after normalization, or the same name inflected | No | Requester must give a note, or pass the question to the approver |
| Semantic | Inference — a model's argument | No | Same as near, but only for high-confidence findings |

**No tier rejects.** Rejection stays with the rules that admit no argument: event naming,
category membership, and property naming. A duplicate check can delay a request and put a
human on the record; it can never end one on its own.

**The ordering never inverts.** Whatever a lower tier demands, a higher tier demands at
least as much. Certainty must never be quieter than a hunch.

## Why three, and why the middle one is deterministic

The middle tier is the one that matters most in practice. `Order Completed` against
`order_completed`, or `Products Added` against `Product Added`, are the collisions that
cause the most organizational pain, and they need no model to find. `vet.py` had already
implemented near-duplicate clustering for auditing third-party plans. Intake had not, and
the review prompt told the model that near-lexical matches were "already handled by a
deterministic engine" — true of the batch CLI, false of intake. The one class of duplicate
we most wanted caught was caught by nobody.

So "mechanical" is redefined as **deterministic**, not **certain**. That gives the middle
tier somewhere to live.

**The comparison is token-aware, not character-similarity.** A name is normalized by
splitting on separators and camelCase boundaries and lowercasing, giving a token list. Two
names are near duplicates when those token lists are identical, or when they are identical
after removing simple plurals — and only when the final token, the action verb, matches
exactly.

The verb condition is what makes this usable. Character similarity measures the wrong
thing: it cannot tell that the differing token is the one that defines what the event
means. Measured against the bundled sample plan — Segment's own curated Ecommerce V2 spec,
which contains no duplicates by construction — a 0.85 character-similarity threshold
reports two: `Product Reviewed` against `Product Viewed` at 0.929, and `Product List
Viewed` against `Product Viewed` at 0.867. Both are false. Under the token rule the same
plan yields none, while `Product Added`/`Products Added` and every case-and-separator
variant of `Order Completed` are still caught.

## What the semantic reviewer sees, and what is withheld

The reviewer is given the requester's own words (`raw_intake_text`) and denied their
stated business value.

Behaviour is the question; motive is not. Two teams instrumenting the same user action for
different reasons still need one event — that is one of the collisions we are trying to
prevent — and business value is precisely the argument that would let a model conclude
"different purpose, therefore not a duplicate." Withholding it follows the discipline
already applied to the PII blocklist: starve the model of the input that would let it
reason its way to the wrong answer. Business value is the approver's input, not the
reviewer's.

For the same reason, the model is told to calibrate its confidence honestly but is **not**
told what confidence controls. A reviewer that knows `high` conscripts two humans, and has
also been told that costing humans decisions is bad, has an incentive to soften.

## Visibility and friction are separate knobs

Every semantic finding is shown. Only high-confidence ones are gated.

The earlier prompt told the model that over-flagging was worse than under-flagging, and
its stated reason was that every finding costs a human a decision. That was true only
because gating was indiscriminate: any finding, at any confidence, forced a note from the
requester and an acknowledgment from the approver. Asking for more flagging while keeping
that gate would produce ritual compliance — requesters typing "not a duplicate" without
reading — and a rubber stamp is worse than no gate, because it manufactures an audit trail
of consideration that never happened. `ReviewFinding.confidence` was already collected,
stored, and displayed while changing nothing; gating on it is what makes wider flagging
affordable.

## Considered and rejected

- **Letting exact matches reject outright.** Rejected: there are legitimate reasons to
  publish against an existing name, and the tool's job here is to make the collision
  impossible to miss, not to decide it.
- **Uniform but cheap friction** — gate every finding, but as a single click with no free
  text. Rejected: the written note is the learning moment, and it is the reason a
  dismissal is a governance record rather than a checkbox.
- **Embeddings for the semantic tier.** Rejected for now; one model call against a
  28-event plan is right at this size. See TASKS.md.

## Consequences

- **The near tier does not share code with `vet.py`.** The two jobs differ: `vet.py`
  compares a whole plan against itself pairwise and wants recall, while intake compares one
  name against the corpus and must not cry wolf at a requester. `vet.py` keeps its
  `_normalize`/`_near` clustering at 0.85; intake gets its own token rule. Reusing one
  helper across both would change audit behaviour to serve intake, which is reuse for its
  own sake.
- At intake, cross-convention collisions (`order_completed` against `Order Completed`) are
  usually caught by the naming rule first, which rejects whichever form the active profile
  disallows. The near tier's real contribution at intake is inflection and spacing. The
  convention-agnostic tokenizer still matters, because a profile can set either convention.
- The token rule is deliberately narrow. `Checkout Step Started` against `Checkout Started`
  is not flagged: the noun phrase genuinely differs. Catching that class is the semantic
  tier's job, which is where a disagreement can be argued rather than asserted.
- The tiers need no new `Decision` member. `flagged_duplicate` covers the routing outcome;
  which tier fired is carried in the rule checks.
- Gating on the deterministic tiers cannot read `duplicate_candidates`, which only the
  model writes. It reads the `rules_evaluated` audit entry, the same way `submit_request`
  already recovers its decision from the `routed` entry.
- `POST /requests/raw` skips requester confirmation by design, so there is no draft state
  in which to demand a note. On that path the exact-match acknowledgment falls to the
  approver alone. The two intake paths do not behave alike, and should not be described as
  if they do.
- **All three tiers compare against the bundled sample plan.** They do not see events this
  tool published, or requests sitting in its own queue. That boundary is a separate
  decision — see ADR 0002 — and it limits what this one delivers.

## Current state

The decision is accepted; the implementation follows it in steps. As of this writing the
exact tier flags but gates nothing, the near tier does not exist on the intake path, the
semantic tier gates every finding regardless of confidence, `confidence` is inert, and the
reviewer sees neither `raw_intake_text` nor business value. Delete this section when the
tiers ship.

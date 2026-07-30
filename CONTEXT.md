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
A drafted event whose name matches one in the corpus once case and non-alphanumerics are
stripped, or sits at or above the similarity threshold. Deterministic, but a judgment —
the threshold is a choice.
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
The versioned file naming the conventions, categories, and PII blocklist a request is
evaluated under.
_Avoid_: Config, ruleset, policy

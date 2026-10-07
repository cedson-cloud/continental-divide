# Identify and group join track

Status: accepted

Supersedes the PRD's "v1 is `track` only" anti-scope line and the matching row under
Killed, with reasons.

A tracking plan made only of `track` calls cannot be wired. Before the first event fires,
someone has to decide what identifies a person, when that identity is attached, and which
facts about the person travel with it. Leaving that out did not keep the plan simple; it
left the hardest decision in the plan to whichever engineer shipped first. So the plan now
holds three **call types**: `track` (something a person did), `identify` (who the person
is, and their **traits**), and `group` (the organization a person belongs to, and its
traits). `page` and `screen` stay out.

## Personal data

A trait that is personal data — an email address, a name — belongs on `identify` and
nowhere else. Track properties never carry it.

"Never" is enforced as a gate, not a rejection. The PII rule stays advisory, as it has
been since PII moved from auto-reject to flag-and-acknowledge, and `pii.mode: block` stays
killed. What changes is what a PII hit costs:

| Where the hit lands | Requester | Approver |
| --- | --- | --- |
| A trait on `identify` | A written reason for that trait | Acknowledges |
| A property on `track`, or a trait on `group` | A written reason for that property | Acknowledges |

The demand is the same on every call type. What differs is the finding's message: on
`identify` personal data is in the right place and the reason explains why it is needed;
anywhere else the finding says the data belongs on `identify`, and the reason has to argue
otherwise on the record.

Why not reject: the PII blocklist is token matching, and a false match on a rejection has
no recourse but a rename. A written reason plus an acknowledgment puts two people on the
record for every piece of personal data the plan carries, which is the point of "never."

## The canonical ID

A plan names one **canonical ID**: a stable identifier for a person that does not change
when their email does. Email is captured as a trait, never used as the ID.

This is not a style preference. Analytics tools merge a person's anonymous and identified
activity only through an explicit `identify` or `alias` call, not by matching property
values, and some refuse to merge a person who is already identified. Identifying by email
splits a person in two the day the address changes, with no supported way to rejoin them.
A plan that uses an email as the ID shows that pattern as an anti-pattern, with the reason.

## Group

Group analytics is a paid add-on in some tools. A plan that uses `group` says so, and names
a person trait that carries the organization's name as the fallback when the add-on is
absent.

## Considered and rejected

- **Staying `track`-only.** The original reason — it multiplies the rules surface for no
  demo payoff — was right about the cost and wrong about the payoff. A plan without
  identity is not a plan anyone can implement.
- **`page` and `screen`.** No need has appeared, and each adds a rules surface. Still out.
- **Rejecting PII outside `identify`.** See above.

## Consequences

- `Decision` gains no member. Call type is part of the definition, not a routing outcome.
- Traits go through the same naming, PII, and duplicate checks as properties.
- The written reason belongs to the request, not the definition. On the model path the
  requester gives it when submitting a draft. `POST /requests/raw` has no requester step, so
  the reasons travel in the request body, and a PII hit without one is refused. On both
  paths the requester argues and the approver acknowledges.
- The governance wizard's "something about a user" card stops being a dead end.
- The drafting prompt learns the call types from the active governance profile, like
  everything else it is told. The PII blocklist stays withheld from it.

# Platform files say what they know, and how they know it

Status: accepted

Amends ADR 0009 (what a platform file holds). Supersedes none of it.

ADR 0009's platform files named each system event and nothing else. The data dictionary
then showed Application Opened, Screen Viewed and the rest with no properties, and it said
nothing about the fields every event already carries: the page URL, the UTM source, the
app version. A requester reading it would ask for `app_version` as a new property, and a
practitioner reading it would conclude the tool gets Segment and PostHog wrong. An empty
list was being read as "none", when it only meant nobody had looked.

## The decision

- **A platform file lists its libraries,** each marked browser, mobile or server. Lifecycle
  defaults really do differ by library: Segment's Swift library sends lifecycle events by
  default, while its Kotlin and React Native libraries do not.
- **A system event lists its properties, and which libraries send it by default.** A
  missing property list means "not listed yet". An empty list means the sources say the
  event carries none of its own. The two never read the same.
- **A platform file lists its common fields:** what every event from a library carries
  without being asked, under the platform's own key (`context.page.url`, `$current_url`)
  and a plain name, grouped for reading.
- **Reserved names are listed apart from system events.** Segment's Mobile spec defines
  `Push Notification Received`, `Install Attributed` and others that its libraries never
  send: the team or a partner does. A request for one of those names follows the spec, so
  it is not a duplicate. Reserved names are shown to readers and kept out of the corpus.
- **Every common field, named system event and reserved name cites its sources, and every
  claim carries its evidence:** `docs` (the vendor's docs say so), `sdk_code` (read in the
  vendor's SDK code on GitHub, which can be ahead of a release), or `disputed` (the sources
  disagree, and the note says how). Anything the sources mention
  that the file does not list goes under `not_listed_yet`, so a missing field is never
  taken for one the platform does not send.
- **Nothing in a platform file is written from memory.** The file records the date it was
  checked.

## Considered and rejected

- **Make reserved names system events, so a request for one is flagged.** The duplicate
  check would tell the requester that something already sends the event, which is false,
  and it would put a finding on every request that follows the spec.
- **Leave out claims that rest on SDK code or disputed docs.** A field left out reads as
  one the platform does not send, which is the mistake this ADR fixes. A tag tells the
  reader how far to trust each claim.
- **A different sent name per library** (PostHog sends `Application Became Active` from
  React Native, and `Application Opened` with `from_background` from iOS and Android).
  Each sent name would need its own uniqueness rules. A note on the event carries the
  difference instead.
- **Flag a requested property that is already a common field.** That would be a new kind
  of rule: duplicate detection compares event names today. Matching `app_version` to
  `context.app.version` or `$app_version` takes judgment, which has to be designed to stay
  deterministic and never reject. It waits for its own ADR, after launch.

## Consequences

- `CONTEXT.md` gains **common field** and **reserved name**.
- PostHog's Application Foregrounded is sent as `Application Became Active` by React Native
  only, where ADR 0009's file had it for every mobile SDK.
- Segment's Experiment Viewed loses `Variation Viewed` as an equivalent: no Segment doc
  names it.
- Deep Link Opened and the other events the files were missing join the corpus, so a
  request for one of them is now a duplicate finding.
- The data dictionary shows the properties, common fields and reserved names in the second
  D13 pull request. Until then it shows only the new system events, with their
  properties still "not listed yet".

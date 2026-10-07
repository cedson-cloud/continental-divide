# Snippets are deterministic and per surface

Status: accepted

The PRD makes code snippets engineering's half of the output: "generated from a platform
spec and syntax-checked in CI." This ADR settles how.

## The decision

- **No model writes code.** A snippet is rendered from a template and an approved
  definition. One definition produces one snippet per surface, the same every time.
- **One snippet per surface the event lives on.** A **surface** is where a call is made
  from. The repo ships three: the browser SDK, a server SDK (Node and Python), and a raw
  HTTP call.
- **Names and values are encoded, never pasted.** Every name and value is written as a
  string literal encoded for the target language.
- **Keys are placeholders.** No snippet carries a real project key.
- **Snippets are parse-tested,** and each template's SDK signatures are checked against
  the SDK's published docs. Each snippet's header records the SDK version and the date of
  that check.
- **Templates are data.** A platform is a file, not code. An instance can load extra
  platform files from its own instance directory, outside the repo. A surface specific to
  one organization's tools lives there, never in the public repo.

Which surfaces an event lives on is recorded on the request, defaulted from where the
requester said it fires: client gives the browser surface, server gives the server surface,
and unsure gives both, marked as unresolved in the export. An instance-only surface is
added only by explicit choice.

## Why encode when names are already validated

Every name the engine accepts today happens to be letters, digits, spaces, and underscores,
so pasting one into code would work. Relying on that would tie the generator's safety to
the naming rule. The rule changes: a convention with a colon in it is coming (ADR 0006),
traits and descriptions carry free text, and a requester's own name is recorded verbatim.
The generator encodes, so that changing a naming rule can never change what code is safe
to generate.

## Considered and rejected

- **Model-written snippets.** They cannot be tested for every event, and two approvals of
  the same definition could produce different code. A wrong snippet is worse than none,
  because it gets shipped.
- **One template with the function name swapped.** The SDKs differ in shape, not just in
  name.

## Consequences

- The JavaScript parse test needs Node in CI. The frontend job already has it.
- Platform files from an instance directory are configuration, controlled by whoever
  operates the instance. They are not requester input.

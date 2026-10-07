# Governance profiles are versioned and edited in the app

Status: accepted

Overturns the governance wizard's download-only stance and the PRD's authoring row, where
the data team "commits the YAML, and `git log` is the history."

Download-only was right for an app with no auth: any write path would have been an
unauthenticated write into the repo. ADR 0004 adds auth. And an organization running its
own instance needs to fix a rule it got wrong now, mid-session, not after a commit and a
redeploy.

## The decision

- **An admin edits the governance profile on an admin page in the app.** Only the admin
  role can save.
- **Every save is a new profile version**, numbered, with a digest of its contents, and
  written to the audit log with who saved it. Old versions are kept. Exactly one version is
  active.
- **Every request is stamped with the profile version that judged it.** A request's
  verdict can always be read against the rules in force at the time.
- **Drift is reported, never fixed.** After a save, the engine, with no model, re-checks
  every approved and published event against the new version and lists the ones that no
  longer pass. Approved events are never changed automatically. A fix goes through rename
  or supersede, with a human confirming. The export shows drift.
- **Choices stay curated.** A save picks from conventions, categories, and PII tokens the
  app offers. No free-form naming regex, ever. A new convention is added in code, as a new
  curated identifier.

The seam between enforcing and authoring holds. Authoring is still a separate, deliberate
act on a separate screen. It now leaves an audit entry instead of a commit.

## Considered and rejected

- **Keep download-only and redeploy on every change.** Too slow to fix a mistake while
  someone is mid-request, and a redeploy is downtime (ADR 0004).
- **Fixing drifted events automatically.** The anti-scope rules out auto-fix and
  auto-amend. A rule change that silently renamed published events would break every
  instrumented call that uses the old name.
- **Writing the profile back to the repo, or opening a PR.** Still killed. A save writes to
  the instance's database, never to git.

## Consequences

- On an instance, the audit log is the profile's history, not `git log`. The repo still
  ships templates and `governance/active.yaml`, which seed an instance's first profile
  version.
- The `version` field inside a profile file is a format version, not a profile version.
  The two must not be conflated in code or copy.
- A dispute (`rule_disputed`) already records the active profile's name and digest. The
  profile version joins them.

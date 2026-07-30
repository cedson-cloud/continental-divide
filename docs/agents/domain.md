# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root
- **`docs/adr/`** — read the ADRs that touch the area you're about to work in

If either doesn't exist, **proceed silently**. Don't flag its absence; don't suggest creating it upfront. The `/domain-modeling` skill creates them lazily, when a term or a decision actually gets resolved.

## File structure

This is a single-context repo:

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-append-only-audit-log.md
│   └── 0002-deterministic-rules-engine.md
├── backend/
└── frontend/
```

## Use the glossary's vocabulary

When your output names a domain concept — an issue title, a refactor proposal, a hypothesis, a test name — use the term as `CONTEXT.md` defines it. Don't drift to synonyms the glossary avoids.

If the concept you need isn't in the glossary yet, that's a signal. Either you're inventing language the project doesn't use, in which case reconsider, or there's a real gap, in which case note it for `/domain-modeling`.

## Flag ADR conflicts

If your output contradicts an existing ADR, say so rather than silently overriding it:

> _Contradicts ADR-0007 (append-only audit log) — but worth reopening because…_

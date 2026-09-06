# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root.
- `docs/adr/`: read ADRs that touch the area you're about to work in.

If these files don't exist, proceed silently. The `/domain-modeling` skill creates them lazily when terms or decisions are actually resolved.

## File structure

Single-context repository:

```
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept, use the term defined in `CONTEXT.md`. If a needed concept is absent, reconsider whether the project already has a preferred term, or note the gap for `/domain-modeling`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface that explicitly rather than silently overriding it.

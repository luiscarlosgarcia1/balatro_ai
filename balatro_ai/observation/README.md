# Observation Guardrails

This folder owns the typed observation boundary for the app. Its job is to turn the live exporter handoff into the canonical in-process observation model and keep that model easy to understand, safe to extend, and hard to accidentally regress.

This README captures lessons from both local observer PRDs. When the older JSON-first observer PRD and the later typed live observer refactor PRD disagree, the refactor PRD wins.

## Priority Rule

- The typed live observer refactor is the authoritative architectural direction for this folder.
- Earlier JSON-first guidance only matters when it still agrees with the typed live observer direction.
- Do not preserve or reintroduce older patterns just because they existed earlier in the project.

## Core Rules

- Observation is live-first and typed-first.
- JSON is allowed only at the Lua-to-Python ingress boundary.
- Inside Python, observation should flow as typed objects, not dict-shaped payloads.
- Keep one canonical in-process observation contract instead of parallel typed and dict contracts.
- Keep this package focused on observation concerns only.
- Do not let runtime orchestration, policy logic, or validation rules leak into this folder.
- Prefer clean deletion of obsolete compatibility layers, fallbacks, and bridges over preserving them by habit.
- Use generic product-level naming for public observation concepts rather than legacy source-specific naming.
- Favor the simplest architecture that keeps the real boundary clear.

## Data Modeling Rules

- `GameObservation` is the canonical in-process observation contract.
- Treat `GameObservation` as a stable top-level boundary, not as a catch-all bucket.
- When a concept is distinct, give it a typed sub-object or supporting model instead of stuffing more loose fields onto `GameObservation`.
- Add fields only when they provide real boundary value, actionability, or necessary fidelity.
- Avoid fields that are speculative, convenience-only, or kept around "just in case."
- Avoid redundant fields when the value can already be derived cheaply and clearly from existing typed data.
- Avoid reconstructed fields unless a concrete consumer needs them and the reconstruction is part of the intended contract.
- Prefer purposeful, typed shapes over generic blobs, raw payload islands, or "misc" containers.
- If a new concern feels awkward to place, that is a sign to refine the model boundary rather than dump it into the nearest object.

## Code Organization Rules

- Group code by purpose and subdomain, not by accident of history.
- Split mixed-responsibility modules before they become the new knot.
- Prefer smaller focused modules and folders when they make boundaries clearer.
- Use the parser subpackage and other purpose-based folders to keep orchestration separate from subdomain parsing.
- Treat roughly 500 lines as a soft limit for new or heavily rewritten files.
- Exceed that limit only on purpose and only when it is clearly the simpler option.
- Prefer deletion over relocation for legacy helpers that no longer justify their existence.
- Do not keep compatibility shims unless a real blocker forces one.

## Testing And Debugging Rules

- Tests should protect surviving public and boundary behavior.
- Do not write tests that mainly freeze helper layout, transitional structure, or old architecture.
- Prefer a small set of strong boundary tests over broad structure-locking coverage.
- Keep smoke tests focused on typed observation acquisition, observation service behavior, public imports, and other surviving contracts.
- Debugging and inspection paths should reinforce the typed observation model.
- Do not revive Python-side JSON serialization or dict-first debug flows as the default inspection path.

## Do / Don't

### Do

- Parse live JSON into typed observation objects as early as possible.
- Add a new typed model when a new concept has its own lifecycle or meaning.
- Remove dead fallback logic when the supported path is clear.
- Refactor oversized modules into smaller purpose-based pieces.
- Keep public observation names generic and current.

### Don't

- Do not turn typed observations back into dicts for normal Python flow.
- Do not add save-first, source-specific, or compatibility-first naming back into the public surface.
- Do not use `GameObservation` as a dumping ground for unrelated leftovers.
- Do not add raw payload passthrough fields when a typed shape is the real need.
- Do not keep old bridges, exporters, or adapters unless a concrete current dependency requires them.
- Do not preserve a behavior or field only because an earlier PRD or deleted code path used it.

## Before You Add Something New

Ask these questions first:

1. Does this belong in observation at all, or is it really a runtime, policy, or validator concern?
2. Is this needed at the typed observation boundary, or is it only convenient internally somewhere else?
3. Should this be a new typed sub-object instead of another loose field on `GameObservation`?
4. Is the value genuinely part of the contract, or can it be derived from existing typed data?
5. Am I making the supported live-first typed path clearer, or am I reintroducing an older parallel shape?
6. Am I simplifying the package, or quietly rebuilding the knot that earlier refactors removed?

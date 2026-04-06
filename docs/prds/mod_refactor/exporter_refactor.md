# Refactor Plan: Responsibility-First Live State Exporter Cleanup

## Problem Statement

The live state exporter mod has grown into a shape that is harder to change safely than it needs to be. Responsibilities are mixed across modules, similar helper logic is repeated in multiple places, and some modules blend orchestration, data extraction, and output shaping in the same file. That makes routine edits feel risky, especially when a change to one game area quietly depends on logic duplicated somewhere else.

The goal of this refactor is to make the exporter easier to reason about and safer to modify by reorganizing it around responsibility boundaries instead of game-area buckets. The refactor should reduce duplication, shrink convoluted files, keep module names short and readable, and preserve the JSON contract that the Python side consumes.

## Solution

Rebuild the exporter as a responsibility-first pipeline with clear seams:

- a small runtime entry layer that installs hooks and triggers exports
- a small coordinator that assembles one raw observation from focused modules
- dedicated phase logic for interaction-state decisions
- shared low-level value helpers
- shared entity readers for cards, jokers, consumables, packs, vouchers, and selection references
- focused collectors for run metadata, hand/deck state, shop state, and pack state
- one output-schema layer that owns null sentinels, array tagging, and final shell shaping
- one writer/export layer that handles serialization, signatures, throttling, and file output

The end state should preserve the exported JSON shape and Python-facing behavior while making internals easier to navigate, split, and extend.

## Commits

1. Add a characterization-plan comment block or doc note that freezes the refactor goals.
   Capture the non-negotiables before moving code: stable exported JSON, responsibility-first layout, aggressive but concise renaming, and a soft line cap near 300 lines for touched modules where practical.

2. Introduce the new module layout without changing runtime behavior.
   Create the responsibility-first folders and placeholder modules so the target architecture exists before logic moves. Keep the current exporter behavior intact.

3. Extract shared low-level value helpers into a dedicated utility module.
   Move repeated primitives such as table guards, first-defined lookup, numeric coercion, lowercasing, and simple boolean selection into one focused utility module. Update one existing module to use it without changing output.

4. Finish replacing duplicated low-level helpers across the exporter.
   Update the remaining modules to use the shared value helpers and remove local copies. Keep this commit narrowly focused on deduplication with no behavior changes.

5. Extract shared entity readers for cards, jokers, consumables, packs, vouchers, and selection references.
   Centralize the repeated rules for reading instance ids, keys, editions, enhancements, sticker state, costs, and selected references. Keep the readers small and purpose-specific so they do not become a new dumping ground.

6. Rebuild the current hand/deck/selection logic on top of shared entity readers.
   Replace the old zone-oriented logic with a responsibility-focused collector for visible hand cards, selected references, jokers, consumables, and canonical deck ordering. Preserve output order and filtering rules exactly.

7. Split shop-state collection away from pack-state collection.
   Create a focused shop collector for UI-visible shop rows and a separate pack collector for opened-pack rewards and skip metadata. Reuse the shared entity readers so shop and pack stop re-implementing the same classification logic.

8. Rework run-metadata collection into a focused state collector.
   Move blind rows, vouchers, tags, slot limits, hand-size limits, run-info hands, and interest into a clearly named collector that owns only run-level metadata and counters.

9. Keep phase inference as its own first-class module and trim it down to decisions only.
   Refactor the phase module so it owns interaction-phase inference and blind-key derivation, while depending on shared helpers instead of carrying its own duplicate support code.

10. Introduce a dedicated raw-state coordinator and move assembly logic out of the current all-in-one module.
   The coordinator should read global state, call the phase module, call the focused collectors, and assemble one raw exporter payload with plain Lua `nil` values where fields are absent.

11. Extract output shaping into its own schema module.
   Move array tagging, null sentinel handling, required/default coercion, and final shell shaping into one module that owns the exported schema boundary. Keep the coordinator free of output-format policy.

12. Shrink the current top-level snapshot module into a thin facade.
   Retain the public entry points expected by the rest of the mod, but have the module delegate to the new coordinator and schema builder instead of owning detailed business logic.

13. Clean up the writer/export module boundaries.
   Keep serialization, signature generation, throttling, and snapshot writes together, but trim naming and local structure so the write path reads as one clear responsibility rather than a mixed helper bag.

14. Update runtime/module loading so the new layout is the canonical path.
   Adjust the runtime entry layer and any shared loader helpers so the mod loads the refactored modules cleanly from the new structure. Keep the installed hooks and export timing behavior the same.

15. Rename remaining legacy module concepts to match responsibility-first ownership.
   Remove vague names such as broad "core" or area-heavy names when they no longer match reality. Prefer short, readable responsibility names over abbreviations.

16. Do a final pass to enforce the soft line cap and remove transitional glue.
   Split any touched module that still feels overloaded, delete compatibility-only wrappers that are no longer needed, and make sure the final layout feels intentional rather than half-migrated.

17. Run the existing exporter and smoke coverage as a regression check after the structural move.
   Use the current Lua exporter tests and Python observation smoke tests as the first contract guard. Add new characterization tests only where the refactor exposes an unprotected behavior seam that feels risky.

## Decision Document

- The exporter will be organized around responsibility boundaries, not around broad game-area buckets.
- Subdirectories are allowed and preferred where they clarify ownership.
- The top-level snapshot entry should become a thin coordinator-facing facade, not a business-logic hub.
- Interaction-phase inference remains a first-class responsibility with its own dedicated module.
- Shop collection and pack collection should be separate responsibilities, with shared lower-level readers beneath them.
- Output shaping is a distinct boundary from raw state collection.
- Shared helpers are allowed, but they must stay focused; do not replace duplication with a single vague dumping-ground module.
- Names should be short, readable, and explicit. Avoid abbreviations and vague catch-all names.
- A soft line cap of roughly 300 lines should guide touched modules where practical, without forcing unnatural splits.
- Internal behavior may be reorganized aggressively, but the exported JSON contract consumed by Python should remain stable.
- Runtime wiring may be updated if needed to support the cleaner structure, as long as the mod still works.

## Testing Decisions

- A good test should validate externally visible exporter behavior, not internal module layout.
- The existing exporter tests already provide useful contract coverage for phase inference, collection behavior, output shaping, writer behavior, and runtime hookup.
- The existing Python smoke tests provide downstream contract coverage for the live-state JSON boundary.
- Testing is not the main goal of this refactor, so the plan is to lean on existing coverage first and add new tests only when a refactor seam is not adequately protected.
- If new tests are added, they should be characterization-style tests around exported data and runtime behavior rather than tests that lock in internal helper structure.

## Out of Scope

- Intentional changes to the Python-facing live-state JSON schema
- Refactoring unrelated mods or unrelated Python runtime areas
- Performance tuning that is not directly required by the cleanup
- Broad test-suite redesign outside the exporter contract surfaces
- Cosmetic renaming that does not improve ownership or change safety

## Further Notes

- The main risk is accidentally changing exported semantics while improving structure. Every step should keep the codebase working and preserve output shape.
- The safest migration style is "extract, redirect, then delete" rather than rewriting everything in one pass.
- If a responsibility split starts producing tiny files with no real ownership, collapse them back into the nearest coherent module. The goal is clarity, not maximal fragmentation.

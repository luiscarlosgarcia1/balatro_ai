# Plan: Responsibility-First Live State Exporter Cleanup

> Source PRD: `docs/issues/live_state_exporter_responsibility_refactor.md`

## Durable decisions

- The exported JSON contract consumed by Python stays stable throughout this refactor.
- The mod should be organized around responsibility boundaries rather than game-area buckets.
- Subdirectories are allowed and preferred when they make ownership clearer.
- `phase` logic remains a first-class boundary instead of being absorbed into a grab-bag collector.
- Shop and pack collection should be separate responsibilities with shared lower-level readers underneath.
- Output shaping is a distinct boundary from raw state extraction.
- Shared helpers are allowed only when they stay focused; do not replace duplication with a vague dumping-ground module.
- Module names should be short, readable, and explicit, without abbreviations.
- Touched modules should aim for a soft line cap around 300 lines where practical.
- Runtime wiring may change if needed, but the mod still needs to function the same way at the boundary.
- Prefer "extract, redirect, then delete" over broad rewrites in place.

## Ordered issue sequence

No pre-existing issue docs were found for this refactor beyond the source design doc, so the plan is sliced directly from `docs/issues/live_state_exporter_responsibility_refactor.md`.

1. `Slice A: Layout reset and shared low-level helpers`
   Why now: it creates the new responsibility-first skeleton and removes the most obvious repeated support code before deeper logic moves start.
   Depends on: source PRD only.

2. `Slice B: Shared entity readers and owned-zone migration`
   Why now: cards, jokers, consumables, deck ordering, and selection rules contain the densest duplicated logic and benefit immediately from the shared helper layer.
   Depends on: Slice A.

3. `Slice C: Run-state collectors, phase cleanup, and raw coordinator`
   Why now: once the shared readers exist, the remaining state and phase logic can be consolidated into a cleaner raw-observation pipeline.
   Depends on: Slices A-B.

4. `Slice D: Schema boundary, thin snapshot facade, and runtime rewiring`
   Why now: after raw-state assembly is stable, output shaping and module wiring can be split cleanly without fighting moving collector logic.
   Depends on: Slices A-C.

5. `Slice E: Naming cleanup, line-cap enforcement, and regression hardening`
   Why now: the last phase should mostly be cleanup, final renames, small structural trims, and verification after the new architecture is already in place.
   Depends on: Slices A-D.

## Phase 1: Layout Reset And Shared Helpers

**Issues**: `Slice A: Layout reset and shared low-level helpers`

### Goal

Create the responsibility-first module skeleton and centralize the repeated low-level support functions that are currently copied across exporter files.

### Why this phase now

This phase reduces immediate duplication and gives later moves a stable destination, which lowers the risk of the refactor collapsing into another round of ad hoc file splitting.

### Implementation notes

- Introduce the new folder structure under `mods/live_state_exporter/` and keep it lean and responsibility-based.
- Extract shared primitives such as table guards, first-defined lookup, numeric coercion, lowercasing, and boolean selection into a focused utility module.
- Update module-loading helpers as needed so the new layout can coexist with the current runtime path while the refactor is in flight.
- Keep behavior unchanged; this phase is about structure and deduped support code, not business-logic redesign.
- Avoid creating a single `helpers` dumping ground; keep the shared module narrow and obvious in scope.

### Acceptance criteria

- [ ] A responsibility-first folder layout exists for the exporter.
- [ ] Repeated low-level value helpers are centralized.
- [ ] Existing modules can load from the new layout without changing exporter output.
- [ ] No new vague catch-all helper module is introduced.

### Read before starting

- Source PRD
- [main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [snap.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/snap.lua)
- [phase.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/phase.lua)
- [tests/exporter/test_main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_main.lua)

## Phase 2: Shared Entity Readers And Owned Zones

**Issues**: `Slice B: Shared entity readers and owned-zone migration`

### Goal

Replace duplicated card/joker/consumable parsing logic with shared entity readers, then rebuild the owned and visible-zone collectors on top of those readers.

### Why this phase now

The repeated entity-shaping rules are the biggest source of unsafe edits today. Consolidating them early pays down the highest duplication before the rest of the pipeline is rearranged.

### Implementation notes

- Extract shared readers for instance ids, keys, editions, enhancements, costs, sticker state, and selected-card references.
- Rework the current hand, deck, joker, consumable, and selected-reference collection to depend on the shared readers rather than local copy-pasted rules.
- Preserve visible order and canonical deck ordering exactly as the current tests expect.
- Rename area-heavy concepts where useful, but prioritize clean ownership over cosmetic churn.
- Keep the new reader layer focused on extracting entities, not on schema null-filling or runtime orchestration.

### Acceptance criteria

- [ ] Shared entity readers own the repeated extraction logic for cards, jokers, consumables, packs, vouchers, and selection references.
- [ ] Hand, deck, joker, consumable, and selected-reference export behavior remains unchanged.
- [ ] Canonical deck ordering and UI-order preservation still match current tests.
- [ ] The old duplicated entity-parsing branches are removed from migrated modules.

### Read before starting

- Source PRD
- [zones.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/zones.lua)
- [market.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/market.lua)
- [tests/exporter/test_zones.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_zones.lua)
- [tests/exporter/test_market.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_market.lua)

## Phase 3: Run State, Phase Logic, And Raw Coordination

**Issues**: `Slice C: Run-state collectors, phase cleanup, and raw coordinator`

### Goal

Separate run-level state collection and interaction-phase decisions from the monolithic snapshot assembly path, then introduce a dedicated raw-state coordinator.

### Why this phase now

Once entity readers and owned zones are stable, the remaining architectural knot is the way phase decisions, run metadata, and raw payload assembly are mixed together. This phase untangles that seam directly.

### Implementation notes

- Refactor run-level collectors for blinds, vouchers, tags, slot limits, hand size, run info, and interest into a focused state collector.
- Keep phase inference and blind-key derivation as their own decision module while moving them onto shared helper code.
- Introduce a raw coordinator that reads game state, calls the phase module, calls the collectors, and returns a plain Lua payload with `nil` for missing fields.
- Reduce the amount of assembly logic still living in the current snapshot module.
- Preserve current phase behavior exactly, especially `blind_select`, `shop`, `pack_reward`, and `play_hand`.

### Acceptance criteria

- [ ] Run-level metadata is collected through a clearly named responsibility-focused module.
- [ ] Phase inference remains isolated and behaviorally unchanged.
- [ ] A dedicated raw coordinator assembles the unshaped exporter payload.
- [ ] The existing snapshot module no longer owns most raw collection logic.

### Read before starting

- Source PRD
- [core.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/core.lua)
- [phase.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/phase.lua)
- [snap.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/snap.lua)
- [tests/exporter/test_core.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_core.lua)
- [tests/exporter/test_phase.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_phase.lua)

## Phase 4: Schema Boundary And Runtime Wiring

**Issues**: `Slice D: Schema boundary, thin snapshot facade, and runtime rewiring`

### Goal

Move output shaping into a dedicated schema boundary, shrink the snapshot layer into a thin facade, and update runtime wiring so the new structure is the canonical path.

### Why this phase now

This phase is easiest once raw collection has stabilized. At that point, null handling, array tagging, shell defaults, and runtime loading can be split out without repeatedly revisiting collector code.

### Implementation notes

- Extract array tagging, null sentinels, required/default shaping, and final shell construction into a dedicated schema module.
- Turn the snapshot module into a thin public facade that delegates to raw coordination and schema shaping.
- Update `main.lua` and any loader helpers so the refactored structure is the main runtime path, not a sidecar.
- Keep the writer module focused on serialization, signatures, dedup, timing, and file output.
- Preserve the live boundary exactly: same path, same write behavior, same externally visible payload shape.

### Acceptance criteria

- [ ] Output shaping lives behind a distinct schema boundary.
- [ ] The snapshot module is a thin facade rather than a business-logic hub.
- [ ] Runtime wiring uses the new structure without changing the mod's observable behavior.
- [ ] Serialization, signature, and write behavior still pass existing contract tests.

### Read before starting

- Source PRD
- [snap.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/snap.lua)
- [out.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/out.lua)
- [main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [tests/exporter/test_snap.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_snap.lua)
- [tests/exporter/test_out.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter/test_out.lua)

## Phase 5: Final Cleanup And Hardening

**Issues**: `Slice E: Naming cleanup, line-cap enforcement, and regression hardening`

### Goal

Finish the refactor with the remaining aggressive renames, trim any overloaded modules that still exceed the soft cap, and verify that the exporter remains stable at the Lua and Python boundaries.

### Why this phase now

The final cleanup should happen after the new structure is already real, so names and file boundaries can be adjusted based on the actual architecture rather than guessed up front.

### Implementation notes

- Rename remaining legacy concepts such as vague area-heavy or catch-all module names when the new responsibilities are already clear.
- Remove transitional compatibility wrappers or duplicate code that only existed to support the migration.
- Split any touched module that still feels overloaded, but avoid tiny files with no real ownership.
- Run the existing exporter tests and the downstream Python smoke tests that defend the live-state contract.
- Add new tests only if the refactor exposed an unprotected behavioral seam that feels genuinely risky.

### Acceptance criteria

- [ ] Remaining legacy names are replaced with concise responsibility-based names.
- [ ] Touched modules are near the soft size target unless a larger file is clearly more coherent.
- [ ] Transitional glue introduced during migration is removed.
- [ ] Exporter and downstream contract verification still pass.

### Read before starting

- Source PRD
- All prior phase sections of this plan
- [tests/exporter/test_*.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/exporter)
- [tests/smoke/observation/test_live_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/smoke/observation/test_live_parser.py)
- [tests/smoke/observation/test_observer_service.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/smoke/observation/test_observer_service.py)

## Resume instructions

To implement a phase in a fresh chat, read this plan, the source PRD, and the target phase section first. Start with the earliest incomplete phase unless the repo already shows that a dependency has been satisfied.

# Plan: Balatro Live Exporter Mod

> Source PRD: `docs/prds/mod_prd/mod_prd.md`

## Durable decisions

- Plan scope is limited to `mods/`.
- The exported contract must conform to [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py).
- `models.py` field names are the contract authority unless a real game name must be preserved and `models.py` does not define a conflicting public name.
- The mod is observation-only in v1: no screenshots, pixel reads, or executor-ready UI geometry.
- Optional values should be emitted as `null`, not omitted.
- Collections should be present with empty arrays when empty.
- `shop_items` should use one object per item with `card`, `joker`, `consumable`, `voucher`, and `pack`, where exactly one is populated and the rest are `null`.
- `cards_in_deck` ordering should be `spades`, `hearts`, `clubs`, `diamonds`, then `ace` through `king`.
- Visible UI collections should otherwise follow UI order: top to bottom, then left to right.
- The first implementation should focus on the throttled live export path at roughly `0.05` seconds.
- No repo-side print/debug output path is part of this plan.
- Modules should be grouped by shared purpose, not split into one file per helper.
- Internal function names should stay concise but still be immediately readable.
- No synthetic fallback IDs: if `models.py` expects `instance_id`, the mod should read the real game ID or treat missing identity as a bug to investigate.
- The last phase is intentionally `Follow ups`, since that work is expected to evolve.

## Ordered issue sequence

No pre-existing issue docs were found for this PRD, so the work is sliced directly from the PRD into implementation units.

1. `Slice A: Exporter skeleton, contract scaffolding, and write loop`
   Why now: It establishes the mod shape, shared helpers, throttled write behavior, and the schema discipline every later collector depends on.
   Depends on: Source PRD only.

2. `Slice B: Core run-state collectors and deterministic ordering`
   Why now: It delivers the smallest end-to-end useful snapshot for `GameObservation` and absorbs the simpler non-instance-heavy collections before the denser identity zones arrive.
   Depends on: Slice A.

3. `Slice C: Identity-rich zone collectors`
   Why now: Cards, jokers, consumables, and selections are the backbone of observation completeness and need shared identity/ordering rules already in place.
   Depends on: Slices A-B.

4. `Slice D: Shop and pack interaction collectors`
   Why now: These are phase-heavy and schema-sensitive, especially around one-of unions and UI ordering, so they should land after the core collection patterns are stable.
   Depends on: Slices A-C.

5. `Slice E: Integration hardening, partial-state guarantees, and mod-facing verification`
   Why now: This phase turns the assembled collectors into a reliable exporter that behaves correctly across phases and matches the PRD’s nullability, completeness, and runtime expectations.
   Depends on: Slices A-D.

6. `Slice F: Follow ups`
   Why now: These are intentionally deferred and living items, not part of the first mod implementation path.
   Depends on: Stable mod contract from Slices A-E.

## Phase 1: Exporter Foundation

**Issues**: `Slice A: Exporter skeleton, contract scaffolding, and write loop`

### Goal

Create the clean-slate mod structure with a thin entrypoint, shared helpers, deterministic JSON shaping rules, signature/dedup support, and the throttled live export path.

### Why this phase now

This phase prevents the rebuild from collapsing into another giant file and gives every later collector a stable home, stable schema rules, and stable write behavior.

### Implementation notes

- Build the mod around deep modules, not a broad `main.lua`.
- Group files by purpose so cooperating reader/shaping or output/write logic can live together when that keeps the structure clearer.
- Keep the first payload shell aligned with the `GameObservation` top-level field set from [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py).
- Establish null-not-omitted behavior and empty-array behavior here so collectors inherit it rather than reinvent it.
- Do not add repo-side print routing, debug file commands, or one-shot export behavior in this phase.
- Prefer readable helper names over ultra-short abbreviations, even for internal module APIs.
- Keep file sizes under the soft cap by separating bootstrap, helpers, write control, and schema shaping before collector work begins.

### Acceptance criteria

- [ ] The mod has a clean multi-file structure inside `mods/`.
- [ ] A valid snapshot shell can be emitted with `models.py`-aligned top-level fields.
- [ ] Throttled export behavior runs at roughly `0.05` seconds.
- [ ] Signature/dedup logic exists and suppresses redundant writes.
- [ ] Module boundaries are grouped by shared purpose rather than one-file-per-function splitting.
- [ ] Internal helper names remain concise but understandable at a glance.

### Read before starting

- Source PRD
- [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py)
- Any remaining mod scaffold files under `mods/live_state_exporter/`

## Phase 2: Core Run State

**Issues**: `Slice B: Core run-state collectors and deterministic ordering`

### Goal

Export the stable run-state backbone needed across all major phases: scalar run state, score, blinds, run info, vouchers, tags, slot counts, phase inference, and canonical ordering rules.

### Why this phase now

This gives the exporter a meaningful end-to-end observation core before the more cluttered object zones and shop/pack unions are added.

### Implementation notes

- Cover `state_id`, `dollars`, `hands_left`, `discards_left`, `score`, `deck_key`, `stake_id`, `blind_key`, `ante`, `round`, `blinds`, `run_info`, `interest`, `reroll_cost`, `hand_size`, `joker_slots`, `consumable_slots`, `vouchers`, and `tags`.
- Keep phase inference isolated and keyed to the PRD’s required phases: `blind_select`, `shop`, `pack_reward`, `play_hand`.
- Apply `RUN_INFO_HAND_ORDER` from [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py) at export time.
- Add focused tests for phase inference, ordering helpers, and core payload shaping.

### Acceptance criteria

- [ ] Core scalar fields needed by `GameObservation` are exported with the correct names.
- [ ] `blinds`, `score`, `interest`, `run_info`, `vouchers`, and `tags` are exported in canonical shape.
- [ ] Required phase inference is implemented for the main decision loop.
- [ ] Ordering rules for non-UI core structures are deterministic.

### Read before starting

- Source PRD
- [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py)
- Phase 1 section of this plan

## Phase 3: Identity-Rich Zones

**Issues**: `Slice C: Identity-rich zone collectors`

### Goal

Export the main identity-bearing zones needed to populate `GameObservation`: `cards_in_hand`, `cards_in_deck`, `jokers`, `consumables`, and `selected_cards`.

### Why this phase now

These zones carry most of the object identity and nullability constraints in the contract, and they benefit from the stable helpers and phase/state backbone already established.

### Implementation notes

- Use real in-game IDs wherever `models.py` expects `instance_id`.
- Do not introduce synthetic identity fallback.
- Keep deck ordering at suit then rank using the PRD’s explicit suit/rank order.
- For `selected_cards.zone`, preserve in-game naming instead of inventing prettier aliases.
- Keep parser-only derivations, such as deriving suit or rank from `card_key`, out of the mod payload.

### Acceptance criteria

- [ ] `cards_in_hand`, `cards_in_deck`, `jokers`, `consumables`, and `selected_cards` are exported in `models.py`-aligned shape.
- [ ] Identity fields are present where required and not synthesized.
- [ ] `cards_in_deck` is exported in the specified canonical order.
- [ ] Empty zone collections emit empty arrays instead of disappearing.

### Read before starting

- Source PRD
- [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py)
- Phase 2 section of this plan

## Phase 4: Shop And Pack Phases

**Issues**: `Slice D: Shop and pack interaction collectors`

### Goal

Export `shop_items` and `pack_contents` in the exact canonical shapes needed for the most phase-sensitive decision points in the run.

### Why this phase now

This is the densest schema work in the PRD and is easier to implement correctly after the exporter already has proven identity, ordering, and nullability behavior in simpler zones.

### Implementation notes

- `shop_items` must emit one object per item with `card`, `joker`, `consumable`, `voucher`, and `pack`, with exactly one populated and the others `null`.
- `pack_contents` must align with `ObservedPackContents`, including `pack`, `choices_remaining`, `skip_available`, and `items`.
- Preserve UI order for visible shop and pack collections: top to bottom, then left to right.
- Keep collector logic separate from schema-wrapping logic so the union encoding does not leak into every collector.

### Acceptance criteria

- [ ] `shop_items` matches the `ObservedShopItem` wrapper shape.
- [ ] `pack_contents` matches the `ObservedPackContents` shape.
- [ ] Visible shop and pack items export in UI order.
- [ ] `shop` and `pack_reward` phases are observation-complete enough to satisfy the PRD.

### Read before starting

- Source PRD
- [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py)
- Phase 3 section of this plan

## Phase 5: Hardening And Finish Line

**Issues**: `Slice E: Integration hardening, partial-state guarantees, and mod-facing verification`

### Goal

Make the exporter reliable across the main gameplay loop by enforcing the final schema guarantees, validating partial/inactive-state behavior, and tightening the mod-facing runtime workflow.

### Why this phase now

Once all major collectors exist, this phase turns them into a dependable contract rather than a loose collection of field emitters.

### Implementation notes

- Validate `null` versus empty-array behavior against every optional or inactive section.
- Confirm the main phases all export a complete payload without missing required `models.py` fields.
- Add or tighten focused pure-logic tests where runtime issues exposed gaps in shaping, ordering, or dedup.
- Keep verification scoped to the mod side and update mod-local docs in `mods/` only if needed to keep the new workflow usable.

### Acceptance criteria

- [ ] The exporter survives partial or missing game structures without crashing.
- [ ] Optional fields are `null` rather than omitted.
- [ ] Collection fields remain present with empty arrays when appropriate.
- [ ] The main decision loop phases produce stable, usable snapshots.
- [ ] The mod remains split into purposeful files under the soft size cap.

### Read before starting

- Source PRD
- [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py)
- All prior phase sections of this plan

## Phase 6: Follow ups

**Issues**: `Slice F: Follow ups`

### Goal

Track the intentionally deferred, living work that should only happen after the mod contract is stable.

### Why this phase now

These items are not part of the first mod implementation path and should stay flexible.

### Implementation notes

- Python parser migration to the new contract
- `GameObservation` review and cleanup
- UI and actionability investigation
- real-session runtime validation capture set
- policy and validator follow-up
- documentation refresh outside the immediate mod scope if still needed

### Acceptance criteria

- [ ] Deferred items are clearly separated from the first mod implementation path.
- [ ] Future chats can pick up follow-up work without reopening scope decisions already settled in the PRD.

### Read before starting

- Source PRD
- Stable exporter implementation from earlier phases

## Resume instructions

To implement a phase in a fresh chat, read the source PRD, this plan, and the target phase section first. Start with the earliest incomplete phase unless there is a clear dependency already satisfied outside the repo.

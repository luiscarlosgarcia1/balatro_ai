# Plan: JSON-First Observer Schema

> Source PRD: [docs/observer_json_first_schema_prd.md](c:/Users/luiga/OneDrive/Documentos/balatro_ai/docs/observer_json_first_schema_prd.md)

## Summary

- Rebuild the observer contract around the canonical JSON-first schema and remove legacy contract code as replacements land.
- Treat parser, decoder, exporter-mod, and serializer work as cleanup opportunities: when we touch old logic, we should actively look for dead paths, duplicate shaping, and display-oriented leftovers that can be safely deleted.
- Optimize for a lightweight observation stack so the AI gets a compact, stable, machine-first contract with minimal extra transformation cost.

## Durable Decisions

- The canonical ordered JSON contract is the only public observer contract after this work.
- No long-term compatibility layer for the old schema; transitional code is acceptable only within the phase that replaces it.
- Every parser/decoder/exporter touchpoint should include a lightweight cleanup pass for safely removable legacy code in that area.
- Prefer simpler data flow over adapters: exporter gathers raw state, parser normalizes it, serializer enforces canonical order/shape, pretty output derives from that serializer.
- Refit the live exporter and signature coverage immediately after the serializer baseline so later slices spend less effort translating legacy live payloads in Python.
- Keep shared infrastructure that still serves the new design: live/save acquisition, save decoding, capture utilities, and signature testing.
- Efficiency matters as a product requirement: avoid duplicate representations, unnecessary reformatting, repeated normalization passes, and stale helper layers that only supported the old contract.
- The save fallback may remain less complete than the live exporter, but it must still emit the canonical top-level shape.

## Ordered Issue Sequence

1. `#30`  
   Why now: creates the canonical serializer boundary and gives the first safe place to delete old schema/formatter logic.  
   Depends on: none.

2. `#31`  
   Why now: moves the live path closer to canonical field names before the deeper schema slices land, so later issues delete live-side compatibility instead of building on it.  
   Depends on: `#30`.

3. `#29`  
   Why now: replaces the scalar backbone and removes old scalar naming and formatting assumptions early.  
   Depends on: `#30`, `#31`.

4. `#28`  
   Why now: replaces the old owned-object structure and settles voucher separation before market refits.  
   Depends on: `#30`, `#31`.

5. `#27`  
   Why now: completes blind/tag normalization using the same compact array conventions.  
   Depends on: `#30`, `#31`, benefits from `#28`.

6. `#26`  
   Why now: should land after voucher separation so the old market split can be removed cleanly.  
   Depends on: `#30`, `#31`, `#28`.

7. `#25`  
   Why now: replaces the current hand-card summary path with the final card-zone contract.  
   Depends on: `#30`.

8. `#24`  
   Why now: finishes the modal/pack side after the final market and card object conventions exist.  
   Depends on: `#30`, `#26`, `#25`.

## Important Interface Changes

- Replace the legacy observation model in [balatro_ai/models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py) with a canonical-schema-oriented model or serializer boundary; legacy fields that exist only for the old contract should be removed.
- Refactor [balatro_ai/observation/live_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/observation/live_parser.py), [balatro_ai/observation/save_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/observation/save_parser.py), and the exporter mod in [mods/live_state_exporter/main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua) to normalize directly into canonical output semantics instead of feeding the current mixed human/debug model.
- Replace the old formatter path in [obs_test.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/obs_test.py) so debug output is derived from canonical JSON, then delete the old formatting assumptions and outdated contract assertions in [tests/test_live_observer_contract.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/test_live_observer_contract.py).

## Cleanup And Efficiency Rules

- Any time a phase edits a parser, decoder, exporter helper, or formatter, inspect adjacent logic for dead branches, duplicated field shaping, stale aliases, and double-normalization steps.
- Delete old code in the same phase when the canonical replacement is already covered by tests; do not leave "maybe useful later" helpers behind.
- Prefer one-pass extraction/normalization over collecting the same concept into multiple intermediate shapes.
- Remove duplicate top-level concepts such as parallel market lists or separate human-readable copies once canonical fields exist.
- Keep helper modules only if they deepen the architecture meaningfully; remove shallow pass-through wrappers that no longer reduce complexity.
- Extend signature and contract tests before deleting behavior so cleanup stays safe and intentional.

## Phase 1: Contract Baseline And First Cleanup

**Issues**: `#30`

### Goal

Create the canonical serializer boundary and remove the old schema/formatter split.

### Why This Phase Now

It gives the repo one authoritative contract early and creates the first safe place to delete old schema-specific code instead of carrying it through every later slice.

### Implementation Notes

- Add canonical ordered serialization with the PRD top-level order and array/null rules.
- Rewire debug formatting to render from canonical JSON only.
- Remove legacy formatter-specific schema logic and any serializer helpers that only exist for the old display contract.

### Acceptance Criteria

- [ ] Canonical JSON field order and top-level presence rules are locked by tests.
- [ ] Pretty output comes only from canonical JSON.
- [ ] No separate legacy display schema remains.

### Read Before Starting

- Source PRD
- `#30`
- [obs_test.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/obs_test.py)
- [tests/test_live_observer_contract.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/test_live_observer_contract.py)

## Phase 2: Live Exporter And Signature Refit

**Issues**: `#31`

### Goal

Move the live Lua exporter and signature coverage closer to the canonical observer contract before the deeper schema slices land.

### Why This Phase Now

It removes live-side translation tax early, so later scalar, owned-object, blind, and market slices can spend more effort deleting compatibility and less effort compensating for old live field names.

### Implementation Notes

- Refit the live exporter to emit canonical-oriented field names where the baseline contract already settled the public shape.
- Make `interaction_phase` the main gameplay phase field for the live path.
- Update signature coverage to use canonical gameplay-relevant fields instead of legacy split names.
- Remove or shrink Python live-path compatibility bridges that only exist because the exporter still emits old field names.
- Keep save fallback less complete if needed; this phase is about the live path first.

### Acceptance Criteria

- [ ] Live exporter phase semantics no longer rely on public `phase`.
- [ ] Signature coverage follows canonical gameplay-relevant fields.
- [ ] Python live-path compatibility bridges are reduced where the live exporter now emits canonical data directly.

### Read Before Starting

- Source PRD
- `#31`
- [mods/live_state_exporter/main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [mods/live_state_exporter/signature.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/signature.lua)

## Phase 3: Scalar Backbone Replacement

**Issues**: `#29`

### Goal

Replace legacy scalar naming and note handling with canonical run-state fields.

### Why This Phase Now

The scalar backbone feeds every later slice and lets us remove old scalar aliases and display-oriented formatting early, before deeper object work starts.

### Implementation Notes

- Add raw-id scalar fields, capacities, counts, score object, and note strings.
- Update exporter signature coverage for the new scalar set.
- Remove superseded scalar aliases, display-oriented formatting, and stale parser branches that only fed the old contract.

### Acceptance Criteria

- [ ] Canonical scalar fields are complete and tested.
- [ ] Obsolete scalar aliases and duplicate scalar shaping are removed.

### Read Before Starting

- Source PRD
- `#29`
- [mods/live_state_exporter/main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [mods/live_state_exporter/signature.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/signature.lua)

## Phase 4: Owned State And Blind/Skip Replacement

**Issues**: `#28`, `#27`

### Goal

Replace old owned-object and blind/tag representations with compact raw-id-first arrays.

### Why This Phase Now

These slices share the same array-of-objects conventions and settle voucher/tag/blind semantics before the shop and pack phases build on them.

### Implementation Notes

- Introduce canonical arrays for owned objects and blind/skip state.
- Remove old split object shapes and duplicated tag/voucher handling.
- Keep vouchers separate from market data and clean up any parser/exporter helpers that still mix them back together.

### Acceptance Criteria

- [ ] Canonical owned/blind arrays are covered by tests.
- [ ] Legacy owned/blind schema remnants are removed.

### Read Before Starting

- Source PRD
- `#28`
- `#27`
- [balatro_ai/observation/live_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/observation/live_parser.py)

## Phase 5: Shop Market Replacement

**Issues**: `#26`

### Goal

Make `shop_items` the only canonical non-voucher market list and remove old market splits.

### Why This Phase Now

Voucher separation is already settled, so the market can be simplified cleanly without reintroducing duplication between shop lists.

### Implementation Notes

- Normalize visible market items into canonical UI-order `shop_items`.
- Add `shop_discounts`.
- Remove old `shop_packs`-style duplication, redundant pack/shop helpers, and any re-sorting logic that exists only for the prior observer shape.

### Acceptance Criteria

- [ ] `shop_items` is the only canonical non-voucher market list.
- [ ] Voucher duplication and obsolete market splits are removed.

### Read Before Starting

- Source PRD
- `#26`
- [mods/live_state_exporter/main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [tests/test_live_observer_contract.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/test_live_observer_contract.py)

## Phase 6: Card Zones And Selection Replacement

**Issues**: `#25`

### Goal

Replace `hand_cards`-style summaries with canonical card zones and lightweight references.

### Why This Phase Now

This phase defines the final shared card object shape and deterministic ordering that the pack-contents phase will reuse.

### Implementation Notes

- Add canonical `cards_in_hand`, `cards_in_deck`, `selected_cards`, and `highlighted_card`.
- Enforce deterministic suit/rank ordering.
- Remove the old card summary contract and any duplicate card-shaping helpers once consumers and tests are switched.

### Acceptance Criteria

- [ ] Canonical card-zone behavior is covered by tests.
- [ ] Legacy hand-card summary schema is removed.

### Read Before Starting

- Source PRD
- `#25`
- [balatro_ai/observation/live_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/observation/live_parser.py)
- [balatro_ai/observation/save_parser.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/observation/save_parser.py)

## Phase 7: Pack Contents And Final Legacy Purge

**Issues**: `#24`

### Goal

Finish pack interaction modeling and remove the last legacy observer contract remnants.

### Why This Phase Now

Pack contents depends on the final market placement and final card object conventions, so it is the cleanest place to do the last transition sweep.

### Implementation Notes

- Add canonical `pack_contents` after `shop_items`.
- Reuse canonical card object shape.
- Do a final cleanup sweep across parsers, decoders, exporter helpers, and tests to remove transitional adapters and any old-contract code left behind.

### Acceptance Criteria

- [ ] `pack_contents` is covered end to end.
- [ ] No legacy observer contract code remains.
- [ ] The touched observation path is lean, with no unnecessary duplicate transforms.

### Read Before Starting

- Source PRD
- `#24`
- [mods/live_state_exporter/main.lua](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/main.lua)
- [tests/test_live_observer_contract.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/tests/test_live_observer_contract.py)

## Test Plan

- Replace old contract assertions with canonical contract tests for exact top-level order, exact `score` shape, normalization, and `[]` vs `null`.
- Keep exporter signature tests, but update them to cover the new gameplay-relevant canonical fields.
- Add representative scenarios for empty collections, shop vouchers, blind-select, UI-ordered market items, pack-open state, deterministic hand/deck ordering, lightweight references, and partial save-fallback payloads.
- For each phase, verify both behavior and cleanup: removed legacy fields/helpers should no longer appear in canonical output or tests.

## Assumptions And Defaults

- No backward compatibility is required for the current legacy observer contract.
- "Throw out old code safely" means removing legacy shaping, stale helpers, and duplicate transforms once canonical coverage exists for that area.
- Cleanup should happen incrementally inside each phase, not as a single up-front delete.
- Efficiency here means both runtime/lightweight output and lower maintenance complexity for future AI-facing changes.

## Resume Instructions

To implement a phase in a fresh chat, read this phase section, the source PRD, and the linked issue docs first. When editing parsers, decoders, exporter helpers, or formatters, include a cleanup pass for safely removable legacy code in the touched area before closing the phase.

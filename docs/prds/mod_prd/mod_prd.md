# Balatro Live Exporter Mod PRD

## Summary

Rebuild the Balatro mod from scratch as a clean, canonical live-state exporter that writes a single `live_state.json` snapshot for the Python side to consume.

This rewrite is intentionally a clean break from the previous mod payload. The new exporter should focus on a stable observation contract, keep files purposeful and modular, and avoid another monolithic `main.lua`.

The PRD scope is limited to the `mods/` folder. Within that scope, the exporter contract must conform to what [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py) asks for. `GameObservation` and the related observation dataclasses are the primary contract reference for exported structure and field naming.

The first usable version should cover the main gameplay decision loop:

- blind selection
- shop
- opened pack reward selection
- in-blind hand play

The mod remains observation-focused in v1. It should not depend on screenshots, pixel reads, or image-based automation.

Implementation sequencing matters:

- prerequisite: old mod-specific exporter tests are removed before rebuild work starts
- once that prerequisite is satisfied, implementation scope remains inside `mods/`

## Problem Statement

The project needs a dependable bridge between Balatro's live game state and the Python runtime. The previous mod approach grew into a large, hard-to-maintain exporter with a broad payload shape and mixed responsibilities. That makes it harder to reason about the code, harder to evolve the schema intentionally, and harder to confidently support downstream parsing and policy logic.

We need a fresh exporter design that:

- exposes the game state the agent actually needs
- avoids dumping raw internals without structure
- preserves stable identity for actionable objects
- keeps the codebase split into small, deep, purposeful files
- keeps file responsibilities obvious at a glance
- stays maintainable for future expansion

## Goals

- Export a canonical JSON snapshot to `AppData/Roaming/Balatro/ai/live_state.json`.
- Provide enough state for the downstream Python side to fully populate `GameObservation` once the parser is updated to the new schema.
- Preserve per-instance identity with `instance_id` wherever the game exposes it.
- Cover the main decision phases: `blind_select`, `shop`, `pack_reward`, and `play_hand`.
- Restrict exported information to player-visible state plus open rule-state.
- Keep the mod architecture highly organized, with a thin entrypoint and domain-focused modules.
- Keep file sizes under a soft cap of about 300-450 lines, and split responsibilities before a file turns into a catch-all module.
- Reintroduce only focused automated tests for stable, pure logic modules inside the mod area.

## Contract Authority

The canonical source of truth for the exported observation contract is [models.py](c:/Users/luiga/OneDrive/Documentos/balatro_ai/balatro_ai/models.py).

Contract rules:

- exporter scope is limited to `mods/`, but exported payload design must conform to the observation structures defined in `models.py`
- field names should match `models.py` exactly where `models.py` already defines the public observation field name
- category and state names should follow naming patterns already used by Balatro game structures whenever the game exposes a real name
- the exporter should not invent aliases, synonyms, or replacement names when an existing game name or `models.py` field name already exists
- `models.py` is the authority for what observation data Python expects the mod to provide
- parser-specific derivation or cleanup should stay on the Python parser side unless `models.py` clearly requires the raw exported field directly
- extra convenience fields should not be added by default; if a non-`models.py` field ever looks worth exporting, it should be treated as a separate explicit decision rather than added casually

## Non-Goals

- No screenshot capture or image-processing support.
- No pixel-based or coordinate-based executor support in v1.
- No attempt to export hidden future information a human player would not normally know.
- No strict compatibility promise with the old exporter payload.
- No attempt to solve Python parser migration inside this mod implementation.

## User Stories

1. As the Python observer, I want a single canonical snapshot file, so that I can read game state without scraping the UI.
2. As the policy layer, I want the current run economy, score, blind, and zone state, so that I can choose a valid next action.
3. As the policy layer, I want shop-visible objects normalized into structured item types, so that I can reason about purchases without raw Lua-specific branching.
4. As the policy layer, I want pack reward choices exported in a consistent structure, so that I can evaluate opened booster decisions.
5. As the policy layer, I want hand, deck, joker, consumable, voucher, and tag state, so that I can plan around the current build.
6. As the runtime, I want stable object identity where available, so that I can refer to specific visible objects across observations.
7. As a maintainer, I want the mod split into small modules by purpose, so that future work does not collapse into one giant file.
8. As a maintainer, I want the serialization and schema logic separated from gameplay collection logic, so that schema changes are easier to review.
9. As a maintainer, I want phase inference isolated from collectors, so that phase behavior can be changed safely.
10. As a maintainer, I want deduplication and write throttling isolated, so that export timing can evolve without touching domain collectors.
11. As a tester, I want pure logic modules with narrow interfaces, so that I can verify behavior without spinning up the full game.
12. As a future executor, I want the observation contract to be stable first, so that any later actionability work can build on a solid base.

## Solution

Create a new mod implementation in `mods/` that exposes a canonical observation snapshot with a clean internal architecture.

The exporter should read the live Balatro state from stable in-memory objects, normalize it into a curated schema, serialize it to JSON, and write one snapshot file for Python. The schema should favor explicit, typed gameplay concepts over raw, sprawling game internals.

The module layout should center on deep responsibilities rather than convenience dumping grounds.

The exported snapshot should be complete enough that, after the downstream parser is updated, Python can populate `GameObservation` from the canonical payload without relying on screenshots or ad hoc gap-filling for core gameplay state.

Recommended structure:

- a thin bootstrap and hook entrypoint
- shared coercion and normalization helpers
- phase inference
- domain collectors for each gameplay area
- schema assembly
- signature and dedup logic
- filesystem output

## Schema Rules

The exporter should emit a deterministic JSON schema that is easy for the parser to consume directly.

Schema rules:

- optional values should be emitted as `null`, not omitted
- collections should always be present when their parent object is present, using empty arrays when there are no items
- nested objects that correspond to optional `models.py` structures may be `null` when inactive or unavailable
- field names should match the corresponding `models.py` observation type field names whenever such a field exists
- where a value must come directly from the game and `models.py` does not define a conflicting public name, preserve the game-facing name rather than inventing a new alias
- the exporter should not push parser-only conveniences into the payload if those conveniences are better handled as Python-side derivation

Union-encoding rules:

- each `shop_items` entry should be one object shaped like `ObservedShopItem`
- that means every shop entry should contain the fields `card`, `joker`, `consumable`, `voucher`, and `pack`
- exactly one of those fields should hold an object and the others should be `null`
- `pack_contents.items` should contain one object per visible item, shaped according to the concrete `ObservedPackItem` member it represents
- the parser is responsible for turning those JSON objects into Python union members, but the exporter is responsible for emitting the concrete JSON shape in the first place

## Parser Boundary

The mod is responsible for exporting the raw canonical observation data that `models.py` requires.

The parser is responsible for parser-side work such as:

- file-level metadata handling such as `seen_at`
- type coercion into Python dataclasses
- any knowledge-layer derivation already intended to happen in Python, such as deriving suit or rank from `card_key`
- any future parser-only convenience transforms that do not need to live in the mod contract

The mod should not offload required `models.py` fields to the parser if those fields are supposed to come from live game state directly.

## Canonical Data Expectations

The exported snapshot should be centered on the observation fields required to populate `GameObservation`, rather than a metadata-heavy wrapper.

Top-level payload rules:

- the canonical payload should default to the observation field set, not a parallel debug envelope
- extra top-level metadata should not be added by default
- parser-side file metadata such as `seen_at` should remain parser work unless a later explicit decision says otherwise

### State Payload

The state payload should represent the current decision-relevant game state in a canonical form.

Expected categories:

- state fields should be organized to satisfy `GameObservation` and the related nested observation types in `models.py`
- top-level state fields should therefore align with names such as `state_id`, `dollars`, `hands_left`, `discards_left`, `score`, `deck_key`, `stake_id`, `blind_key`, `ante`, `round`, `blinds`, `joker_slots`, `jokers`, `consumable_slots`, `consumables`, `tags`, `vouchers`, `run_info`, `interest`, `shop_items`, `reroll_cost`, `pack_contents`, `hand_size`, `cards_in_hand`, `selected_cards`, and `cards_in_deck`
- nested object fields should likewise align with the names in the corresponding `Observed*` dataclasses in `models.py`
- the canonical payload should stay centered on these observation fields rather than growing a parallel debug-oriented envelope by default

## Information Boundary

The exporter should include:

- state visible to the player
- rule-state that the game openly uses and that a player could infer during play

The exporter should exclude:

- hidden deck order
- unrevealed future rewards
- hidden randomness or future outcomes
- any other omniscient internal state that would give the agent unfair information

## Identity Rules

The exporter should preserve stable per-object identity wherever Balatro exposes it.

This includes, when available:

- playing cards
- jokers
- consumables
- packs
- selected references
- other actionable visible objects

Identity should not rely on a derived display label if a real object identifier exists.

There should be no synthetic fallback identity scheme. If `models.py` expects `instance_id`, the exporter should read the real in-game ID. If an expected real ID is missing for an object that should normally have one, that should be treated as a collector gap or bug to investigate rather than papered over with a made-up ID.

For objects that do not have an `instance_id` field in `models.py`, follow the corresponding `models.py` type exactly instead of inventing an extra identity field.

## Phase Coverage

The first implementation should fully support these phases:

- `blind_select`
- `shop`
- `pack_reward`
- `play_hand`

Other phases may exist internally, but they are not required to be modeled comprehensively in v1.

## Implementation Decisions

- The exporter is a clean schema reset, not a compatibility-preserving patch.
- The handoff format remains a single snapshot JSON file.
- The mod stays observation-first and does not include screenshot logic.
- The mod should not attempt to be executor-ready in v1.
- Files should remain narrowly scoped and split before they become broad utility buckets.
- Files should be grouped by shared purpose; avoid one-file-per-function splits when related logic reads better together.
- If a file starts approaching the soft cap or begins mixing unrelated concerns, it should be split by domain or behavior immediately instead of extended further.
- Domain collectors should build structured summaries, not leak raw Balatro tables into the output.
- Shared helpers should stay generic and lightweight, not become cross-cutting grab bags.
- Internal helper and module API names should be concise but readable, not so abbreviated that their purpose is unclear.
- Deduplication should be based on meaningful exported state, not raw write frequency alone.
- Exact hook choice is an implementation detail unless a hook proves unstable; the observable requirement is correct throttled live export behavior.

## Ordering Rules

To keep the payload deterministic and avoid unnecessary parser-side reordering, the exporter should produce arrays in canonical order.

Ordering rules:

- when `models.py` implies a meaningful order, preserve that order in the exported arrays
- for visible UI collections, use UI order: top to bottom, then left to right
- `cards_in_deck` should be sorted by suit, then by rank
- suit order for `cards_in_deck` should be `spades`, `hearts`, `clubs`, `diamonds`
- rank order for `cards_in_deck` should be `ace`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `jack`, `queen`, `king`
- `run_info.hands` should follow `RUN_INFO_HAND_ORDER` from `models.py`
- the parser may preserve or validate exported order, but canonical ordering should originate in the exporter rather than being left ambiguous
- tie-break behavior for visually overlapping or ambiguous UI ordering can be deferred until executor or UI-specific follow-up work clarifies the need

## Zone Naming Rules

`selected_cards.zone` and any similar game-facing zone names should follow the game's naming conventions rather than made-up aliases.

Rules:

- use the real game naming when the game already exposes a stable zone name
- do not invent alternate labels just to make the JSON look nicer
- if a zone name decision becomes ambiguous during implementation, prefer the in-game name and document it

## Write Policy

The exporter should support a throttled live export path that captures on the normal update loop at roughly every `0.05` seconds.

Write behavior rules:

- deduplication should still suppress redundant identical writes
- the throttled path should be the normal live-export behavior during gameplay
- exact hook implementation details are flexible as long as these observable behaviors hold
- repo-side print/debug output paths are out of scope for this mod PRD

## Partial-State Rules

When a section of state is inactive or unavailable, the payload should still be shaped according to what `GameObservation` needs.

Rules:

- use `null` for inactive optional nested objects such as structures that correspond to optional nested dataclasses
- use empty arrays for present collection fields with zero items
- do not omit fields simply because the current phase does not populate them
- if a value is required by `models.py` and should be available from the game in the current context, missing data should be treated as a collection bug to investigate

## Proposed Internal Module Boundaries

This section names responsibilities, not final file names.

### Bootstrap And Hooking

- install the mod
- attach to the update path
- trigger snapshot capture on startup and on eligible updates

### Snapshot Orchestration

- gather root game references
- invoke phase inference
- invoke each domain collector
- assemble the final payload

### Shared Normalization

- safe table and scalar coercion
- token normalization
- stable sorting helpers
- lightweight shared transforms

### Phase Inference

- determine the current interaction phase from Balatro state
- keep phase mapping rules in one place

### Domain Collectors

Separate collectors should exist for clearly different gameplay domains, such as:

- economy and run progression
- blinds and tags
- cards and zones
- jokers and consumables
- vouchers and deck identity
- shop items
- pack contents
- selections and references

### Schema And Serialization

- convert internal summaries into the canonical public snapshot shape
- handle JSON encoding cleanly and deterministically

### Signature And Write Control

- compute a stable signature from exported state
- skip redundant writes
- enforce export throttling behavior

### Filesystem Output

- ensure target directory exists
- write `live_state.json`
- keep write failure handling isolated

## Testing Decisions

Good tests should validate exported behavior and public semantics, not internal implementation details.

The first pass of automated mod tests should focus on pure core logic inside `mods/`, especially:

- phase inference
- normalization and coercion helpers
- canonical payload shaping
- signature and dedup behavior

Hook installation and filesystem interaction do not need heavy automated coverage in v1. Those should be validated primarily through runtime verification in a real Balatro session.

The old exporter-specific Lua tests should not be treated as a baseline to preserve. The rebuild should introduce only new focused tests that match the new modular architecture.

## Acceptance Criteria

- The mod loads successfully under the expected Balatro mod environment.
- The mod writes `ai/live_state.json` without screenshot support or external image tooling.
- The written payload follows the new canonical schema.
- The written payload is complete enough to support full downstream population of `GameObservation` after parser migration.
- The written payload uses `models.py` field names and preserves game-facing category names instead of introducing aliases.
- Optional exported values are emitted as `null` rather than being omitted.
- Exported arrays follow the canonical ordering rules defined in this PRD.
- The payload covers the main decision loop phases.
- The payload includes stable object identity when exposed by the game.
- The exporter tolerates partial or missing game structures without crashing.
- Repeated identical state does not spam writes unnecessarily.
- The exporter supports throttled live export at roughly `0.05` second intervals.
- The implementation remains organized into purposeful modules rather than one oversized file.

## Out Of Scope

- Python parser migration
- updates to `GameObservation` on the Python side
- executor automation
- screenshot capture
- pixel targeting
- coordinate extraction for UI clicks
- complete support for every obscure game overlay or edge-case phase

## Risks And Watchouts

- Balatro and Steamodded hook behavior may shift over time.
- Some game structures may be absent or shaped differently across phases.
- Some live objects may not expose identity exactly as expected, which should be treated as a collector investigation problem rather than solved with synthetic fallback IDs.
- Some assumptions in `models.py` may need confirmation against live Balatro state if a field expected by the Python contract is not actually exposed the way we expect.
- Schema cleanup in the mod will require downstream Python parser work before the new payload is consumable end-to-end.
- If helper modules are not kept disciplined, they may drift into a new dumping ground even with a split layout.

## Follow-Ups

These items are intentionally outside the first mod implementation, but they should be tracked after the new observation contract stabilizes.

### Python Parser Update

Update the Python observation parser to consume the new canonical schema and populate `GameObservation` correctly from the rebuilt mod output.

This likely includes:

- updating field names and shape assumptions
- mapping any new identity fields such as `instance_id`
- reconciling any renamed or cleaned-up payload sections
- revalidating parser behavior against real exported snapshots

### Observation Model Review

Review `GameObservation` and related Python dataclasses to confirm they still match the intended canonical exporter contract.

This may include:

- adding fields the new canonical contract supports cleanly
- removing legacy assumptions from the old exporter shape
- tightening comments to reflect the new contract source of truth

### UI And Actionability Investigation

Investigate whether the mod can expose enough stable UI or object-level interaction data to support executor automation without screenshots or pixel calculations.

This should be treated as a separate feasibility effort, not a hidden requirement of the first exporter rewrite.

Questions for that follow-up:

- which in-game actions can be tied directly to object identity
- which actions, if any, require UI geometry
- whether stable game structures can replace screenshot-based targeting

### Runtime Validation Pass

Run the rebuilt exporter in real Balatro sessions and capture representative snapshots for:

- blind selection
- shop
- opened packs
- in-blind hand play

Use those snapshots to verify both completeness and stability of the canonical contract.

### Policy And Validator Follow-Up

Once the new parser is updated, review policy and runtime validation logic to make sure they are using the richer canonical state effectively and not relying on stale assumptions from the old payload.

### Documentation Refresh

Update mod-facing and repo-facing documentation so the new exporter contract, install flow, and handoff expectations are documented consistently.

## Assumptions

- Old mod-specific tests outside `mods/` have already been purged by the user.
- The first rebuild should stay entirely within `mods/`.
- The canonical schema defined by the new mod becomes the new source of truth for downstream integration work.
- The rebuild should not leave behind any new dumping-ground file that combines unrelated collectors, serialization, hooks, and write control in one place.

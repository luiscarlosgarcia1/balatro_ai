# PRD: JSON-First Observer Schema For The Balatro AI

## Problem Statement

The current observer has improved a lot, but it is still shaped like an engineering debug dump instead of the canonical machine-readable game-state contract for the Balatro agent. It mixes human-readable labels with raw ids, duplicates some concepts across sections, uses inconsistent naming, and still exposes too much formatting-oriented structure instead of a stable JSON schema optimized for AI consumption.

The user wants the observer output to become the authoritative JSON-first contract for the agent. That means:

- prioritize machine-readable ids and normalized gameplay categories over human-readable labels
- keep top-level fields in a strict, approved order
- expose the full state the AI needs without screenshot inference
- omit irrelevant fields when possible, but not at the cost of confusing or incomplete JSON
- avoid duplicating the same gameplay concept in multiple sections unless explicitly required
- keep the pretty output as a derived debug view, not the canonical contract

The agreed top-level order is:

1. `source`
2. `state_id`
3. `interaction_phase`
4. `blind_key`
5. `deck_key`
6. `stake_id`
7. `score`
8. `money`
9. `interest`
10. `hands_left`
11. `discards_left`
12. `joker_slots`
13. `jokers`
14. `consumable_slots`
15. `consumables`
16. `vouchers`
17. `tags`
18. `ante`
19. `round_count`
20. `blinds`
21. `shop_items`
22. `reroll_cost`
23. `pack_contents`
24. `hand_size`
25. `cards_in_hand`
26. `selected_cards`
27. `cards_in_deck`
28. `notes`

This matters because the AI will eventually consume the observer directly. If the observer stays half-human, half-machine, then policy logic, evaluation, and future automation will all be built on an unstable surface.

## Solution

Refit the observer around a canonical JSON-first schema that is optimized for AI consumption and uses raw ids plus normalized gameplay categories instead of human-readable labels.

The observer should:

- emit the approved top-level fields in the approved order
- use raw ids and normalized gameplay categories as the primary representation
- normalize machine-readable ids, categories, and enum-like values to lowercase-with-underscores wherever practical
- represent lists as arrays of structured objects rather than flattened strings
- keep card, joker, consumable, voucher, tag, blind, and pack objects compact but gameplay-complete
- include structural card information such as `card_key`, `card_kind`, `suit`, `rank`, `rarity`, `enhancement`, `edition`, `seal`, `stickers`, `facing`, `cost`, `sell_price`, and `debuffed` when relevant
- expose selected state as lightweight references when that is more efficient than repeating full objects
- avoid duplicating shop vouchers inside `shop_items`
- preserve visible UI order for `shop_items` so the AI sees the market in the same order the player does
- represent opened packs through a dedicated `pack_contents` object placed after `shop_items`
- keep notes as structured strings in `notes`, including operational entries like screenshot status and observation timestamp when those are part of the observer output

The canonical JSON contract should prefer predictable top-level presence over aggressive omission:

- every approved top-level key should be present in the canonical output
- top-level collection fields should use empty arrays when they have no entries
- top-level optional object fields should use `null` when they are not active, such as `pack_contents`
- nested object fields should usually be omitted when they are irrelevant to that specific object, unless keeping them present materially simplifies machine consumption

The canonical JSON output is the contract. Any human-readable console rendering is a secondary view derived from that contract.

## User Stories

1. As the Balatro agent developer, I want observer output to be JSON-first, so that policy code can consume it directly without reparsing human-readable text.
2. As the Balatro agent developer, I want the observer to prefer raw ids and normalized gameplay categories, so that the AI operates on stable identifiers instead of display labels.
3. As the Balatro agent developer, I want the top-level fields to appear in one strict order, so that downstream tooling can depend on a consistent schema.
4. As the Balatro agent developer, I want `source` and `state_id` preserved as compact machine-readable fields, so that the agent can reason about freshness and state transitions.
5. As the Balatro agent developer, I want `interaction_phase` preserved separately from the main state id, so that the agent can tell shop, blind select, and pack interaction apart.
6. As the Balatro agent developer, I want `blind_key`, `deck_key`, and `stake_id` represented as raw ids, so that the agent can look up meaning elsewhere instead of relying on display text.
7. As the Balatro agent developer, I want score represented as a machine-readable structure, so that the AI can compare current and target score without string parsing.
8. As the Balatro agent developer, I want core run state like money, hands, discards, ante, round count, reroll cost, and raw interest determinants exposed directly, so that the AI can evaluate economy and tempo.
9. As the Balatro agent developer, I want `joker_slots`, `joker_count`, `consumable_slots`, and `hand_size` exposed explicitly, so that the AI knows both current occupancy and capacity.
10. As the Balatro agent developer, I want `jokers` emitted as structured objects, so that the AI can inspect edition, rarity, sell price, stickers, and debuff state without pulling effect summaries from the observer.
11. As the Balatro agent developer, I want `consumables` emitted as structured inventory objects, so that the AI can evaluate current inventory without screenshots.
12. As the Balatro agent developer, I want `shop_vouchers` broken out separately, so that voucher decisions are not mixed into the rest of the market data.
13. As the Balatro agent developer, I want `vouchers` to contain all currently active purchased vouchers, so that the AI understands the run modifiers already in force.
14. As the Balatro agent developer, I want `skip_tags` to show the claimable tags for the current ante, so that the AI can evaluate skipping blind options.
15. As the Balatro agent developer, I want `tags` to show active tags ordered most-recent-first, so that the AI can understand the run’s current tag stack.
16. As the Balatro agent developer, I want `shop_items` to be the canonical market list for buyable items other than vouchers, so that the AI can reason over one primary shop list without duplication.
17. As the Balatro agent developer, I want `shop_items` entries to include structural details like cost, edition, enhancement, seal, consumable kind, stickers, and sell price when relevant, so that the AI can distinguish modified offers.
18. As the Balatro agent developer, I want `shop_items` to expose effective current prices directly, so that price reasoning does not rely on a separate discount payload.
19. As the Balatro agent developer, I want opened pack state represented through `pack_contents`, so that pack decisions are modeled separately from the normal shop market.
20. As the Balatro agent developer, I want `pack_contents` to include metadata like pack key, kind, pack size, choose limit, choices remaining, and skip availability, so that the AI understands the pack interaction constraints.
21. As the Balatro agent developer, I want `cards_in_hand` represented as structured card objects, so that the AI can evaluate play and discard decisions from game state alone.
22. As the Balatro agent developer, I want `selected_cards` represented explicitly, so that the AI can reason about partial selections without screen inspection.
23. As the Balatro agent developer, I want `cards_in_deck` represented as structured card objects sorted by suit and rank, so that the AI sees a stable inventory-style view of the deck rather than arbitrary area order.
24. As the Balatro agent developer, I want `cards_in_hand` represented in the same stable suit-and-rank ordering, so that the AI sees a deterministic inventory-style hand view instead of arbitrary area order.
25. As the Balatro agent developer, I want every card object to expose suit and rank directly, so that the AI does not need to infer them from a code string.
26. As the Balatro agent developer, I want card objects to expose `card_kind`, so that the AI can distinguish default, stone, steel, glass, and other gameplay categories through normalized values.
27. As the Balatro agent developer, I want card, joker, and consumable objects to expose `rarity` when meaningful, so that the AI can use it without falling back to human-readable names.
28. As the Balatro agent developer, I want structural properties like edition, seal, enhancement, stickers, facing, debuffed, cost, and sell price emitted only when relevant, so that JSON stays compact but complete.
29. As the Balatro agent developer, I want the observer to avoid duplicating shop vouchers inside `shop_items`, so that the market view is efficient and unambiguous.
30. As the Balatro agent developer, I want the pretty observation output to be derived from the canonical JSON contract, so that human-readable formatting cannot drift away from the true schema.
31. As the Balatro agent developer, I want tests to verify the exact schema shape, field ordering, omission behavior, normalization rules, note entries, and non-duplication rules, so that future refactors cannot silently regress the AI contract.

## Implementation Decisions

- The canonical contract is JSON-first and AI-first. Human-readable labels are not part of the primary observer schema.
- The approved top-level field order is mandatory and should be preserved in the serializer and pretty output.
- Machine-readable ids, categories, and enum-like values should be normalized to lowercase-with-underscores wherever practical so downstream policy code does not need a second normalization pass.
- Lists should be arrays of compact structured objects rather than flattened strings.
- `score` should be represented as an object with `current` and `target`.
- The exact `score` shape should be `{"current": <number|null>, "target": <number|null>}` rather than a string or split top-level fields.
- `shop_vouchers` should be separate from `shop_items`; vouchers must not be duplicated inside `shop_items`.
- `shop_vouchers` should always be represented as an array, even when there is only one current shop voucher.
- `shop_items` remains the canonical market list for other buyable items such as jokers, consumables, and booster packs, and it should preserve visible UI order.
- `interest` should be represented as a raw-state object with `amount`, `cap`, and `no_interest` rather than a derived payout scalar.
- `pack_contents` should be a dedicated object placed after `shop_items` and contain both metadata and the visible pack cards.
- `selected_cards` should use lightweight references where that is more efficient than repeating the full card payload. The preferred shape is a compact object such as `{zone, card_key}` or `{zone, joker_key}` rather than a full repeated object.
- `selected_cards` should be an array and use `[]` when nothing is selected.
- `cards_in_hand` and `cards_in_deck` should both be rendered in stable suit-and-rank order for deterministic AI consumption.
- The exact suit order should be `clubs`, `diamonds`, `hearts`, `spades`.
- The exact rank order should be `ace`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `jack`, `queen`, `king`.
- `cards_in_deck` should be rendered in this suit-and-rank order, not future draw order.
- Card, joker, consumable, and blind objects should prioritize ids and normalized gameplay categories over display labels.
- `stake_id` should preserve the raw game-exported identifier in the most direct efficient form available, even if that form is numeric rather than a prettified string key.
- Relevant structural fields should be emitted only when meaningful to that object. If omitting them would make the JSON harder to consume or reason about, use explicit nulls instead of inventing values.
- Notes stay as string entries in `notes`, and operational observer entries such as `screenshot_status` and `seen_at` belong there when emitted.
- The preferred operational note format is compact strings such as `screenshot_status=true` and `seen_at=2026-03-25T23:33:06.250035+00:00`.
- Suggested deep modules:
  - a canonical observation schema module
  - a JSON serializer that enforces field order and omission rules
  - a Lua exporter layer that gathers raw state into schema-shaped payloads
  - a card normalization module for cards, jokers, and consumables
  - a selection and modal-state module for pack contents and selected cards

## Testing Decisions

- Good tests should verify public behavior through the canonical JSON contract and the derived pretty output, not private helper implementation.
- Tests should assert exact field names, field ordering, omission behavior, and non-duplication rules.
- Tests should cover:
  - score object structure
  - top-level empty-array versus null behavior
  - raw id fields for state, blind, deck, and stake
  - raw interest object behavior for `interest.amount`, `interest.cap`, and `interest.no_interest`
  - lowercase-with-underscores normalization behavior for machine-readable ids and categories
  - structured joker, consumable, voucher, tag, shop item, blind, and card objects
  - exclusion of vouchers from `shop_items`
  - preservation of visible UI order in `shop_items`
  - presence and shape of `pack_contents`
  - suit/rank ordering for `cards_in_hand` and `cards_in_deck`
  - lightweight reference behavior for `selected_cards`, including compact `{zone, *_key}` shapes
  - note structure including `screenshot_status` and `seen_at` entries when emitted
- The Lua exporter and Python observer should both be covered end to end where possible.
- Prior art in the codebase is the live observer contract suite and the live exporter signature regression tests.

## Out of Scope

- Policy logic for deciding what the agent should buy, play, discard, or skip
- Effect interpretation or effect lookup registries beyond structural ids and fields
- Screenshot-based state inference
- Training, self-play, or model learning loops
- Human-readable UI polish as a primary objective

## Further Notes

- The user explicitly wants JSON and efficiency prioritized over human readability.
- The observer should expose exactly what the AI needs to know, not more display text.
- If an object cannot meaningfully have a field, that field should usually be omitted rather than invented.
- The pretty output still matters for debugging, but it is downstream of the canonical JSON contract rather than the source of truth.

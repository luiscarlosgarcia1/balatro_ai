# Plan: Telepathic File-Bridge Executor

> Source PRD: docs/prds/telepathic_executor/telepathic_executor.md

## Architectural Decisions

Durable decisions that apply across all phases:

- **File channel**: `ai/action.json` (Python → Lua), `ai/action_error.json` (Lua → Python on failure). No separate ack file — deletion of `action.json` is the completion signal.
- **Action schema**: `action.json` is a JSON object with a top-level `"actions"` array. Each item has `kind` (string), `target_ids` (int array), `target_key` (string or null), and `order` (int array). Python writes the full sequence atomically.
- **Bridge key**: `instance_id` in `GameObservation` is identical to `card.ID` in Lua. This is the lookup key the Lua executor uses to find card objects — no screen positions, no display indices.
- **Stable-state completion signal**: The Lua executor does not delete `action.json` immediately after queuing the last `G.FUNCS.*` call. It appends a final `G.E_MANAGER` condition event that polls `G.STATE` and fires only once the game has settled into a known actionable state. The actionable states are defined as a constant set in `ai_executor`: `SELECTING_HAND`, `SHOP`, `BLIND_SELECT`, and all pack states (`TAROT_PACK`, `PLANET_PACK`, `SPECTRAL_PACK`, `BUFFOON_PACK`, `STANDARD_PACK`). Scoring periods, interest screens, and ante transitions are not in this set and cause the condition event to keep waiting.
- **Exporter gate**: `live_state_exporter` skips its write cycle while `action.json` is present. It writes exactly once after `action.json` is deleted (transition-triggered, not tick-triggered). This guarantees Python always reads a stable, post-action observation.
- **Startup write**: On game load, before any `action.json` has ever been written, the exporter performs one unconditional write so Python has an initial observation to act on. After that it switches to the transition-triggered model.
- **Separate mods**: `ai_executor` and `live_state_exporter` are independent mods. Each can be installed, disabled, or modified without touching the other.
- **Protocol unchanged**: The `Executor` Python protocol (`execute(action: GameAction) -> None`) is not modified. `EpisodeRunner` and `Validator` are not touched.
- **Lua trusts Python**: The Lua executor performs no re-validation. It executes what the queue says and writes an error file if execution fails at the game API level.

---

## Phase 1: Action Contract

**User stories**: 22, 23, 24

### What to build

Define the shared vocabulary that both sides of the file channel will depend on. This is pure Python — no file I/O, no Lua, no running game required.

Introduce an `ActionKind` module that declares string constants for every valid action kind: `play_hand`, `discard`, `buy_shop_item`, `sell_joker`, `reroll_shop`, `leave_shop`, `select_blind`, `skip_blind`, `pick_pack_item`, `skip_pack`, `use_consumable`, `reorder_jokers`, `reorder_hand`. Policy code imports from this module rather than using bare strings.

Extend `GameAction` with two new fields: `target_ids` (tuple of ints, default empty) and `order` (tuple of ints, default empty). The existing `target` string field is retained but superseded by `target_ids` and `target_key` in the new schema.

Define and test the JSON serialization shape for `action.json`: every `ActionKind` constant produces a correctly structured action object, `target_ids` and `order` serialize as integer arrays, `target_key` serializes as string or null.

### Acceptance criteria

- [ ] `ActionKind` module exists and covers every action in the PRD
- [ ] `GameAction` carries `target_ids` and `order` fields with correct types and defaults
- [ ] Every `ActionKind` constant round-trips through JSON serialization without mutation
- [ ] `GameAction` serializes to the documented `action.json` action object shape for each kind
- [ ] Existing policy and runtime tests still pass without modification

---

## Phase 2: FileExecutor

**User stories**: 1, 2, 3, 4, 25, 26, 27, 33

### What to build

Implement `FileExecutor`, a concrete `Executor` that closes the Python side of the file channel. It accepts a paths argument consistent with `BalatroPaths` to locate the `ai/` directory.

On `execute`, it serializes the action as a one-item queue and writes `action.json` atomically (write to temp, then rename). It then polls on a configurable interval until either `action.json` is absent (success) or `action_error.json` appears (failure). On failure it reads the error file, raises a typed `ExecutorError` with the reason, and cleans up the error file. On timeout it raises as well.

A companion `execute_sequence` method accepts a pre-built list of `GameAction` and writes them as a multi-item queue in one atomic write. The runtime loop continues to call `execute` for single actions; `execute_sequence` is available for future policy upgrades.

All tests use a real temporary filesystem directory — no mocks, no running game.

### Acceptance criteria

- [ ] `FileExecutor` implements the `Executor` protocol without protocol changes
- [ ] `action.json` is written atomically and contains a valid `"actions"` array
- [ ] `FileExecutor` returns cleanly when `action.json` is deleted
- [ ] `FileExecutor` raises `ExecutorError` when `action_error.json` appears, including the reason from the file
- [ ] `FileExecutor` raises on timeout if neither signal appears within the configured window
- [ ] `execute_sequence` writes all actions as a single atomic queue
- [ ] Poll interval and timeout are configurable for fast test execution

---

## Phase 3: Lua Executor — All Game Actions

**User stories**: 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 34, 35, 36, 37, 38, 39

### What to build

Build the complete `ai_executor` Lua mod. This is the meat of the feature and the first point at which a real end-to-end run becomes possible.

The mod hooks into `love.update` and polls for `action.json` each frame. When the file appears and the mod is not already processing, it reads and parses the JSON queue, then processes each action in order via `G.E_MANAGER:add_event`. Each action handler locates target card objects by iterating the appropriate `CardArea.cards` table and matching `card.ID` to the instance IDs declared in the action.

Action handlers to implement: `play_hand` (select by `target_ids`, then `G.FUNCS.play_cards_from_highlighted`), `discard` (select by `target_ids`, then `G.FUNCS.discard_cards_from_highlighted`), `buy_shop_item` (find in shop areas by `target_ids[0]`, then `G.FUNCS.buy_from_shop`), `sell_joker` (find in jokers by `target_ids[0]`, then `card:sell_card`), `reroll_shop` (`G.FUNCS.reroll_shop`), `leave_shop` (`G.FUNCS.toggle_shop`), `select_blind` (find blind by `target_key`, then `G.FUNCS.select_blind`), `skip_blind` (find blind by `target_key`, then `G.FUNCS.skip_blind`), `pick_pack_item` (find in `G.pack_cards` by `target_ids[0]`, then `G.FUNCS.use_card`), `skip_pack` (`G.FUNCS.skip_booster`), `use_consumable` (`target_ids[0]` is consumable, `target_ids[1:]` are hand card targets, select targets then `G.FUNCS.use_card`).

After the last action event is queued, a final `G.E_MANAGER` condition event is appended. This event polls `G.STATE` on each game tick and fires only when the state has settled into the actionable set (defined as a named constant in the mod). On fire, it deletes `action.json`. On any handler error, the mod writes `action_error.json` with the action kind and reason, halts queue processing, and does not delete `action.json`.

### Acceptance criteria

- [ ] Mod polls for `action.json` each frame without impacting game performance when idle
- [ ] Each action kind routes to the correct `G.FUNCS.*` or card method call
- [ ] Card objects are located by `card.ID` matching, not by display position
- [ ] The actionable state set is defined as a named constant and covers all non-transitional states
- [ ] `action.json` is deleted only after `G.STATE` settles into the actionable set
- [ ] `action_error.json` is written with action kind and reason on any handler failure
- [ ] Queue processing halts at the first error; subsequent actions in the queue are not executed
- [ ] A real play-through of at least one full blind (select blind → play hand to completion → enter shop) works end-to-end

---

## Phase 4: Exporter Gate and Deduplication Removal

**User stories**: 28, 29, 30, 31

### What to build

Modify `live_state_exporter` to integrate with the action channel. The exporter now checks for the presence of `action.json` at the start of each write cycle. If the file exists, the write is skipped entirely — the game is mid-execution and the state is not yet stable.

The exporter tracks whether it has written since the last `action.json` deletion. When it detects the file has been deleted (transition from present to absent), it writes `live_state.json` exactly once, then returns to waiting. It does not write again until the next deletion transition.

On game load, before any `action.json` has been written, the exporter performs one unconditional startup write so Python has an initial observation to work from.

With the transition-triggered model confirmed working, remove the deduplication logic from the exporter. It is no longer needed — state only changes as a result of actions, and the exporter only writes post-action.

### Acceptance criteria

- [ ] Exporter skips all write cycles while `action.json` is present
- [ ] Exporter writes exactly once after `action.json` is deleted
- [ ] Exporter does not write again until the next action queue completes
- [ ] Startup write fires once on game load before any action has been submitted
- [ ] Deduplication logic is removed
- [ ] Existing observation parser and smoke tests continue to pass against the new export behavior

---

## Phase 5: Reorder Actions

**User stories**: 19, 20, 21, 38, 40

### What to build

Add `reorder_jokers` and `reorder_hand` handlers to `ai_executor`. These cannot use `G.FUNCS.*` or `CardArea:sort()` since they require arbitrary ordering. Instead, each handler receives the full desired sequence as an `order` array of instance IDs, builds a new ordered table by matching each position to its card object via `card.ID`, assigns it back to `CardArea.cards`, and triggers a display refresh so the game renders the new order correctly.

If any instance ID in the `order` array is not found in the target area, the handler writes `action_error.json` and halts rather than performing a partial reorder. The `order` array must also contain exactly as many IDs as there are cards in the target area; a length mismatch is also an error.

The reorder logic is extracted into a testable helper function that can be exercised against a mock card table without a running game.

### Acceptance criteria

- [ ] `reorder_jokers` rearranges `G.jokers.cards` to match the declared `order` sequence
- [ ] `reorder_hand` rearranges `G.hand.cards` to match the declared `order` sequence
- [ ] Display refresh is triggered after reorder so the game renders the new order
- [ ] An unknown instance ID in `order` produces an error file and halts without partial reorder
- [ ] A length mismatch between `order` and the target area produces an error file and halts
- [ ] Reorder logic is tested against a mock card table independently of a running game

# PRD: Telepathic File-Bridge Executor

## Problem Statement

The `Executor` interface in the Balatro AI scaffold is a permanent stub. The system can observe the game and reason about the correct action to take, but it cannot close the loop — no action ever reaches the game. The only path to real game control today would be mouse and keyboard automation, which is brittle, intrusive, and dependent on screen layout. It also hijacks the developer's input devices and cannot run cleanly alongside normal use.

The game itself, however, already exposes a rich internal Lua API. Every meaningful player interaction — playing a hand, discarding, buying from the shop, selecting a blind, using a consumable, reordering jokers — maps directly to a callable function in the `G.FUNCS.*` namespace. The game's event queue (`G.E_MANAGER`) handles sequencing and animation. Card objects are addressable by stable numeric IDs that are already present in the live observation. In other words, the game already has the actuator layer the AI needs. It is simply not connected to anything.

The observation side of this project already uses a file-based channel: the Lua mod writes `live_state.json` and Python reads it. The same pattern works in reverse. Python can write an action queue to a file, and a Lua mod can read it, execute each action through the game's own APIs, and signal completion through deletion of the file. No mouse. No keyboard. No screen coordinates. The AI speaks directly to the game's internal logic, which is why this approach is called telepathic.

There is also a secondary problem with the current exporter. It writes `live_state.json` on every game tick regardless of whether anything has changed. This requires deduplication logic to avoid spurious observations. Because game state in Balatro only changes as a result of player actions, the right model is for the exporter to write only after the action queue has been fully processed — producing exactly one post-action snapshot per round of the AI loop. This removes the deduplication requirement and makes the observation-action cycle semantically clean.

## Solution

Extend the existing file-based communication channel to support both directions. Python writes a queue of typed actions to `ai/action.json`. A new, separate Lua mod (`ai_executor`) reads the queue, executes each action in order through `G.FUNCS.*` and `G.E_MANAGER`, then deletes the file when all actions are complete. If an action cannot be executed, the mod writes `ai/action_error.json` describing the failure before halting. The live state exporter is modified to skip its write cycle when `action.json` is present, resuming only after the executor has finished — guaranteeing that `live_state.json` always reflects a stable post-action state and eliminating the need for deduplication.

On the Python side, `GameAction` is extended to carry structured targeting information: a `target_ids` tuple of integer instance IDs for actions that target specific cards or items, and an `order` tuple of instance IDs for reordering actions. A new `FileExecutor` class implements the `Executor` protocol by serializing the action queue to `action.json` and polling until the file is deleted or an error file appears. A canonical set of `ActionKind` constants closes the previously open-ended `kind` string.

Reordering of joker slots and hand card positions is included in scope. It receives dedicated treatment because it cannot be implemented through a simple `G.FUNCS.*` call — it requires direct manipulation of the relevant `CardArea.cards` table followed by a redraw. A reorder action carries the full desired sequence of instance IDs, and the Lua executor rearranges the array to match.

The executor mod is deliberately separate from `live_state_exporter`. Each mod has a single responsibility and can be toggled independently.

## User Stories

1. As the Balatro AI developer, I want the Python executor to write a queue of actions to a file and have them performed inside the game without touching my mouse or keyboard, so that the AI can control the game in a clean, non-intrusive way.
2. As the Balatro AI developer, I want the action queue to be expressed as a single atomic file containing an ordered array of actions, so that the entire intended sequence is committed at once and the Lua side never sees a partial plan.
3. As the Balatro AI developer, I want the Lua executor to process each action in the queue in order using the game's own internal APIs, so that the game responds identically to AI input as it would to human input.
4. As the Balatro AI developer, I want the Lua executor to signal completion by deleting the action file, so that Python has a clean, observable ack signal without requiring an extra file or polling mechanism.
5. As the Balatro AI developer, I want the Lua executor to write a structured error file if an action cannot be executed, so that failures are visible and debuggable rather than silent.
6. As the Balatro AI developer, I want the Lua executor to fully trust the Python-side validator and not re-validate actions in Lua, so that validation logic lives in one place and the Lua mod stays thin.
7. As the Balatro AI developer, I want the action queue to support playing a specific set of hand cards identified by instance ID, so that the AI can select and play any hand combination it chooses.
8. As the Balatro AI developer, I want the action queue to support discarding a specific set of hand cards identified by instance ID, so that the AI can manage its hand strategically.
9. As the Balatro AI developer, I want the action queue to support buying a specific shop item identified by instance ID, so that the AI can act on exactly the item it evaluated.
10. As the Balatro AI developer, I want the action queue to support selling a specific joker identified by instance ID, so that the AI can manage its joker slots.
11. As the Balatro AI developer, I want the action queue to support rerolling the shop, so that the AI can pursue a different set of shop options.
12. As the Balatro AI developer, I want the action queue to support leaving the shop, so that the AI can advance to the next blind select phase.
13. As the Balatro AI developer, I want the action queue to support selecting a blind by its key string, so that the AI can advance into a round.
14. As the Balatro AI developer, I want the action queue to support skipping a blind by its key string, so that the AI can preserve hand count when appropriate.
15. As the Balatro AI developer, I want the action queue to support picking a specific item from an open booster pack by instance ID, so that the AI can take the card or joker it evaluated.
16. As the Balatro AI developer, I want the action queue to support skipping an open booster pack, so that the AI can decline a pack when no items are worth taking.
17. As the Balatro AI developer, I want the action queue to support using a specific consumable by instance ID, optionally targeting one or more hand cards by instance ID, so that the AI can apply Tarot, Planet, and Spectral cards to its intended targets.
18. As the Balatro AI developer, I want consumable targeting to carry the consumable's instance ID and all target card instance IDs in a single action, so that the Lua executor can perform the selection and use in one sequenced operation without Python re-entering the loop mid-action.
19. As the Balatro AI developer, I want the action queue to support reordering jokers to a fully specified desired sequence of instance IDs, so that the AI can arrange jokers for optimal interaction ordering.
20. As the Balatro AI developer, I want the action queue to support reordering hand cards to a fully specified desired sequence of instance IDs, so that the AI can sort its hand before playing or discarding.
21. As the Balatro AI developer, I want reorder actions to declare the full target order rather than individual swap operations, so that the Lua executor can converge to the desired state in one pass without needing Python to choreograph a series of swaps.
22. As the Balatro AI developer, I want `GameAction` to carry a `target_ids` tuple of integer instance IDs, so that actions referencing specific cards or items can be expressed unambiguously.
23. As the Balatro AI developer, I want `GameAction` to carry an `order` tuple of integer instance IDs, so that reordering actions can express the full desired sequence without encoding it in `target_ids`.
24. As the Balatro AI developer, I want a canonical `ActionKind` module that closes the set of valid action kind strings, so that policy authors and executor authors share an unambiguous vocabulary and typos are caught statically.
25. As the Balatro AI developer, I want the `FileExecutor` to implement the existing `Executor` protocol without changes to the protocol, so that the runtime loop requires no modification to gain real execution capability.
26. As the Balatro AI developer, I want `FileExecutor` to serialize the action queue atomically so that the Lua side never reads a partially-written file.
27. As the Balatro AI developer, I want `FileExecutor` to raise a typed exception if an error file is detected, so that the runtime can handle execution failures explicitly rather than silently looping.
28. As the Balatro AI developer, I want the `live_state_exporter` to skip its write cycle whenever `action.json` is present, so that Python never receives a mid-execution observation.
29. As the Balatro AI developer, I want `live_state.json` to be written exactly once after the action queue is fully processed, so that every observation Python reads represents a stable post-action game state.
30. As the Balatro AI developer, I want the deduplication logic in the exporter to be removed once the action-gated write cycle is in place, so that the codebase does not carry unnecessary complexity.
31. As the Balatro AI developer, I want the `ai_executor` mod to be a separate mod from `live_state_exporter`, so that each mod has a single responsibility and can be installed, disabled, or modified independently.
32. As the Balatro AI developer, I want the `ai/` folder to remain the single shared communication directory for both mods, so that the file-based channel is easy to locate and reason about.
33. As the Balatro AI developer, I want all action file writes and deletes to be atomic where the platform supports it, so that partial reads are not possible under normal operation.
34. As the Balatro AI developer, I want the error file to carry the action kind and a human-readable reason for the failure, so that debugging a failed queue does not require reading game logs.
35. As the Balatro AI developer, I want the Lua executor to halt queue processing after the first error rather than skipping to the next action, so that the game is never left in a partially-executed state that the Python side did not anticipate.
36. As the Balatro AI developer, I want the Lua executor to find card and item objects by iterating the appropriate `CardArea.cards` table and matching `card.ID` to the instance IDs in the action, so that the executor does not depend on screen position or display order.
37. As the Balatro AI developer, I want each action in the queue to be self-contained, so that the Lua executor does not need to track state between items in the queue.
38. As the Balatro AI developer, I want the `play_hand` and `discard` actions to perform card selection and the subsequent trigger as a sequenced `G.E_MANAGER` operation, so that animation and game state update correctly as they would for human input.
39. As the Balatro AI developer, I want the reorder implementation to directly manipulate the `CardArea.cards` table and trigger a redraw, so that the game reflects the new order without requiring drag-and-drop simulation.
40. As the Balatro AI developer, I want the reorder implementation to match each position in the desired order to the corresponding card object by instance ID before rearranging, so that a mismatch between the declared order and actual hand contents produces a clear error rather than a silent wrong reorder.

## Implementation Decisions

- The communication channel uses two files: `ai/action.json` (Python → Lua) and `ai/action_error.json` (Lua → Python on failure). No separate ack file is needed — deletion of `action.json` is the ack signal.
- `action.json` contains a top-level JSON object with an `"actions"` key whose value is an ordered array of action objects. Python writes the entire sequence at once.
- Each action object in the array has the following fields: `kind` (string), `target_ids` (array of integers, may be empty), `target_key` (string or null, used for objects without instance IDs such as blinds), and `order` (array of integers, used only for reorder actions).
- For `use_consumable`, `target_ids[0]` is the instance ID of the consumable to use; `target_ids[1:]` are the instance IDs of the hand cards to target. The Lua executor uses this convention to perform both the selection and the use in a single sequenced operation.
- For `select_blind` and `skip_blind`, `target_key` carries the blind key string (e.g., `"bl_small"`). Blind objects have no stable numeric instance ID in the observation.
- `ActionKind` is a new Python module that declares string constants for every valid action kind. Policy code should import from this module rather than using bare strings.
- `GameAction` gains two new fields: `target_ids: tuple[int, ...]` (default empty) and `order: tuple[int, ...]` (default empty). The `target: str | None` field is retained for backwards compatibility with existing policy code but is superseded by `target_ids` and `target_key` in the new action schema.
- `FileExecutor` implements the `Executor` protocol. It accepts a `paths` argument providing the `ai/` directory location (consistent with the existing `BalatroPaths` pattern). It writes `action.json` atomically, polls for its deletion or the appearance of `action_error.json`, and raises `ExecutorError` if an error file is found.
- `FileExecutor` exposes a configurable poll interval and timeout so that tests can run at low latency and production use can tolerate slow game frames.
- The `Executor` protocol signature (`execute(action: GameAction) -> None`) is not changed. `FileExecutor` serializes a single `GameAction` as a one-item queue. A companion `FileExecutor.execute_sequence(actions: list[GameAction])` method accepts a pre-built queue for callers that want to commit a full sequence atomically. The runtime loop continues to call `execute` for single actions; the sequence method is available for future policy upgrades.
- The `ai_executor` Lua mod is a new mod that loads independently of `live_state_exporter`. It hooks into `love.update` (or equivalent) to poll for `action.json` on each frame.
- The Lua executor checks for the existence of `action.json` at the start of each frame. If absent, it does nothing. If present and not already processing, it reads and parses the file, then begins processing the queue via `G.E_MANAGER:add_event`.
- The Lua executor uses a single completion event at the end of the queue that deletes `action.json` via `love.filesystem.remove`. On error, it writes `action_error.json` and stops queue processing without deleting `action.json`.
- The `live_state_exporter` is modified to check for the existence of `action.json` before each write cycle. If the file exists, the write is skipped entirely. The exporter resumes writing on the next tick after `action.json` is no longer present. This guarantees that `live_state.json` is only ever written in a stable post-action state.
- The deduplication logic in `live_state_exporter` is removed once the action-gated write cycle is confirmed to be working. No deduplication is needed if the exporter only writes after actions complete.
- Reordering is implemented by directly building a new ordered table from the desired `order` instance ID sequence, assigning it to `CardArea.cards`, and calling the appropriate redraw or sort function on the `CardArea`. If an instance ID in the `order` array does not match any card in the target area, the executor writes an error file rather than performing a partial reorder.
- The reorder implementation for jokers targets `G.jokers.cards`. The reorder implementation for hand cards targets `G.hand.cards`. Both follow the same array-rebuild pattern.
- All file writes in both the Python and Lua sides use atomic rename where the platform supports it. On Windows this means write-to-temp then `MoveFileEx` (Python) and `love.filesystem` temp-rename (Lua).
- The `ai/` directory path is resolved through `BalatroPaths` on the Python side. The Lua side uses the same path convention already established by `live_state_exporter`.
- The `Executor` protocol is not changed. The `EpisodeRunner` is not changed. The `Validator` boundary is not changed.

## Testing Decisions

- Good tests for this feature verify observable behavior at the file channel boundary and the `Executor` protocol boundary. They do not test Lua internals directly or depend on a running game.
- `FileExecutor` should be tested with a real temporary filesystem directory. Tests should cover: correct JSON structure of the written file for each action kind, correct polling termination when the file is deleted, correct exception raising when an error file appears, and correct timeout behavior.
- `ActionKind` constants should be tested to verify that every constant round-trips through JSON serialization without mutation.
- `GameAction` serialization should be tested for every action kind: fields are present, `target_ids` and `order` serialize as arrays of integers, `target_key` serializes as string or null.
- The exporter gate behavior should be tested at the unit level by confirming that the write-skip logic fires when the action file path exists and does not fire when it does not.
- Reorder logic should be tested independently of the rest of the Lua executor: given a known card table and a desired order, verify the resulting table matches and that a missing instance ID produces the expected error path.
- Lua-side tests follow the same patterns already established in `tests/exporter/` — use the game's Lua test runner with a mock `G` global.
- There are no game-in-the-loop integration tests. The boundary is the file channel; tests verify both sides of the boundary independently.
- Prior art for the Python side: `tests/smoke/observation/` and `tests/smoke/runtime/` show the pattern for testing protocol-boundary behavior with minimal scaffolding.
- Prior art for the Lua side: `tests/exporter/` shows the pattern for testing collectors and schema logic against a mock `G` table.

## Out of Scope

- The RunAgent: long-term LLM-based reasoning that coordinates across a full run. This PRD builds the execution layer that a future RunAgent will depend on, not the RunAgent itself.
- Domain subagents (HandAgent, ShopAgent, BlindAgent, PackAgent) and any tick-based coordination architecture above the executor.
- Changes to `DemoPolicy` or `RuleBasedValidator`. The existing policy and validator continue to work as before; this PRD adds a real executor underneath them.
- Any expansion of `GameObservation` or the observation layer. The current observation contract is sufficient to express all actions in this PRD.
- Mouse and keyboard automation. This approach is explicitly replaced by the file-bridge.
- Network-based communication between Python and Lua. The file channel is the intended long-term boundary for local use.
- Multi-instance or concurrent AI control.
- Windows UAC or permission hardening for the `ai/` directory.
- Action replay or logging of executed action sequences beyond what the existing `StepRecord` mechanism already captures.

## Further Notes

- The "telepathic" framing captures the design intent: the AI does not simulate user input, it speaks directly to the game's internal logic using the game's own APIs. This distinction matters for robustness — screen layout changes, resolution differences, and animation timing do not affect execution.
- The key insight enabling this design is that `card.ID` in Lua is identical to `instance_id` in `GameObservation`. The observation layer already exports stable object identifiers; the executor layer just needs to use them as a lookup key.
- The action-gated exporter is a meaningful semantic improvement beyond mere performance. It establishes a clean causal model: Python writes a plan, the game executes it, the game writes the result. Observations are always post-action. Plans are always pre-observation. The loop has a defined direction.
- Reordering is genuinely harder than the other actions because `CardArea:sort()` only supports preset orderings. Direct table manipulation is required. The implementation should verify that after rearranging `CardArea.cards`, any necessary display refresh is triggered so the game renders the new order correctly. This may require calling `CardArea:parse_highlighted()` or equivalent after the reorder to resync the UI.
- The `execute_sequence` method on `FileExecutor` is the natural entry point for future policy upgrades that want to commit a full turn plan atomically — for example, select two cards, play them, then use a Planet card on the resulting scored hand type. Single-action `execute` remains correct for the current `EpisodeRunner` without any runtime changes.
- The error halt-on-first-failure policy means the Lua executor never partially applies a sequence. If the Python-side validator is thorough, errors in production should be rare. During development they will surface real gaps in the validator's phase and affordability checks, which is the desired behavior.
- Acceptance criteria for this PRD:
  - A Python policy running under `EpisodeRunner` can play a real game of Balatro to completion without any mouse or keyboard input.
  - Every valid `ActionKind` constant has a working Lua handler in `ai_executor`.
  - `live_state.json` is never written while `action.json` is present.
  - `live_state.json` is written exactly once after each action queue completes.
  - Deduplication logic is removed from `live_state_exporter`.
  - Reorder actions correctly rearrange both joker slots and hand cards to the declared order.
  - `FileExecutor` raises `ExecutorError` on error file detection and returns cleanly on file deletion.
  - Tests cover the Python file-channel boundary and the Lua reorder logic independently of a running game.

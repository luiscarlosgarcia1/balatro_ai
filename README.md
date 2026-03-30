# balatro_ai

Build a Balatro agent that can play faster and better than a human while also serving as a sandbox for practical AI engineering workflows like delegated coding tasks, agentic workflows, skills, validation, and experiment logging.

## Project Goals

This project still has the same two goals:

1. Build a real Balatro-playing agent.
2. Practice common AI engineering patterns while building it.

The second goal is about how we develop the codebase, not about turning the in-game player into a multi-agent system.

## AI Workflow Goal

This repo is also meant to be a good place to practice coding-agent workflows:

- clean module boundaries
- delegated implementation
- validation and review loops
- deterministic local harnesses for testing changes

## Current Architecture

The starter scaffold is organized around a typed single-policy loop:

1. `BalatroObserver` reads `AppData/Roaming/Balatro/ai/live_state.json`.
2. `Policy` proposes the next action.
3. `Validator` checks whether the action is acceptable.
4. `Executor` performs the action.
5. `Runtime` logs the result and advances the episode.

The in-process contract is `GameObservation`, so JSON exists only at the Lua-to-Python handoff from the live exporter.

## Run The Demo

```bash
python main.py
```

## Live Observation Flow

- Install the mod in [mods/live_state_exporter](c:/Users/luiga/OneDrive/Documentos/balatro_ai/mods/live_state_exporter/README.md).
- Launch Balatro so the mod writes `AppData/Roaming/Balatro/ai/live_state.json`.
- Use `BalatroObserver` in Python code to parse that file into `GameObservation`.

## Current State

The project now has a typed live-observer core:

- a live exporter mod that writes `AppData/Roaming/Balatro/ai/live_state.json`
- a Python parser that converts the exporter payload into `GameObservation`
- a runtime loop that passes typed observations through observer, policy, validator, and step recording
- smoke coverage around the public observer surface, live parsing, and typed runtime flow

## Next Work

The highest-value next steps are:

1. Expand the live exporter so it covers more of the shop, jokers, consumables, and selection state.
2. Improve runtime decision quality on top of the typed observation contract.
3. Add executor automation that can safely act on validated `GameAction` output.
4. Keep tightening module boundaries so delegated work stays easy to reason about.

## Observation

### Features

- reads structured Balatro state from the live exporter handoff
- parses core run state like money, blind, score, hands, discards, and card counts
- exposes typed gameplay data through `GameObservation`
- keeps runtime, policy, and validator on the same typed contract

### Limitations

- the live exporter is still an initial scaffold and may need hook adjustments depending on how Balatro and Steamodded update
- observer coverage is still incomplete for some crowded or highly dynamic game state

### To-Do

- runtime-verify the live exporter inside a real Balatro session
- expand state coverage for shop, consumables, selections, and other cluttered UI details
- add a smarter event-driven observe-after-action loop instead of relying only on steady polling
- add tests around the parser and live-export contract

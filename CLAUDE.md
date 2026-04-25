# balatro_ai project context for Claude

> Read this first before exploring the repo.
> Update this file when architecture, entrypoints, branches, or verification materially change.

## What this repo is now

This repo has two implemented halves:

- a typed live-observation stack, which is the mainline architecture
- a file-channel execution bridge, which is real and tested but not the default top-level runtime path

Do not treat it as a finished autonomous player. The current truth is:

1. Lua exports live Balatro state to `ai/live_state.json`.
2. Python parses that into typed `GameObservation`.
3. Python has an observer -> policy -> validator -> executor seam.
4. Python can also write `ai/action.json`, and the Lua executor mod can consume it.
5. `main.py` still runs a scripted demo runtime with `LoggingExecutor`, not a live end-to-end in-game loop.

## Branch picture

- `observer` is the old observer refactor branch; it is now stale, fully absorbed into `main`, and behind it.
- `main` is the current integrated baseline for the typed observer/exporter architecture.
- `policy` is really an intermediate executor checkpoint branch, not the best place for new work.
- `executor` contains all `policy` commits plus the later action-execution work and is the only branch meaningfully ahead of `main`.
- If future observer work resumes, branch from `main`, not from the stale `observer` branch.

## Current architecture

Primary path:
`mods/live_state_exporter/` -> `ai/live_state.json` -> `BalatroObserver` -> `LiveObservationParser` -> `GameObservation`

Secondary path:
`GameAction` -> `FileExecutor` -> `ai/action.json` -> `mods/ai_executor/` -> in-game handler dispatch

Top-level scripts:

- `main.py`: runs `balatro_ai.demo_runtime.main()` with scripted observations and `LoggingExecutor`
- `pretty_printer.py`: reads the real live observation and writes a dataclass tree into `prints/`

## Python package map

- `balatro_ai/models.py`: frozen dataclasses; `GameObservation` is the canonical in-process observation contract
- `balatro_ai/interfaces.py`: `Observer`, `Policy`, `Validator`, `Executor` protocols
- `balatro_ai/runtime.py`: `EpisodeRunner`, the simple runtime loop
- `balatro_ai/policy.py`: `DemoPolicy`, `RuleBasedValidator`, `infer_phase()`; seam exercise, not strong gameplay logic
- `balatro_ai/demo_runtime.py`: scripted observations plus `LoggingExecutor`
- `balatro_ai/observation/paths.py`: `BalatroPaths` with the default Windows `%AppData%\\Roaming\\Balatro` root
- `balatro_ai/observation/service.py`: `BalatroObserver`; raises `FileNotFoundError` or `ValueError` on missing/invalid live state
- `balatro_ai/observation/parser/live_parser.py`: exporter JSON -> `GameObservation`
- `balatro_ai/observation/parser/zones.py`: cards, jokers, consumables, vouchers, blinds, tags, selected references
- `balatro_ai/observation/parser/run_state.py`: interest, run-hand, and pack-content parsing
- `balatro_ai/observation/parser/shop.py`: shop item parsing plus voucher merge logic
- `balatro_ai/observation/README.md`: authoritative typed-first/live-first guardrails
- `balatro_ai/action_kind.py`: string constants for the file-channel action protocol
- `balatro_ai/executor/file_executor.py`: writes `action.json` atomically and waits for deletion or `action_error.json`

## Lua mods

- `mods/live_state_exporter/main.lua`: hooks `love.update` or `Game.update`, ticks exporter and probe safely
- `mods/live_state_exporter/state/raw.lua`: reads live state from `G`, collectors, and phase inference
- `mods/live_state_exporter/state/schema.lua`: shapes collector output into canonical JSON-ready state
- `mods/live_state_exporter/collectors/`: split into `run_state.lua`, `zones.lua`, and `market.lua`
- `mods/live_state_exporter/probe.lua`: writes `ai/live_state_probe.json` and dedupes unchanged debug payloads
- `mods/ai_executor/main.lua`: hooks update and wires filesystem plus event-manager deps into the executor
- `mods/ai_executor/executor.lua`: polls for `ai/action.json`, decodes queues, schedules events, and signals completion/failure
- `mods/ai_executor/handlers.lua`: Balatro-specific action dispatch and actionable-state checks

## File-channel protocol

Files under `%USERPROFILE%\\AppData\\Roaming\\Balatro\\ai\\`:

- `live_state.json`: written by `live_state_exporter`, read by `BalatroObserver`
- `live_state_probe.json`: written by `probe.lua` for debug snapshots
- `action.json`: written by Python `FileExecutor`, deleted by the Lua executor on success
- `action_error.json`: written by the Lua executor on failure

`action.json` shape:
`{"actions":[{"kind":"play_hand","target_ids":[14762],"target_key":null,"order":[]}]}`

Important nuance:

- observation is typed-first inside Python; do not reintroduce dict-first flows
- execution is still JSON/file based
- `GameAction.target_ids` and `order` are bridge-facing fields
- `GameAction.target` serializes as `target_key`

## Working assumptions

- The mainline architecture is the typed observer pipeline, not the executor bridge by itself.
- The demo runtime is not wired to the real live exporter or executor.
- Older PRDs do not automatically describe the exact current code; prefer current source plus `balatro_ai/observation/README.md`.
- There are no declared third-party Python dependencies right now.
- Windows is the default environment because `BalatroPaths` targets `%AppData%\\Roaming\\Balatro`.

## Tests and verification

Verified on 2026-04-25 from the project root:

- `python -m unittest discover -s tests -p "test*.py" -v` passed with 39 tests
- `Get-ChildItem tests\exporter\test_*.lua | ForEach-Object { lua $_.FullName }` passed
- `Get-ChildItem tests\ai_executor\test_*.lua | ForEach-Object { lua $_.FullName }` passed
- Toolchain used: Python 3.14.3, Lua 5.4.6

## Where to look first

- typed observation changes: `balatro_ai/models.py`, `balatro_ai/observation/parser/`, `mods/live_state_exporter/`, `tests/smoke/observation/`
- runtime seam changes: `balatro_ai/interfaces.py`, `balatro_ai/runtime.py`, `balatro_ai/policy.py`, `tests/smoke/runtime/`
- file-channel execution changes: `balatro_ai/action_kind.py`, `balatro_ai/executor/file_executor.py`, `mods/ai_executor/`, `tests/ai_executor/`
- docs and planning context: `README.md`, `docs/README.md`, `docs/prds/`, this file

## Gaps worth remembering

- There is still no single production entrypoint wiring live observation, policy, validation, and `FileExecutor` together.
- The policy layer is intentionally lightweight and not a serious Balatro strategy engine yet.
- The repo has stronger observation and action-transport infrastructure than decision quality.
- Earlier docs sometimes overstated the executor branch as the whole project story; that is no longer the best summary.

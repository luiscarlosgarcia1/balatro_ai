# balatro_ai

`balatro_ai` is a Balatro agent project and an AI-engineering sandbox built in the open at the same time.

The repository is not a finished autonomous player yet. Its current center of gravity is a typed live-observation pipeline: a Steamodded Lua exporter writes canonical game state, Python parses that handoff into `GameObservation`, and a small runtime layer exercises policy and validation boundaries on top of that typed model.

The action-execution bridge also exists in-tree. A Python `FileExecutor` can write `ai/action.json`, and the `mods/ai_executor/` Steamodded mod can consume that queue in-game. That bridge is implemented and tested, but it is not the default top-level runtime entrypoint yet.

## Current Repo State

- `mods/live_state_exporter/` writes canonical live state to `%USERPROFILE%\\AppData\\Roaming\\Balatro\\ai\\live_state.json`.
- `balatro_ai.observation` exposes a public `BalatroObserver` API backed by a typed `LiveObservationParser`.
- `balatro_ai/models.py` defines the frozen dataclass contract used inside Python, centered on `GameObservation`.
- `balatro_ai/runtime.py`, `balatro_ai/policy.py`, and `balatro_ai/interfaces.py` provide the current observer -> policy -> validator -> executor seam.
- `main.py` runs a local scripted demo loop, not a live in-game agent.
- `pretty_printer.py` reads the latest live observation and writes a readable dataclass-tree dump into `prints/`.
- `balatro_ai/executor/file_executor.py` and `mods/ai_executor/` provide the file-channel execution path for future end-to-end play.
- The repo currently has no third-party Python dependencies declared.

Verified locally on 2026-04-25:

- Python 3.14.3
- Lua 5.4.6
- `python -m unittest discover -s tests -p "test*.py" -v` passed with 39 tests
- All `tests/exporter/test_*.lua` scripts passed
- All `tests/ai_executor/test_*.lua` scripts passed

## Architecture

### Live observation path

1. `mods/live_state_exporter/` reads Balatro runtime state from `G`.
2. The exporter shapes that data into a canonical JSON payload and writes `ai/live_state.json`.
3. `BalatroObserver` reads the file through `BalatroPaths`.
4. `LiveObservationParser` converts the payload into typed Python dataclasses.
5. Runtime, policy, validation, and debug tools operate on `GameObservation`, not raw dicts.

### Execution path that already exists

1. Python creates a `GameAction`.
2. `FileExecutor` serializes one or more actions into `ai/action.json`.
3. `mods/ai_executor/` polls that file from inside the game and dispatches handlers against Balatro APIs.
4. The Lua mod deletes `action.json` on success or writes `ai/action_error.json` on failure.

### Important current gap

The repo has both sides of the bridge, but the default entrypoint is still the demo runtime in `main.py`. There is not yet a single top-level script that observes the live game, chooses actions, validates them, and sends them through `FileExecutor` in one integrated production loop.

## Getting Started

### Prerequisites

- Python 3.14 was used for the latest local verification
- Lua 5.4 if you want to run the Lua test scripts directly
- Balatro with Steamodded if you want live in-game observation or execution
- Windows if you want the default `%AppData%\\Roaming\\Balatro` path without overrides

### Installation

```powershell
git clone <repo-url>
cd balatro_ai
```

No dependency installation step is currently required for the Python package.

For live observation, install `mods/live_state_exporter/` into your Steamodded setup.

For action execution, also install `mods/ai_executor/`.

### Default paths

By default, Python looks for the exporter output at:

```text
%USERPROFILE%\AppData\Roaming\Balatro\ai\live_state.json
```

That path comes from `BalatroPaths`. If you want to point the observer at another Balatro root:

```python
from pathlib import Path

from balatro_ai import BalatroObserver, BalatroPaths

observer = BalatroObserver(paths=BalatroPaths(root=Path(r"C:\path\to\Balatro")))
observation = observer.observe()
```

## Common Commands

Run the local scripted runtime:

```powershell
python main.py
```

Read the latest live observation and write a readable printout:

```powershell
python pretty_printer.py
```

Run the Python test suite:

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

Run the exporter Lua tests from the project root:

```powershell
Get-ChildItem tests\exporter\test_*.lua | ForEach-Object { lua $_.FullName }
```

Run the AI executor Lua tests from the project root:

```powershell
Get-ChildItem tests\ai_executor\test_*.lua | ForEach-Object { lua $_.FullName }
```

## Project Structure

- `balatro_ai/`
  Python package holding the typed models, observer service, parser modules, runtime, policy, interfaces, and file executor.
- `mods/live_state_exporter/`
  Steamodded Lua mod that exports canonical Balatro state to `ai/live_state.json`.
- `mods/ai_executor/`
  Steamodded Lua mod that reads `ai/action.json` and executes queued actions in-game.
- `tests/smoke/`
  Python smoke coverage for parser behavior, public imports, pretty printing, and typed runtime flow.
- `tests/ai_executor/`
  Python tests for the action contract and `FileExecutor`, plus Lua tests for the in-game executor mod.
- `tests/exporter/`
  Lua tests for exporter shaping, collectors, probes, schema defaults, and write behavior.
- `prints/`
  Human-readable observation dumps written by `pretty_printer.py`.
- `docs/prds/`
  PRDs and plans for the observer, exporter, mod refactor, and executor work.
- `WORKFLOW.md`
  Notes on how the repo approaches coding-agent collaboration and module boundaries.

## Practical Notes

- The observation architecture is typed-first inside Python. JSON is only the Lua-to-Python ingress boundary.
- `balatro_ai/observation/README.md` is the best guardrail doc for the observation package.
- `CLAUDE.md` is the fast-start context file for coding agents working in this repo.
- The current demo policy is intentionally tiny. It exists to exercise the seam, not to play Balatro well.
- The execution bridge is more concrete than the policy layer right now, so avoid assuming the top-level app is further along than it is.

## Near-Term Direction

- Wire the typed observer/runtime seam to the real `FileExecutor` for a genuine live loop.
- Strengthen the policy layer on top of the richer `GameObservation` contract.
- Continue extending exporter coverage for interaction-heavy states while keeping the typed boundary clean.
- Keep tests focused on surviving contracts instead of preserving old transitional structure.

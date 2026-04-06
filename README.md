# balatro_ai

## Project Overview

`balatro_ai` is a Balatro-playing agent project and an AI-engineering sandbox built in the open at the same time.

The two core goals of the project have not changed:

- Build a real Balatro agent that can eventually play faster and better than a human.
- Practice practical AI engineering patterns while building it: clean boundaries, delegated work, validation loops, and testable local workflows.

Today, the repo is centered on a typed live-observation pipeline rather than a finished bot. The current system can export live game state from a Balatro mod, parse it into Python, and run that state through a typed observer/policy/validator/runtime seam.

### Current features

- A Lua mod in `mods/live_state_exporter/` that writes canonical live state to `AppData/Roaming/Balatro/ai/live_state.json`
- A typed Python observation boundary built around `GameObservation`
- A public `BalatroObserver` API for reading and parsing the live handoff file
- A small runtime loop with explicit `Observer`, `Policy`, `Validator`, and `Executor` boundaries
- A demo runtime for exercising the typed loop without the game
- A readable observation printer that writes snapshots into `prints/`
- Smoke coverage for live parsing, public imports, pretty printing, and typed runtime flow

## Getting Started

### Prerequisites

- Python 3.10+ for the Python codebase
- Balatro with Steamodded if you want live in-game observation
- A Windows environment if you want the default `AppData/Roaming/Balatro` path to work without overrides

### Installation

```bash
git clone <repo-url>
cd balatro_ai
```

No third-party Python dependencies are declared in the repo today. The current Python workflow uses the standard library test runner.

For live observation, install the Balatro mod from `mods/live_state_exporter/` into your Steamodded setup so Balatro can write `ai/live_state.json`.

### Configuration

There are no environment variables to set right now.

By default, the observer reads:

```text
%USERPROFILE%\AppData\Roaming\Balatro\ai\live_state.json
```

That path comes from `BalatroPaths`. If you need a different root, override it in code:

```python
from pathlib import Path

from balatro_ai import BalatroObserver, BalatroPaths

observer = BalatroObserver(paths=BalatroPaths(root=Path(r"C:\path\to\Balatro")))
observation = observer.observe()
```

### Troubleshooting

- If `BalatroObserver` raises `FileNotFoundError`, Balatro has not written `ai/live_state.json` yet.
- If `BalatroObserver` raises `ValueError`, the file exists but the payload does not match the current live parser.
- If you only want to exercise the architecture without running the game, use the demo runtime in `main.py`.

## Running the Project

### Usage

Run the local typed demo loop:

```bash
python main.py
```

Read the latest live observation from Balatro and write a readable printout:

```bash
python pretty_printer.py
```

Run the Python smoke suite:

```bash
python -m unittest discover -s tests -p "test*.py" -v
```

### Scripts and commands

- `python main.py`
  Runs the scripted demo runtime built around `EpisodeRunner`, `DemoPolicy`, and `RuleBasedValidator`.
- `python pretty_printer.py`
  Reads the live observation through `BalatroObserver` and writes a readable dataclass tree into `prints/`.
- `python -m unittest discover -s tests -p "test*.py" -v`
  Runs the current Python smoke suite.

## Project Structure

- `balatro_ai/`
  Main Python package. Holds the typed models, interfaces, observer service, parser modules, policy, runtime, and demo runtime.
- `mods/live_state_exporter/`
  Steamodded Lua mod that exports canonical Balatro state into `ai/live_state.json`.
- `tests/smoke/`
  Python smoke tests protecting the surviving typed observer and runtime boundaries.
- `tests/exporter/`
  Lua-side tests for exporter modules, schema shaping, collectors, and write behavior.
- `prints/`
  Human-readable observation dumps written by `pretty_printer.py`.
- `docs/prds/`
  PRDs, plans, and follow-up notes for the observer/exporter work that shaped the current architecture.
- `WORKFLOW.md`
  Notes on how the repo approaches coding-agent collaboration and delegation boundaries.

## Next Steps

- Build a stronger policy and knowledge layer on top of `GameObservation` before spending real effort on UI automation.
- Expand runtime-verified observation coverage for crowded game state such as shop details, modifiers, and interaction-heavy zones.
- Add a real execution boundary after the decision loop is stronger, ideally through direct in-game actions rather than fragile pixel clicking.
- Keep tightening tests and module boundaries so future delegated work stays easy to verify.

## Collaboration

### Contributing

- Keep changes grounded in the typed live-observer architecture.
- Prefer small, reviewable slices over broad rewrites.
- Run `python -m unittest discover -s tests -p "test*.py" -v` before closing work.
- Treat `GameObservation` as the in-process contract and avoid reintroducing dict-first or save-first flows.

### Credits

- Built around Balatro as the target game.
- Uses a Steamodded Lua mod as the live observation ingress.
- Shaped by the repo's PRD-driven workflow in `docs/prds/`.

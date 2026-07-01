# Balatro AI Restart Workspace

This repository is trimmed back to the pieces needed for a fresh restart:

- `balatro-gym/` contains the Python Balatro game implementation, Gymnasium environment, tests, and the shared action/observation contract.
- `balatrobot/` is preserved as-is and should be treated as the real-game bridge source of truth.
- `Balatro Unpacked/` is preserved as-is.

No training code, model checkpoints, experiment logs, or generated run outputs are part of the cleaned working tree.

## Active Python Package

The maintained package is `balatro-gym`.

Important contract files:

- `balatro-gym/balatro_gym/core/constants.py` defines canonical phase IDs, action IDs, action counts, and direct play-subset encoding helpers.
- `balatro-gym/balatro_gym/core_utils/mvp_contract.py` defines the observation space, token encoders, and action-mask rules shared by the Python environment and live adapter.
- `balatro-gym/balatro_gym/core_utils/action_handler.py` validates sim actions against the contract.
- `balatro-gym/balatro_gym/core_utils/observation_builder.py` emits contract-shaped observations from Python game state.
- `balatro-gym/balatro_gym/environments/live/balatro_live_env.py` adapts `balatrobot` game state/actions to the same Gym contract without modifying `balatrobot`.

## Setup

```bash
cd balatro-gym
poetry install
```

Or with pip:

```bash
cd balatro-gym
python -m pip install -e . pytest
```

## Test

```bash
cd balatro-gym
poetry run pytest
```

The kept tests focus on the Python game implementation and the shared action/interface contract. Live-process smoke tests and model-training tests were removed with the training stack.

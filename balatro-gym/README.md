# Balatro Gym

`balatro-gym` contains the maintained Python implementation of Balatro gameplay plus a Gymnasium environment.

The package is intentionally focused on game simulation and the shared interface contract. Training loops, bot policies, checkpoint runners, generated trajectories, logs, and model artifacts have been removed.

## Key Modules

- `balatro_gym/core/`: cards, jokers, consumables, shop, boss blinds, and game primitives.
- `balatro_gym/core_utils/`: unified game state, phase handlers, observation building, action validation, RNG, and the shared MVP contract.
- `balatro_gym/scoring/`: scoring engines and joker effects.
- `balatro_gym/environments/balatro_env_small.py`: maintained Gymnasium environment for the Python implementation.
- `balatro_gym/environments/live/balatro_live_env.py`: adapter that maps `balatrobot` live game state/actions onto the same contract.

## Install

```bash
poetry install
```

Or:

```bash
python -m pip install -e . pytest
```

## Run Tests

```bash
poetry run pytest
```

## Contract Surface

The canonical action and observation contract lives in:

- `balatro_gym/core/constants.py`
- `balatro_gym/core_utils/mvp_contract.py`

Keep these stable when changing the Python environment or live adapter.

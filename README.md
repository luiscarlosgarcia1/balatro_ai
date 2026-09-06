# Balatro AI Restart Workspace

This repository is trimmed back to the pieces needed for a fresh restart:

- `balatro-gym/` contains the maintained Round Tactics live-environment adapter and its contract tests.
- `balatrobot/` is preserved as-is and should be treated as the real-game bridge source of truth.
- `Balatro Unpacked/` is preserved as-is.

No training code, model checkpoints, experiment logs, or generated run outputs are part of the cleaned working tree.

## Active Python Package

The maintained package is `balatro-gym`.

The initial public contract is
`balatro_gym.environments.live.RoundTacticsEnvironment.reset(seed)`. It drives
BalatroBot through a seeded Red Deck / White Stake first Small Blind and returns
a versioned, shop-free settled observation plus its canonical legal-action mask.

## Setup

```bash
cd balatro-gym
uv sync --group test
```

Or with pip:

```bash
cd balatro-gym
python -m pip install -e . pytest
```

## Test

```bash
cd balatro-gym
uv run pytest
```

The kept tests focus on the live adapter's public action/observation contract.

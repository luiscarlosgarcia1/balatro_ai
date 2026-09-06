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

## Replaceable policy and optimizer boundaries

Round Tactics deliberately separates game behavior from learning experiments.
A replacement must use these published boundaries without changing their rules:

- A policy implements `Policy.select_action(observation, legal_action_mask)` and
  returns the exact `LegalAction` instance supplied by the current mask. It must
  make deterministic selections for the same observation and mask, including any
  tie-breaking it owns. Policies do not call the live bridge or alter episode
  lifecycle semantics.
- An optimizer trains or selects a policy only by invoking an `EpisodeRunner`
  with that policy and a manifest seed. It must keep all selection and tuning on
  the manifest's development seeds. The optimizer is independent of the
  Round Tactics adapter and may be replaced without changing the adapter.
- `Benchmark.evaluate(policy, manifest, episode_runner)` remains the only
  benchmark boundary. The manifest version and seed partitions, baseline
  comparison, held-out gate, one-use held-out policy-revision rule, scorecards,
  paired bootstrap analysis, and improvement criterion are fixed by
  `Benchmark`; replacements cannot weaken or reinterpret them.

Policies and optimizers therefore need reproducible revisions and deterministic
seed handling, but this interface does not prescribe a production learner,
model format, or training system. The substitution conformance test exercises a
second policy and development-only optimizer through the same live-environment
episode, manifest, and benchmark seams used by the CEM slice.

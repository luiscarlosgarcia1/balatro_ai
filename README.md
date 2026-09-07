# Balatro AI Restart Workspace

This repository is trimmed back to the pieces needed for a fresh restart:

- `balatro-gym/` contains the maintained Round Tactics live-environment adapter and its contract tests.
- `balatrobot-main/` is preserved as-is and should be treated as the real-game bridge source of truth.
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

## Run the package

After setup, run the remaining commands from `balatro-gym/`.

### Checks

Run the whole contract suite:

```bash
uv run pytest
```

Run the focused suites while working on a surface:

```bash
uv run pytest tests/test_cli.py -q
uv run pytest tests/test_watchable_session.py -q
uv run pytest tests/test_round_tactics_reset.py tests/test_round_tactics_step.py -q
```

The project also has a `ty` configuration. When `ty` is installed in the
environment, run its type check with:

```bash
uv run ty check
```

### CLI

Show the available commands:

```bash
uv run balatro-gym --help
# Equivalent module form:
uv run python -m balatro_gym --help
```

Run one visible, seeded Red Deck / White Stake first Small Blind:

```bash
uv run balatro-gym watch --seed BAL9SEED
```

Add `--keep-open` to leave the Balatro window open after the blind settles;
press <kbd>Ctrl</kbd>+<kbd>C</kbd> to finish cleanup:

```bash
uv run balatro-gym watch --seed BAL9SEED --keep-open
```

`watch` writes lifecycle events as JSON Lines to standard output and sends
human-readable diagnostics (including help and failures) to standard error.
This makes it safe to retain a machine-readable trace while still seeing
diagnostics in the terminal:

```bash
mkdir -p ../.local/acceptance-traces
uv run balatro-gym watch --seed BAL9SEED \
  > ../.local/acceptance-traces/BAL9SEED.jsonl
```

`../.local/acceptance-traces/` is ignored by Git and is the intended location
for local acceptance traces. Do not commit captures from a specific local game
installation.

The watch command launches and owns a real Balatro instance through
BalatroBot. It therefore needs a working local BalatroBot installation and a
real game setup; the test commands above use fakes and do not need either.
Install the checked-in bridge package into this project's environment first:

```bash
uv pip install -e ../balatrobot-main
```

Set these optional BalatroBot configuration variables when its defaults do not
find your installation:

```bash
export BALATROBOT_BALATRO_PATH="/path/to/Balatro"
export BALATROBOT_LOVELY_PATH="/path/to/lovely"
export BALATROBOT_LOVE_PATH="/path/to/love"
export BALATROBOT_PLATFORM="macos"
export BALATROBOT_LOGS_PATH="logs"
```

Refer to the [BalatroBot documentation](https://coder.github.io/balatrobot/)
for the required mod/game installation and platform-specific launcher setup.

### Real-installation acceptance checklist

Use this checklist after changing the real-game integration. Capture the trace
under `../.local/acceptance-traces/` if it will help diagnose a local failure.

1. Run `uv run balatro-gym watch --seed BAL9SEED`. Confirm that a visible
   Balatro window launches, begins the seeded first Small Blind, and closes
   after it settles. The command should exit with status `0`.
2. Inspect the trace. It should be JSONL and finish with a `settled` event;
   it should include lifecycle events such as `launching`, `bridge_ready`,
   `session_ready`, and one or more `action_applied` events. A `failed` event
   or a nonzero exit status indicates a runner failure; check stderr and the
   reported BalatroBot log path.
3. Run `uv run balatro-gym watch --seed BAL9SEED --keep-open`. After the blind
   settles, confirm that the window remains visible. Press
   <kbd>Ctrl</kbd>+<kbd>C</kbd>, then confirm the managed window closes and the
   command returns to the shell.
4. Repeat inspection mode and send `SIGTERM` from a second terminal to the
   `uv run balatro-gym ... --keep-open` process. Confirm that the managed
   window closes and the command exits cleanly. For example, start it in the
   background, record `$!`, then run `kill -TERM <pid>` and `wait <pid>`.

### Python API

`run_watchable_session` is the high-level API behind the CLI. It owns the
BalatroBot process and returns a terminal result instead of exiting the Python
process:

```bash
uv run python - <<'PY'
import sys

from balatro_gym import run_watchable_session

result = run_watchable_session("BAL9SEED", keep_open=False)
print(result, file=sys.stderr)
raise SystemExit(result.exit_code)
PY
```

For a custom policy or experiment, use `RoundTacticsEnvironment` with a live
BalatroBot-compatible bridge. `reset` returns both a settled observation and
the canonical legal-action mask; pass the exact action instance from that mask
to `step`:

```python
from balatrobot import BalatroClient
from balatro_gym import RoundTacticsEnvironment

bridge = BalatroClient(port=port)  # A running BalatroBot instance.
environment = RoundTacticsEnvironment(bridge)
reset = environment.reset("BAL9SEED")
observation = reset.observation
action = reset.legal_action_mask[0]
next_step = environment.step(action)
```

Do not rebuild `LegalAction` values yourself: an action is valid only for the
current mask returned by the environment. Continue choosing actions from each
non-terminal `next_step.legal_action_mask` until `terminated` or `truncated`
is true.

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

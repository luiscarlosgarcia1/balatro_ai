# Next Steps

## Pipeline

```
Balatro (game)
  ↑
headless (pool.py — runs N Balatro instances)
  ↑
balatrobot (API — reads game state, sends actions) ← verify this is the game bridge
  ↑
balatro-gym (env — obs/reward/step interface)
  ↑
ppo (model)
```

---


## 1. Integration & Cleanup (do this first)

Clean up the four merged projects and wire them into a single pipeline:

```
headless (pool.py) → balatro-gym (env) → balatrobot (API/game state) → ppo (model)
```

- Remove duplicate files and dead code across `balatro-gym`, `balatrobot`, `headless`, and `ppo`
- Define clear boundaries: what each module owns and what it exposes
- Establish a single entry point for training (one `train.py` that calls into all four)
- Ensure the gym env talks to balatrobot through a stable interface, not ad-hoc imports
- Confirm the headless pool is actually invoked by the gym env (not running standalone)
- Wire multi-instance parallelism — pool exists but rollout collection across parallel instances is not connected to the gym env

---

## 2. Missing / Incomplete

- **Reward shaping** — Balatro's win/lose signals are too sparse for PPO to learn from efficiently. Add intermediate rewards: chips scored per hand, gold earned, hand level-ups, blind clears. No hardcoded joker synergies — let the model discover those.

- **Checkpoint + resume** — Save/load model weights AND optimizer state so training survives crashes and can be resumed mid-run.

- **Evaluation harness** — Separate eval loop running greedy policy (no exploration noise). Tracks win rate per ante over time, decoupled from training rollouts.

- **Action masking** — Balatro has many state-dependent invalid actions (e.g. discard when 0 discards remain). Masking these out prevents PPO from wasting capacity on illegal moves.

- **Logging / metrics pipeline** — TensorBoard or W&B tracking: episode return, entropy, value loss, KL divergence, win rate per ante.

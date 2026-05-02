# Next Steps

## Pipeline

```
Balatro (game)
  ↑
balatrobot (API — reads game state, sends actions) ← verify this is the game bridge
  ↑
balatro-gym (env — obs/reward/step interface)
  ↑
ppo (model)
```

---

## Deferred Observation Stubs

These keys were declared in the `balatro_env_2.py` observation space but never implemented. They were removed to unblock training. Implement them later once there is a stable baseline and evidence the agent is struggling from lack of information.

### Hand Analysis
`rank_counts`, `suit_counts`, `flush_potential`, `straight_potential`, `hand_one_hot`, `hand_suits`, `hand_ranks`, `hand_potential_scores`

**What:** Derived features about the current hand — how many of each rank/suit, probability of completing a straight or flush, expected score per hand type.

**Why:** Gives the agent structured signal about what hand to play instead of forcing it to infer everything from raw card indices. Should meaningfully speed up learning of card selection decisions.

**When:** After the agent shows it can learn the basic play loop (reliably playing hands, not discarding randomly). If card selection quality plateaus early, add these.

---

### Joker Synergy
`has_mult_jokers`, `has_chip_jokers`, `has_xmult_jokers`, `has_economy_jokers`, `joker_synergy_score`

**What:** Binary flags and a scalar score indicating what category of jokers the agent holds and how well they interact.

**Why:** Joker synergy is the core strategic layer of Balatro. Without this signal the agent has to discover synergies purely from reward, which is very slow given how sparse late-game rewards are.

**When:** After the agent reliably clears early antes. If it starts buying jokers randomly with no coherent build strategy, this is the missing signal.

---

### Risk / Economy Context
`avg_score_per_hand`, `risk_level`, `economy_health`, `blind_difficulty`, `win_probability`, `hands_until_shop`, `rounds_until_boss`

**What:** Scalars that summarize how dangerous the current situation is — how close to losing, how healthy the economy is, how far until the next shop or boss blind.

**Why:** Helps the agent make conservative vs. aggressive tradeoffs (e.g. save discards when a boss blind is next, spend money aggressively when economy is healthy). Hard to infer from raw game state alone.

**When:** Later-stage training, once the agent understands the basic economy loop. These matter most for ante 6+ decision quality.

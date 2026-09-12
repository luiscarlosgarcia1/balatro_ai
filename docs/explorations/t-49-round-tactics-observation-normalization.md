# T-49: Round Tactics observation normalization exploration

## Outcome: Defer

Do not introduce a new normalization module at the live bridge seam yet. The
direction could become valuable, but the required leverage is not present:
there is one live adapter, one observed bridge representation, and no recorded
recurring schema-change cost. Reassess after the first two exploration tickets,
or earlier if a second adapter or real payload variation arrives.

## Scope and evidence examined

The relevant domain term is **Round Tactics**: the maintained, shop-free
boundary that exposes settled observations and canonical legal actions. There
are no ADRs in this repository that constrain this area.

The live adapter, `balatro_gym/environments/live/round_tactics.py`, projects a
BalatroBot game state directly into `RoundTacticsObservation`. Its `hand`,
`poker_hands`, and `jokers` fields retain mapping-shaped bridge data.

BalatroBot is presently the only adapter. Its game-state extractor has one
canonical representation:

* Each card is an object whose playing-card facts live under `value`, including
  a compact rank and suit. (`balatrobot-main/src/lua/utils/gamestate.lua`.)
* Each poker-hand entry is an object with `level`, `chips`, `mult`, and related
  bridge data in a mapping keyed by its display name.
* Jokers use the same card object representation.

The two policies do need card facts, but they do not independently decode the
wire shape. `baseline.py` and `linear.py` both delegate rank, suit, chip, and
poker-category interpretation to the existing `policies/hand_evaluation.py`
module. That module contains the only tolerance for the alternate fixture
shorthand: a card may be supplied directly as `{rank, suit, ...}` rather than
the bridge-shaped `{value: {rank, suit, ...}}`. The shorthand is constructed in
`tests/test_baseline_policy.py`; the live bridge test support uses the canonical
`value` nesting. No production adapter emits the shorthand.

There is therefore one adapter and one production payload shape. The raw
interface leaks representation knowledge through its public types, but the
knowledge has good locality today: projection is at the live boundary and the
small amount of card interpretation is centralized in the hand-evaluation
implementation. `poker_hands` and `jokers` are currently read only where the
policies need their game facts; no policy-specific mapping decoder exists for
jokers.

## Depth and seam assessment

A prospective normalizer could expose typed cards and hand values, isolating
the bridge representation behind a deeper interface. But with a single client
and stable shape it would be a speculative seam: it adds a module and a public
model without reducing any demonstrated adapter or schema-change burden. It
would also need to preserve rank, suit, chip, and hand-level facts required by
the policies, so its interface would not be materially smaller merely by
hiding them.

The existing `hand_evaluation` module is a focused, relatively deep policy
implementation: it turns the small card facts into rank values, base chips,
and poker categories. It is not a live-bridge adapter and should not be moved
just to create a new layer.

## Deletion test

If a new observation-normalization module were removed today, the raw
card/poker-hand mapping complexity would redistribute to the live projection
and both policies (and their tests). That means a genuinely normalizing module
could pass the deletion test; it would not merely be a shallow forwarding
module. This proves that a future seam is conceivable, not that it has current
leverage. The necessary trigger remains absent: concrete payload variation, a
second adapter, or recurring schema-change friction.

## Reassessment triggers

Create a scoped implementation follow-up only when at least one of these is
observed:

1. BalatroBot emits more than one real card or poker-hand payload variation
   that Round Tactics must support.
2. A second live/replay/simulated adapter must produce the same Round Tactics
   interface.
3. A bridge schema change requires coordinated edits across projection,
   policy logic, and fixtures more than once.

At that point, evaluate a deep normalizer at the adapter seam whose interface
keeps the policy-required game facts while making the bridge shape private.

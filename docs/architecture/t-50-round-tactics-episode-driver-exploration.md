# T-50: Round Tactics episode-driver exploration

## Outcome: Implement

Create a scoped follow-up implementation ticket for one deep Round Tactics
episode-driving module at the existing `EpisodeRunner` seam. This exploration
does not make the refactor.

## Scope and evidence

`RoundTacticsEnvironment` already owns the live-bridge sequence and exposes a
settled `ResetResult` and `StepResult`. The remaining episode semantics are
currently split between two callers:

- `balatro_gym/watchable_session.py` resets the environment, repeatedly asks a
  policy to choose an action from the current legal-action mask, applies that
  action, verifies termination and truncation states, and maps a settled state
  to its visible outcome.
- `tests/test_substitution_conformance.py` independently resets, selects an
  action, steps, asserts terminal conditions, and constructs an
  `EpisodeOutcome` for its evaluator caller.

The test's one-step fixture does not duplicate the Watchable session's full
multi-step and truncation handling, but it independently owns the same
reset/select/step/terminal-to-outcome rule. More importantly, `evaluation.py`
already publishes `EpisodeRunner = Callable[[Policy, str], EpisodeOutcome]`,
and `Benchmark` and `CEMTrainer` consume only that interface. There is no
production implementation at that seam today, so every real evaluator caller
would otherwise need to recreate the entire loop.

## Alternatives considered

### Keep the current module shape — rejected

Keeping the loop in `run_watchable_session` is locally simple because that
module also owns a visible Balatro instance and JSON Lines lifecycle. It fails
the deletion test, though: deleting a prospective episode module leaves the
policy-driving, current-action validation, terminal classification,
truncation rejection, and `EpisodeOutcome` conversion to be reproduced in the
Watchable session and in each evaluator implementation. That is semantic
complexity, not incidental orchestration.

### Extract a bridge or launch adapter first — rejected for this scope

The Watchable session's managed-instance lifecycle, bridge health check,
visible lifecycle trace, stdout redirection, inspection mode, and cleanup are
not episode-driving behavior. Moving them would broaden this ticket and
introduce an adapter at the wrong seam. The existing `EpisodeRunner` seam is
the relevant seam; a transport adapter is not needed to deepen it. T-51 can
separately examine the BalatroBot composition seam.

### Deepen the existing `EpisodeRunner` seam — selected

The follow-up should provide a module whose public callable conforms directly
to `EpisodeRunner`: given a `Policy` and seed, it resets a supplied Round
Tactics environment, repeatedly selects only current legal actions, applies
them until a terminal state, rejects truncation as an incomplete episode, and
returns the canonical `EpisodeOutcome` from the terminal `StepResult`.

The construction-time interface may accept the already-composed
`RoundTacticsEnvironment` and an optional action observer for the Watchable
session's `action_applied` JSONL event. Its caller-facing episode interface
must remain the two-argument `EpisodeRunner` interface; it should not expose
individual reset, select, step, or terminal-mapping operations. The Watchable
session retains ownership of its managed Balatro instance, bridge health
check, JSON Lines lifecycle, inspection mode, and cleanup. It composes the
environment and observes actions, then translates the returned outcome into
its visible settlement result.

## Depth, leverage, and locality

This is a deep module because one small interface exercises the whole episode
while hiding the policy loop and its invariants. It gives evaluators leverage:
`Benchmark` and `CEMTrainer` can receive a real episode runner without
learning Round Tactics transition details. It gives maintainers locality:
policy-action validity, terminal-state handling, truncation semantics, and
`EpisodeOutcome` construction have one owner and one test surface.

The module would have an internal seam only if testing requires a fake
environment; that is distinct from its external `EpisodeRunner` seam. The
current real `RoundTacticsEnvironment` and existing test fakes are not two
transport adapters that justify a new transport interface.

## Follow-up guardrails

The implementation ticket should specify tests for a multi-step terminal
episode, both `ROUND_EVAL` and `GAME_OVER` outcomes, stale or out-of-mask
policy actions, and truncated episodes. It should also preserve the
Watchable-session lifecycle tests and update the substitution conformance
test to consume the shared episode driver rather than reconstructing outcome
semantics. No production learner, launch adapter, or broad environment
refactor is in scope.

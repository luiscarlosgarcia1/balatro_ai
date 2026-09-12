"""The authoritative reset-to-terminal driver for Round Tactics episodes."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .environments.live import (
    GAME_OVER_STATE,
    ROUND_EVAL_STATE,
    TERMINAL_STATES,
    LegalAction,
    RoundTacticsEnvironment,
    StepResult,
)
from .evaluation import EpisodeOutcome
from .policies import Policy


class EpisodeExecutionError(RuntimeError):
    """Raised when a Round Tactics episode cannot produce a terminal outcome."""

    def __init__(self, phase: str, message: str, *, unexpected: bool = False) -> None:
        super().__init__(message)
        self.phase = phase
        self.unexpected = unexpected


class RoundTacticsEpisodeRunner:
    """Drive a supplied Round Tactics environment through one complete episode.

    The instance is an ``EpisodeRunner``: callers only provide a policy and seed.
    Construction composes the live environment and optionally observes accepted
    actions without exposing the episode's reset/step state machine.
    """

    def __init__(
        self,
        environment: RoundTacticsEnvironment,
        *,
        action_observer: Callable[[LegalAction], None] | None = None,
        ready_observer: Callable[[], None] | None = None,
    ) -> None:
        self._environment = environment
        self._action_observer = action_observer
        self._ready_observer = ready_observer

    def __call__(self, policy: Policy, seed: str) -> EpisodeOutcome:
        try:
            reset_result = self._environment.reset(seed)
        except Exception as error:
            raise EpisodeExecutionError("reset", str(error)) from error
        observation = reset_result.observation
        actions = reset_result.legal_action_mask
        self._require_actions(actions, "reset")
        if self._ready_observer is not None:
            self._ready_observer()

        while True:
            action = policy.select_action(observation, actions)
            self._require_current_action(action, actions)
            try:
                step_result = self._environment.step(action)
            except Exception as error:
                raise EpisodeExecutionError("step", str(error)) from error
            if self._action_observer is not None:
                self._action_observer(action)

            if step_result.truncated:
                raise EpisodeExecutionError(
                    "step",
                    f"Round Tactics episode was truncated at {step_result.state!r}",
                    unexpected=True,
                )
            if step_result.terminated:
                return self._outcome(seed, step_result)

            observation = step_result.observation
            actions = step_result.legal_action_mask
            self._require_actions(actions, "step")

    @staticmethod
    def _require_actions(actions: Sequence[LegalAction], operation: str) -> None:
        if not actions:
            raise EpisodeExecutionError(
                operation,
                f"Round Tactics {operation} produced no legal action",
                unexpected=True,
            )

    @staticmethod
    def _require_current_action(
        action: LegalAction, actions: Sequence[LegalAction]
    ) -> None:
        if not any(action is current for current in actions):
            raise EpisodeExecutionError(
                "step",
                "Round Tactics policy selected an action outside the legal mask",
                unexpected=True,
            )

    @staticmethod
    def _outcome(seed: str, step_result: StepResult) -> EpisodeOutcome:
        state = step_result.state
        if state not in TERMINAL_STATES:
            raise EpisodeExecutionError(
                "step",
                f"Round Tactics terminated at unsupported state {state!r}",
                unexpected=True,
            )
        return EpisodeOutcome(
            seed=seed,
            terminal_reward=step_result.reward,
            won=state == ROUND_EVAL_STATE,
            hands_left=step_result.observation.hands_left,
        )


def settlement_state(outcome: EpisodeOutcome) -> str:
    """Translate the canonical terminal outcome into Watchable presentation."""
    return ROUND_EVAL_STATE if outcome.won else GAME_OVER_STATE

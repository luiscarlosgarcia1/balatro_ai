"""The seeded first-Small-Blind boundary over a live BalatroBot bridge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Any, Mapping, Protocol


OBSERVATION_VERSION = "round-tactics/v1"
EXTERNAL_LIMIT_STATE = "EXTERNAL_LIMIT"
BRIDGE_FAULT_STATE = "BRIDGE_FAULT"
ROUND_EVAL_STATE = "ROUND_EVAL"
GAME_OVER_STATE = "GAME_OVER"
TERMINAL_STATES = frozenset((ROUND_EVAL_STATE, GAME_OVER_STATE))
NONTERMINAL_REWARD = 0.0
FAILURE_REWARD = -1.0
VICTORY_BASE_REWARD = 1.0
VICTORY_HAND_EFFICIENCY_MULTIPLIER = 0.25


class BalatroBotBridge(Protocol):
    """The small portion of the BalatroBot JSON-RPC client this adapter uses."""

    def call(self, method: str, params: Mapping[str, object] | None = None) -> Mapping[str, Any]:
        """Invoke a BalatroBot endpoint and return its result."""


class ActionKind(StrEnum):
    """Kinds of action available at the Round Tactics boundary."""

    PLAY = "PLAY"
    DISCARD = "DISCARD"


@dataclass(frozen=True)
class LegalAction:
    """A canonical action whose indices address the observed ordered hand."""

    kind: ActionKind
    indices: tuple[int, ...]


@dataclass(frozen=True)
class RoundTacticsObservation:
    """A shop-free projection of a settled active Round Tactics state."""

    version: str
    hand: tuple[Mapping[str, Any], ...]
    remaining_deck_cards: int
    round_chips: int
    blind_target: int
    hands_left: int
    discards_left: int
    hands_played: int
    discards_used: int
    money: int
    poker_hands: Mapping[str, Mapping[str, Any]]
    jokers: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ResetResult:
    """The initial settled observation and its canonical legal-action mask."""

    observation: RoundTacticsObservation
    legal_action_mask: tuple[LegalAction, ...]


@dataclass(frozen=True)
class StepResult:
    """The outcome of one action at the Round Tactics boundary."""

    state: str
    observation: RoundTacticsObservation
    legal_action_mask: tuple[LegalAction, ...]
    reward: float
    terminated: bool
    truncated: bool


class RoundTacticsEnvironment:
    """Owns the live bridge sequence for a deterministic first Small Blind."""

    def __init__(
        self, bridge: BalatroBotBridge, *, max_steps: int | None = None
    ) -> None:
        self._bridge = bridge
        self._max_steps = max_steps
        self._legal_action_mask: tuple[LegalAction, ...] | None = None
        self._last_observation: RoundTacticsObservation | None = None
        self._starting_hands = 0
        self._steps_taken = 0

    def reset(self, seed: str) -> ResetResult:
        """Start a seeded Red/White run and return its settled first hand."""
        self._bridge.call("menu")
        started = self._bridge.call(
            "start", {"deck": "RED", "stake": "WHITE", "seed": seed}
        )
        self._require_state(started, "BLIND_SELECT", "start")
        selected = self._bridge.call("select")
        self._require_state(selected, "SELECTING_HAND", "select")

        observation, legal_action_mask = self._settle(selected)
        self._starting_hands = observation.hands_left
        self._steps_taken = 0
        return ResetResult(observation, legal_action_mask)

    def step(self, action: LegalAction) -> StepResult:
        """Apply a current legal action and return the next settled hand."""
        self._validate_action(action)
        if self._max_steps is not None and self._steps_taken >= self._max_steps:
            return self._truncate(EXTERNAL_LIMIT_STATE)

        method = action.kind.lower()
        try:
            settled = self._bridge.call(method, {"cards": list(action.indices)})
        except OSError:
            return self._truncate(BRIDGE_FAULT_STATE)
        self._steps_taken += 1
        state = settled.get("state")
        if state == "SELECTING_HAND":
            observation, legal_action_mask = self._settle(settled)
            return StepResult(
                state, observation, legal_action_mask, NONTERMINAL_REWARD, False, False
            )
        if state == ROUND_EVAL_STATE:
            self._legal_action_mask = None
            observation = self._project(settled)
            self._last_observation = observation
            return StepResult(
                state, observation, (), self._victory_reward(observation), True, False
            )
        if state == GAME_OVER_STATE:
            self._legal_action_mask = None
            observation = self._project(settled)
            self._last_observation = observation
            return StepResult(state, observation, (), FAILURE_REWARD, True, False)
        raise RuntimeError(
            f"BalatroBot {method} did not settle at a Round Tactics state; got {state!r}"
        )

    def _settle(
        self, gamestate: Mapping[str, Any]
    ) -> tuple[RoundTacticsObservation, tuple[LegalAction, ...]]:
        observation = self._project(gamestate)
        legal_action_mask = self._legal_actions(observation)
        self._last_observation = observation
        self._legal_action_mask = legal_action_mask
        return observation, legal_action_mask

    def _validate_action(self, action: LegalAction) -> None:
        if self._legal_action_mask is None:
            raise ValueError("Round Tactics has no active hand; call reset() first")
        if not isinstance(action, LegalAction):
            raise ValueError("Round Tactics action must be a LegalAction")
        if not self._is_canonical_indices(action.indices):
            raise ValueError("Round Tactics action indices must be distinct ascending positions")
        if not any(action is legal_action for legal_action in self._legal_action_mask):
            raise ValueError("Round Tactics action is stale or not in the current mask")

    @staticmethod
    def _require_state(
        gamestate: Mapping[str, Any], expected: str, operation: str
    ) -> None:
        actual = gamestate.get("state")
        if actual != expected:
            raise RuntimeError(
                f"BalatroBot {operation} did not settle at {expected}; got {actual!r}"
            )

    @staticmethod
    def _project(gamestate: Mapping[str, Any]) -> RoundTacticsObservation:
        hand = tuple((gamestate.get("hand") or {}).get("cards") or ())
        deck = gamestate.get("cards") or {}
        round_info = gamestate.get("round") or {}
        blinds = gamestate.get("blinds") or {}
        small_blind = blinds.get("small") or {}
        jokers = tuple((gamestate.get("jokers") or {}).get("cards") or ())

        return RoundTacticsObservation(
            version=OBSERVATION_VERSION,
            hand=hand,
            remaining_deck_cards=int(deck.get("count", 0)),
            round_chips=int(round_info.get("chips", 0)),
            blind_target=int(small_blind.get("score", 0)),
            hands_left=int(round_info.get("hands_left", 0)),
            discards_left=int(round_info.get("discards_left", 0)),
            hands_played=int(round_info.get("hands_played", 0)),
            discards_used=int(round_info.get("discards_used", 0)),
            money=int(gamestate.get("money", 0)),
            poker_hands=gamestate.get("hands") or {},
            jokers=jokers,
        )

    def _truncate(self, state: str) -> StepResult:
        self._legal_action_mask = None
        if self._last_observation is None:
            raise RuntimeError("Round Tactics has no observation to truncate")
        return StepResult(
            state, self._last_observation, (), NONTERMINAL_REWARD, False, True
        )

    def _victory_reward(self, observation: RoundTacticsObservation) -> float:
        if self._starting_hands <= 0:
            return VICTORY_BASE_REWARD
        return VICTORY_BASE_REWARD + VICTORY_HAND_EFFICIENCY_MULTIPLIER * (
            observation.hands_left / self._starting_hands
        )

    @staticmethod
    def _is_canonical_indices(indices: tuple[int, ...]) -> bool:
        return (
            isinstance(indices, tuple)
            and 1 <= len(indices) <= 5
            and all(type(index) is int for index in indices)
            and indices == tuple(sorted(set(indices)))
        )

    @staticmethod
    def _legal_actions(observation: RoundTacticsObservation) -> tuple[LegalAction, ...]:
        subsets = tuple(
            indices
            for size in range(1, min(5, len(observation.hand)) + 1)
            for indices in combinations(range(len(observation.hand)), size)
        )
        plays = tuple(
            LegalAction(ActionKind.PLAY, indices) for indices in subsets
        )
        if observation.discards_left <= 0:
            return plays
        discards = tuple(
            LegalAction(ActionKind.DISCARD, indices) for indices in subsets
        )
        return plays + discards

"""The seeded first-Small-Blind boundary over a live BalatroBot bridge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Any, Mapping, Protocol


OBSERVATION_VERSION = "round-tactics/v1"


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
    poker_hands: Mapping[str, Mapping[str, Any]]
    jokers: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ResetResult:
    """The initial settled observation and its canonical legal-action mask."""

    observation: RoundTacticsObservation
    legal_action_mask: tuple[LegalAction, ...]


class RoundTacticsEnvironment:
    """Owns the live bridge sequence for a deterministic first Small Blind."""

    def __init__(self, bridge: BalatroBotBridge) -> None:
        self._bridge = bridge

    def reset(self, seed: str) -> ResetResult:
        """Start a seeded Red/White run and return its settled first hand."""
        self._bridge.call("menu")
        started = self._bridge.call(
            "start", {"deck": "RED", "stake": "WHITE", "seed": seed}
        )
        self._require_state(started, "BLIND_SELECT", "start")
        selected = self._bridge.call("select")
        self._require_state(selected, "SELECTING_HAND", "select")

        observation = self._project(selected)
        return ResetResult(observation, self._legal_actions(observation))

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
            poker_hands=gamestate.get("hands") or {},
            jokers=jokers,
        )

    @staticmethod
    def _legal_actions(observation: RoundTacticsObservation) -> tuple[LegalAction, ...]:
        subsets = tuple(
            indices
            for size in range(1, min(5, len(observation.hand)) + 1)
            for indices in combinations(range(len(observation.hand)), size)
        )
        plays = tuple(LegalAction(ActionKind.PLAY, indices) for indices in subsets)
        if observation.discards_left <= 0:
            return plays
        discards = tuple(LegalAction(ActionKind.DISCARD, indices) for indices in subsets)
        return plays + discards

from __future__ import annotations

from typing import Protocol

from .models import GameAction, ObservationPayload, ValidationResult


class Observer(Protocol):
    def observe(self) -> ObservationPayload:
        """Return the latest visible game state."""


class Policy(Protocol):
    def choose_action(self, observation: ObservationPayload) -> GameAction:
        """Choose the next high-level action for the current state."""


class Validator(Protocol):
    def validate(
        self,
        observation: ObservationPayload,
        action: GameAction,
    ) -> ValidationResult:
        """Approve or reject the proposed game action."""


class Executor(Protocol):
    def execute(self, action: GameAction) -> None:
        """Perform the action in the game environment."""

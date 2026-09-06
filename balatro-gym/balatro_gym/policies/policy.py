"""The policy contract consumed by Round Tactics evaluators."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from balatro_gym.environments.live import LegalAction, RoundTacticsObservation


class Policy(Protocol):
    """Select one action admitted by the current Round Tactics mask."""

    def select_action(
        self,
        observation: RoundTacticsObservation,
        legal_action_mask: Sequence[LegalAction],
    ) -> LegalAction:
        """Return an action from ``legal_action_mask``."""

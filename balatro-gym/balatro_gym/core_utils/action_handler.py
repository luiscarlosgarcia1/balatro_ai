from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from balatro_gym.core.constants import Action
from balatro_gym.core_utils.mvp_contract import build_mvp_action_mask

if TYPE_CHECKING:
    from balatro_gym.core_utils.rng import DeterministicRNG
    from balatro_gym.core_utils.state import UnifiedGameState


class ActionHandler:
    """Handles action validation and masking for the Balatro environment."""

    def __init__(self, state: UnifiedGameState, rng: DeterministicRNG):
        self.state = state
        self.rng = rng

    @staticmethod
    def get_action_space_size() -> int:
        return Action.ACTION_SPACE_SIZE

    def is_valid_action(self, action: int) -> bool:
        """Check if action is valid."""
        if not 0 <= action < Action.ACTION_SPACE_SIZE:
            return False
        mask = self._get_action_mask()
        return bool(mask[action])

    def _get_action_mask(self) -> np.ndarray:
        """Get valid actions for current state."""
        return build_mvp_action_mask(self.state)

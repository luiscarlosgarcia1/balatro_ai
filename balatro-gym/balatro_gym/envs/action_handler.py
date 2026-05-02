from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from balatro_gym.constants import Phase, Action

if TYPE_CHECKING:
    from balatro_gym.envs.rng import DeterministicRNG
    from balatro_gym.envs.state import UnifiedGameState


class ActionHandler:
    """Handles action validation and masking for the Balatro environment"""

    def __init__(self, state: UnifiedGameState, rng: DeterministicRNG):
        self.state = state
        self.rng = rng

    @staticmethod
    def get_action_space_size() -> int:
        return Action.ACTION_SPACE_SIZE

    def is_valid_action(self, action: int) -> bool:
        """Check if action is valid"""
        mask = self._get_action_mask()
        return bool(mask[action])

    def _get_action_mask(self, shop=None) -> np.ndarray:
        """Get valid actions for current state"""
        mask = np.zeros(Action.ACTION_SPACE_SIZE, dtype=np.int8)

        if self.state.phase == Phase.PLAY:
            for i in range(min(8, len(self.state.hand_indexes))):
                mask[Action.SELECT_CARD_BASE + i] = 1

            if len(self.state.selected_cards) > 0:
                mask[Action.PLAY_HAND] = 1

            if len(self.state.selected_cards) > 0 and self.state.discards_left > 0:
                mask[Action.DISCARD] = 1

            for i in range(len(self.state.consumables)):
                mask[Action.USE_CONSUMABLE_BASE + i] = 1

        elif self.state.phase == Phase.SHOP:
            if shop:
                for i in range(len(shop.inventory)):
                    if self.state.money >= shop.inventory[i].cost:
                        mask[Action.SHOP_BUY_BASE + i] = 1

                if self.state.money >= self.state.shop_reroll_cost:
                    mask[Action.SHOP_REROLL] = 1

            mask[Action.SHOP_END] = 1

            for i in range(len(self.state.jokers)):
                mask[Action.SELL_JOKER_BASE + i] = 1

        elif self.state.phase == Phase.BLIND_SELECT:
            for i in range(Action.SELECT_BLIND_COUNT):
                mask[Action.SELECT_BLIND_BASE + i] = 1
            mask[Action.SKIP_BLIND] = 1

        return mask

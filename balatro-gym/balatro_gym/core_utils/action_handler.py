from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from balatro_gym.core.constants import Phase, Action

if TYPE_CHECKING:
    from balatro_gym.core_utils.rng import DeterministicRNG
    from balatro_gym.core_utils.state import UnifiedGameState


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

    def _get_action_mask(self) -> np.ndarray:
        """Get valid actions for current state"""
        mask = np.zeros(Action.ACTION_SPACE_SIZE, dtype=np.int8)

        if self.state.phase == Phase.PLAY:
            n_selected = len(self.state.selected_cards)
            for i in range(min(Action.SELECT_CARD_COUNT, len(self.state.hand_indexes))):
                mask[Action.SELECT_CARD_BASE + i] = 1

            if 0 < n_selected <= 5:
                mask[Action.PLAY_HAND] = 1

            if n_selected > 0 and self.state.discards_left > 0:
                mask[Action.DISCARD] = 1

            for i in range(min(Action.USE_CONSUMABLE_COUNT, len(self.state.consumables))):
                mask[Action.USE_CONSUMABLE_BASE + i] = 1

        elif self.state.phase == Phase.SHOP:
            for i, item in enumerate(self.state.shop_inventory[:Action.SHOP_BUY_COUNT]):
                if self.state.money >= item.cost:
                    mask[Action.SHOP_BUY_BASE + i] = 1

            if self.state.money >= self.state.shop_reroll_cost:
                mask[Action.SHOP_REROLL] = 1

            mask[Action.SHOP_END] = 1

            for i in range(min(Action.SELL_JOKER_COUNT, len(self.state.jokers))):
                mask[Action.SELL_JOKER_BASE + i] = 1

        elif self.state.phase == Phase.PACK_OPEN:
            pack_contents = self._get_pack_contents()
            selected_indexes = set(self._get_pack_selected_indexes())
            cards_to_select = self._get_pack_cards_to_select()

            if len(selected_indexes) < cards_to_select:
                for i in range(min(Action.SELECT_FROM_PACK_COUNT, len(pack_contents))):
                    if i not in selected_indexes:
                        mask[Action.SELECT_FROM_PACK_BASE + i] = 1

            if pack_contents:
                mask[Action.SKIP_PACK] = 1

        elif self.state.phase == Phase.BLIND_SELECT:
            for i in range(Action.SELECT_BLIND_COUNT):
                mask[Action.SELECT_BLIND_BASE + i] = 1
            mask[Action.SKIP_BLIND] = 1

        return mask

    def _get_pack_contents(self) -> list:
        for attr in (
            "pack_contents",
            "current_pack_contents",
            "pack_items",
            "pack_cards",
            "pack_choices",
        ):
            value = getattr(self.state, attr, None)
            if value is not None:
                return list(value)
        return []

    def _get_pack_selected_indexes(self) -> list:
        for attr in (
            "selected_indexes",
            "pack_selected_indexes",
            "selected_pack_indexes",
        ):
            value = getattr(self.state, attr, None)
            if value is not None:
                return list(value)
        return []

    def _get_pack_cards_to_select(self) -> int:
        for attr in (
            "cards_to_select",
            "pack_cards_to_select",
            "pack_selection_limit",
        ):
            value = getattr(self.state, attr, None)
            if value is not None:
                return max(0, int(value))
        return 1

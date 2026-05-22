from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

import numpy as np

from balatro_gym.core.constants import Phase
from balatro_gym.core_utils.mvp_contract import (
    build_mvp_action_mask,
    get_visible_boss_blind,
    create_mvp_observation_space,
    encode_consumable_ids,
    encode_fool_replayable_consumable,
    encode_hand_levels,
    encode_joker_ids,
    encode_pack_item_ids,
    encode_pack_item_types,
    get_pack_cards_to_select,
    get_pack_contents,
    get_pending_pack_target_count,
    get_pack_selected_indexes,
    get_shop_inventory,
    get_shop_item_cost,
    get_shop_item_type_id,
    is_pack_item_selectable,
)

if TYPE_CHECKING:
    from balatro_gym.core_utils.state import UnifiedGameState


class ObservationBuilder:
    """Builds observations and observation space for the Balatro environment."""

    def create_observation_space(self):
        """Create the reduced MVP observation space."""
        return create_mvp_observation_space()

    def build_observation(self, state: UnifiedGameState, shop=None) -> Dict[str, Any]:
        """Build observation dict from current game state."""
        hand_array = np.full(8, -1, dtype=np.int8)
        for i, idx in enumerate(state.hand_indexes[:8]):
            if idx < len(state.deck):
                hand_array[i] = int(state.deck[idx])

        obs = {
            "hand": hand_array,
            "hand_size": np.int8(len(state.hand_indexes)),
            "deck_size": np.int8(sum(1 for _ in state.deck)),
            "selected_cards": np.array([1 if i in state.selected_cards else 0 for i in range(8)], dtype=np.int8),
            "chips_scored": np.int64(state.chips_scored),
            "round_chips_scored": np.int32(state.round_chips_scored),
            "progress_ratio": np.float32(min(2.0, state.round_chips_scored / max(1, state.chips_needed))),
            "mult": np.int32(1),
            "chips_needed": np.int32(state.chips_needed),
            "money": np.int32(state.money),
            "ante": np.int16(state.ante),
            "round": np.int8(state.round),
            "hands_left": np.int8(state.hands_left),
            "discards_left": np.int8(state.discards_left),
            "joker_count": np.int8(len(state.jokers)),
            "joker_ids": encode_joker_ids(state.jokers),
            "joker_slots": np.int8(state.joker_slots),
            "consumable_count": np.int8(len(state.consumables)),
            "consumables": encode_consumable_ids(state.consumables),
            "consumable_slots": np.int8(state.consumable_slots),
            "shop_items": np.zeros(10, dtype=np.int16),
            "shop_costs": np.zeros(10, dtype=np.int16),
            "shop_rerolls": np.int16(state.shop_reroll_cost),
            "pack_item_types": np.zeros(5, dtype=np.int8),
            "pack_item_ids": np.zeros(5, dtype=np.int16),
            "pack_item_selectable": np.zeros(5, dtype=np.int8),
            "pack_cards_to_select": np.int8(0),
            "pack_choices_remaining": np.int8(0),
            "fool_replayable_consumable": encode_fool_replayable_consumable(state),
            "hand_levels": encode_hand_levels(state.hand_levels),
            "phase": np.int8(state.phase),
            "action_mask": build_mvp_action_mask(state, shop=shop),
            "hands_played": np.int32(state.hands_played_total),
            "best_hand_this_ante": np.int32(state.best_hand_this_ante),
            "boss_blind_active": np.int8(1 if state.boss_blind_active else 0),
            "boss_blind_type": np.int8(
                get_visible_boss_blind(state).value if get_visible_boss_blind(state) else 0
            ),
            "face_down_cards": np.array([1 if i in state.face_down_cards else 0 for i in range(8)], dtype=np.int8),
        }

        hand_cards = [state.deck[i] for i in state.hand_indexes if i < len(state.deck)]
        hand_features = self._calculate_hand_features(hand_cards)
        obs["rank_counts"] = hand_features["rank_counts"]
        obs["suit_counts"] = hand_features["suit_counts"]
        obs["straight_potential"] = np.float32(hand_features["straight_potential"])
        obs["flush_potential"] = np.float32(hand_features["flush_potential"])

        if state.phase == Phase.SHOP:
            shop_items, shop_costs = self._get_shop_arrays(state, shop)
            obs["shop_items"][: len(shop_items)] = shop_items
            obs["shop_costs"][: len(shop_costs)] = shop_costs

        pack_contents = get_pack_contents(state, shop)
        if pack_contents:
            selected_indexes = set(get_pack_selected_indexes(state, shop))
            cards_to_select = max(0, get_pack_cards_to_select(state, shop))
            pack_selectable = np.zeros(5, dtype=np.int8)
            for i, item in enumerate(pack_contents[:5]):
                pack_selectable[i] = np.int8(
                    i not in selected_indexes and is_pack_item_selectable(state, item, item_index=i)
                )

            obs["pack_item_types"] = encode_pack_item_types(pack_contents, slots=5)
            obs["pack_item_ids"] = encode_pack_item_ids(pack_contents, slots=5)
            obs["pack_item_selectable"] = pack_selectable
            obs["pack_cards_to_select"] = np.int8(min(5, cards_to_select))
            pending_target_count = get_pending_pack_target_count(state, shop)
            obs["pack_choices_remaining"] = np.int8(
                max(0, min(5, pending_target_count - len(state.selected_cards)))
                if pending_target_count > 0
                else max(0, min(5, cards_to_select - len(selected_indexes)))
            )

        return obs

    def _get_shop_arrays(self, state: UnifiedGameState, shop=None) -> tuple[np.ndarray, np.ndarray]:
        inventory = get_shop_inventory(state, shop)
        if inventory:
            item_types = [self._get_shop_item_type_value(item) for item in inventory[:10]]
            costs = [get_shop_item_cost(item) or 0 for item in inventory[:10]]
            return np.array(item_types, dtype=np.int16), np.array(costs, dtype=np.int16)

        if shop and hasattr(shop, "get_observation"):
            shop_obs = shop.get_observation()
            item_types = np.array(shop_obs.get("shop_item_type", [])[:10], dtype=np.int16)
            costs = np.array(shop_obs.get("shop_cost", [])[:10], dtype=np.int16)
            return item_types, costs

        return np.zeros(0, dtype=np.int16), np.zeros(0, dtype=np.int16)

    def _get_shop_item_type_value(self, item: Any) -> int:
        return get_shop_item_type_id(item)

    def _calculate_hand_features(self, hand_cards: list) -> Dict[str, Any]:
        """Calculate advanced hand features for better decision making."""
        rank_counts = np.zeros(13, dtype=np.int8)
        suit_counts = np.zeros(4, dtype=np.int8)

        for card in hand_cards:
            if card:
                rank_counts[card.rank.value - 2] += 1
                suit_counts[card.suit.value] += 1

        consecutive = 0
        max_consecutive = 0
        sorted_ranks = sorted(set(card.rank.value for card in hand_cards if card))
        for i in range(1, len(sorted_ranks)):
            if sorted_ranks[i] - sorted_ranks[i - 1] == 1:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0

        max_suit = max(suit_counts) if suit_counts.any() else 0
        return {
            "rank_counts": rank_counts,
            "suit_counts": suit_counts,
            "straight_potential": min(1.0, max_consecutive / 4.0),
            "flush_potential": min(1.0, max_suit / 5.0),
        }

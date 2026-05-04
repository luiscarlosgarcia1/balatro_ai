from __future__ import annotations

from typing import Dict, List, Any, Optional, TYPE_CHECKING

import numpy as np
from gymnasium import spaces

from balatro_gym.core.constants import Phase, Action
from balatro_gym.scoring.scoring_engine import HandType

if TYPE_CHECKING:
    from balatro_gym.envs.state import UnifiedGameState


class ObservationBuilder:
    """Builds observations and observation space for the Balatro environment"""

    def create_observation_space(self) -> spaces.Dict:
        """Create the complete observation space"""
        return spaces.Dict({
            'hand': spaces.Box(-1, 51, (8,), dtype=np.int8),
            'hand_size': spaces.Box(0, 12, (), dtype=np.int8),
            'deck_size': spaces.Box(0, 52, (), dtype=np.int8),
            'selected_cards': spaces.MultiBinary(8),

            'chips_scored': spaces.Box(0, 10_000_000_000, (), dtype=np.int64),
            'round_chips_scored': spaces.Box(0, 10_000_000, (), dtype=np.int32),
            'progress_ratio': spaces.Box(0.0, 2.0, (), dtype=np.float32),
            'mult': spaces.Box(0, 10_000, (), dtype=np.int32),
            'chips_needed': spaces.Box(0, 10_000_000, (), dtype=np.int32),
            'money': spaces.Box(-20, 999, (), dtype=np.int32),

            'ante': spaces.Box(1, 1000, (), dtype=np.int16),
            'round': spaces.Box(1, 3, (), dtype=np.int8),
            'hands_left': spaces.Box(0, 12, (), dtype=np.int8),
            'discards_left': spaces.Box(0, 10, (), dtype=np.int8),

            'joker_count': spaces.Box(0, 10, (), dtype=np.int8),
            'joker_ids': spaces.Box(0, 200, (10,), dtype=np.int16),
            'joker_slots': spaces.Box(0, 10, (), dtype=np.int8),

            'consumable_count': spaces.Box(0, 5, (), dtype=np.int8),
            'consumables': spaces.Box(0, 100, (5,), dtype=np.int16),
            'consumable_slots': spaces.Box(0, 5, (), dtype=np.int8),

            'shop_items': spaces.Box(0, 300, (10,), dtype=np.int16),
            'shop_costs': spaces.Box(0, 5000, (10,), dtype=np.int16),
            'shop_rerolls': spaces.Box(0, 999, (), dtype=np.int16),

            'hand_levels': spaces.Box(0, 15, (12,), dtype=np.int8),

            'phase': spaces.Box(0, 3, (), dtype=np.int8),
            'action_mask': spaces.MultiBinary(Action.ACTION_SPACE_SIZE),

            'hands_played': spaces.Box(0, 10000, (), dtype=np.int32),
            'best_hand_this_ante': spaces.Box(0, 10_000_000, (), dtype=np.int32),

            'boss_blind_active': spaces.Box(0, 1, (), dtype=np.int8),
            'boss_blind_type': spaces.Box(0, 30, (), dtype=np.int8),
            'face_down_cards': spaces.MultiBinary(8),

            'rank_counts': spaces.Box(0, 4, (13,), dtype=np.int8),
            'suit_counts': spaces.Box(0, 8, (4,), dtype=np.int8),
            'straight_potential': spaces.Box(0, 1, (), dtype=np.float32),
            'flush_potential': spaces.Box(0, 1, (), dtype=np.float32),
        })

    def build_observation(self, state: UnifiedGameState, shop=None) -> Dict[str, Any]:
        """Build observation dict from current game state"""
        hand_array = np.full(8, -1, dtype=np.int8)
        for i, idx in enumerate(state.hand_indexes[:8]):
            if idx < len(state.deck):
                hand_array[i] = int(state.deck[idx])

        for hand_type in HandType:
            state.hand_levels[hand_type] = state.hand_levels.get(hand_type, 0)

        consumable_ids = self._get_consumable_ids(state)

        obs = {
            'hand': hand_array,
            'hand_size': np.int8(len(state.hand_indexes)),
            'deck_size': np.int8(sum(1 for _ in state.deck)),
            'selected_cards': np.array([1 if i in state.selected_cards else 0 for i in range(8)]),

            'chips_scored': np.int64(state.chips_scored),
            'round_chips_scored': np.int32(state.round_chips_scored),
            'progress_ratio': np.float32(min(2.0, state.round_chips_scored / max(1, state.chips_needed))),
            'mult': np.int32(1),
            'chips_needed': np.int32(state.chips_needed),
            'money': np.int32(state.money),

            'ante': np.int16(state.ante),
            'round': np.int8(state.round),
            'hands_left': np.int8(state.hands_left),
            'discards_left': np.int8(state.discards_left),

            'joker_count': np.int8(len(state.jokers)),
            'joker_ids': np.array([j.id for j in state.jokers] +
                                  [0] * (10 - len(state.jokers)), dtype=np.int16),
            'joker_slots': np.int8(state.joker_slots),

            'consumable_count': np.int8(len(state.consumables)),
            'consumables': np.array(consumable_ids, dtype=np.int16),
            'consumable_slots': np.int8(state.consumable_slots),

            'shop_items': np.zeros(10, dtype=np.int16),
            'shop_costs': np.zeros(10, dtype=np.int16),
            'shop_rerolls': np.int16(state.shop_reroll_cost),

            'hand_levels': np.array(list(state.hand_levels.values())[:12], dtype=np.int8),
            'phase': np.int8(state.phase),
            'action_mask': self._get_action_mask(state, shop),

            'hands_played': np.int32(state.hands_played_total),
            'best_hand_this_ante': np.int32(state.best_hand_this_ante),

            'boss_blind_active': np.int8(1 if state.boss_blind_active else 0),
            'boss_blind_type': np.int8(state.active_boss_blind.value if state.active_boss_blind else 0),
            'face_down_cards': np.array([1 if i in state.face_down_cards else 0 for i in range(8)]),
        }

        hand_cards = [state.deck[i] for i in state.hand_indexes if i < len(state.deck)]
        hand_features = self._calculate_hand_features(hand_cards)
        obs['rank_counts'] = hand_features['rank_counts']
        obs['suit_counts'] = hand_features['suit_counts']
        obs['straight_potential'] = np.float32(hand_features['straight_potential'])
        obs['flush_potential'] = np.float32(hand_features['flush_potential'])

        if state.phase == Phase.SHOP and shop:
            shop_obs = shop.get_observation()
            for i, (item_type, cost) in enumerate(zip(shop_obs['shop_item_type'][:10],
                                                      shop_obs['shop_cost'][:10])):
                obs['shop_items'][i] = item_type
                obs['shop_costs'][i] = cost

        return obs

    def _get_action_mask(self, state: UnifiedGameState, shop=None) -> np.ndarray:
        """Get valid action mask for current state"""
        mask = np.zeros(Action.ACTION_SPACE_SIZE, dtype=np.int8)

        if state.phase == Phase.PLAY:
            for i in range(min(8, len(state.hand_indexes))):
                mask[Action.SELECT_CARD_BASE + i] = 1

            if len(state.selected_cards) > 0:
                mask[Action.PLAY_HAND] = 1

            if len(state.selected_cards) > 0 and state.discards_left > 0:
                mask[Action.DISCARD] = 1

            for i in range(len(state.consumables)):
                mask[Action.USE_CONSUMABLE_BASE + i] = 1

        elif state.phase == Phase.SHOP:
            if shop:
                for i in range(len(shop.inventory)):
                    if state.money >= shop.inventory[i].cost:
                        mask[Action.SHOP_BUY_BASE + i] = 1

                if state.money >= state.shop_reroll_cost:
                    mask[Action.SHOP_REROLL] = 1

            mask[Action.SHOP_END] = 1

            for i in range(len(state.jokers)):
                mask[Action.SELL_JOKER_BASE + i] = 1

        elif state.phase == Phase.BLIND_SELECT:
            for i in range(Action.SELECT_BLIND_COUNT):
                mask[Action.SELECT_BLIND_BASE + i] = 1
            mask[Action.SKIP_BLIND] = 1

        return mask

    def _calculate_hand_features(self, hand_cards: list) -> Dict[str, Any]:
        """Calculate advanced hand features for better decision making"""
        features = {}

        rank_counts = np.zeros(13, dtype=np.int8)
        suit_counts = np.zeros(4, dtype=np.int8)

        for card in hand_cards:
            if card:
                rank_counts[card.rank.value - 2] += 1
                suit_counts[card.suit.value] += 1

        features['rank_counts'] = rank_counts
        features['suit_counts'] = suit_counts

        consecutive = 0
        max_consecutive = 0
        sorted_ranks = sorted(set(card.rank.value for card in hand_cards if card))

        for i in range(1, len(sorted_ranks)):
            if sorted_ranks[i] - sorted_ranks[i - 1] == 1:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0

        features['straight_potential'] = min(1.0, max_consecutive / 4.0)

        max_suit = max(suit_counts) if suit_counts.any() else 0
        features['flush_potential'] = min(1.0, max_suit / 5.0)

        return features

    def _get_consumable_ids(self, state: UnifiedGameState) -> list:
        """Convert consumable names to IDs for observation"""
        consumable_id_map = {
            'The Fool': 1, 'The Magician': 2, 'The High Priestess': 3,
            'The Empress': 4, 'The Emperor': 5, 'The Hierophant': 6,
            'The Lovers': 7, 'The Chariot': 8, 'Strength': 9,
            'The Hermit': 10, 'Wheel of Fortune': 11, 'Justice': 12,
            'The Hanged Man': 13, 'Death': 14, 'Temperance': 15,
            'The Devil': 16, 'The Tower': 17, 'The Star': 18,
            'The Moon': 19, 'The Sun': 20, 'Judgement': 21,
            'The World': 22,

            'Mercury': 30, 'Venus': 31, 'Earth': 32, 'Mars': 33,
            'Jupiter': 34, 'Saturn': 35, 'Uranus': 36, 'Neptune': 37,
            'Pluto': 38, 'Planet X': 39, 'Ceres': 40, 'Eris': 41,

            'Familiar': 50, 'Grim': 51, 'Incantation': 52, 'Talisman': 53,
            'Aura': 54, 'Wraith': 55, 'Sigil': 56, 'Ouija': 57,
            'Ectoplasm': 58, 'Immolate': 59, 'Ankh': 60, 'Deja Vu': 61,
            'Hex': 62, 'Trance': 63, 'Medium': 64, 'Cryptid': 65,
            'The Soul': 66, 'Black Hole': 67
        }

        ids = [consumable_id_map.get(c, 0) for c in state.consumables]
        return ids + [0] * (5 - len(ids))

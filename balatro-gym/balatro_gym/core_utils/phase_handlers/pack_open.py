"""Pack opening phase handler for Balatro RL environment.

This module handles the pack opening phase where players select
cards from booster packs.
"""

from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from balatro_gym.core.consumables import (
    ConsumableManager,
    is_planet_consumable_name,
    is_tarot_consumable_name,
)
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.jokers import JOKER_LIBRARY
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.mvp_contract import can_use_consumable_from_pack, get_pack_consumable_target_count
from balatro_gym.scoring.scoring_engine import HandType


class PackOpenHandler:
    """Handles pack opening phase."""
    
    def __init__(self, state: UnifiedGameState, shop_handler):
        """Initialize the pack open handler.
        
        Args:
            state: Game state
            shop_handler: Reference to shop handler for returning to shop
        """
        self.state = state
        self.shop_handler = shop_handler
        self.shop_handler.pack_open_handler = self
        self.pack_contents: List[Dict] = []
        self.pack_type: str = ""
        self.cards_to_select: int = 1
        self.selected_indexes: List[int] = []
        self.consumable_manager = ConsumableManager()
    
    def step(self, action: int) -> Tuple[float, bool, Dict]:
        """Process an action during pack open phase.
        
        Args:
            action: Action to execute
            
        Returns:
            Tuple of (reward, terminated, info)
        """
        if Action.SELECT_FROM_PACK_BASE <= action < Action.SELECT_FROM_PACK_BASE + Action.SELECT_FROM_PACK_COUNT:
            return self._handle_select_card(action)
        elif action == Action.SKIP_PACK:
            return self._handle_skip_pack()
        else:
            return -1.0, False, {'error': 'Invalid pack open action'}
    
    def open_pack(
        self,
        pack_type: str,
        pack_contents: List[Dict],
        cards_to_select: int | None = None,
    ) -> Dict:
        """Initialize pack opening with contents.
        
        Args:
            pack_type: Type of pack being opened
            pack_contents: List of card/item dictionaries in the pack
            cards_to_select: Explicit choice count from shop/game data when available
            
        Returns:
            Info dictionary about the pack
        """
        self.pack_type = pack_type
        self.pack_contents = self._normalize_pack_contents(pack_type, pack_contents)
        self.selected_indexes = []
        
        # Determine how many cards can be selected
        self.cards_to_select = (
            self._get_cards_to_select(pack_type)
            if cards_to_select is None
            else max(1, int(cards_to_select))
        )
        
        # Transition to pack open phase
        self.state.phase = Phase.PACK_OPEN
        self._sync_pack_state_to_unified_state()
        
        return {
            'pack_type': pack_type,
            'pack_size': len(self.pack_contents),
            'cards_to_select': self.cards_to_select,
            'pack_contents': self._format_pack_contents()
        }
    
    def _handle_select_card(self, action: int) -> Tuple[float, bool, Dict]:
        """Handle selecting a card from the pack."""
        card_idx = action - Action.SELECT_FROM_PACK_BASE
        
        if card_idx >= len(self.pack_contents):
            return -1.0, False, {'error': 'Invalid card index'}
        
        if card_idx in self.selected_indexes:
            return -1.0, False, {'error': 'Card already selected'}
        
        if len(self.selected_indexes) >= self.cards_to_select:
            return -1.0, False, {'error': 'Already selected maximum cards'}

        selected_item = self.pack_contents[card_idx]
        if not self._can_take_pack_item(selected_item):
            return -1.0, False, {'error': 'Cannot take selected pack item'}

        # Select the card
        self.selected_indexes.append(card_idx)
        self._sync_pack_state_to_unified_state()
        
        # Apply the selected item
        reward, apply_info = self._apply_pack_item(selected_item)
        
        info = {
            'action': 'selected_card',
            'card_index': card_idx,
            'cards_selected': len(self.selected_indexes),
            'cards_remaining': self.cards_to_select - len(self.selected_indexes)
        }
        info.update(apply_info)
        
        # Check if pack selection is complete
        if len(self.selected_indexes) >= self.cards_to_select:
            return self._complete_pack_opening(reward, info)
        
        return reward, False, info
    
    def _handle_skip_pack(self) -> Tuple[float, bool, Dict]:
        """Handle skipping the remaining pack selections."""
        # Small penalty for not using full pack value
        cards_skipped = self.cards_to_select - len(self.selected_indexes)
        reward = -1.0 * cards_skipped
        
        info = {
            'action': 'skipped_pack',
            'cards_skipped': cards_skipped
        }

        self._sync_pack_state_to_unified_state()
        
        return self._complete_pack_opening(reward, info)
    
    def _complete_pack_opening(self, base_reward: float, info: Dict) -> Tuple[float, bool, Dict]:
        """Complete pack opening and return to shop."""
        # Clear pack state
        self.pack_contents = []
        self.pack_type = ""
        self.cards_to_select = 1
        self.selected_indexes = []
        self._clear_pack_state_from_unified_state()
        
        # Return to shop phase
        self.state.phase = Phase.SHOP
        
        # Regenerate shop display
        if self.shop_handler.shop:
            self.state.shop_inventory = self.shop_handler.shop.inventory.copy()
        
        info['transition_to'] = 'shop'
        
        return base_reward, False, info
    
    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    
    def _get_cards_to_select(self, pack_type: str) -> int:
        """Get number of cards that can be selected from pack type."""
        normalized = pack_type.lower()
        if normalized.startswith('mega '):
            return 2
        return 1

    def _sync_pack_state_to_unified_state(self) -> None:
        """Mirror pack-open state onto UnifiedGameState for masks/observations."""
        mirrored_contents = list(self.pack_contents)
        mirrored_selected_indexes = list(self.selected_indexes)

        self.state.pack_contents = mirrored_contents
        self.state.current_pack_contents = mirrored_contents
        self.state.pack_choices = mirrored_contents
        self.state.selected_indexes = mirrored_selected_indexes
        self.state.pack_selected_indexes = mirrored_selected_indexes
        self.state.selected_pack_indexes = mirrored_selected_indexes
        self.state.cards_to_select = self.cards_to_select
        self.state.pack_cards_to_select = self.cards_to_select
        self.state.pack_selection_limit = self.cards_to_select
        self.state.pack_type = self.pack_type

    def _clear_pack_state_from_unified_state(self) -> None:
        """Clear pack-open mirror state once pack resolution is complete."""
        self.state.pack_contents = []
        self.state.current_pack_contents = []
        self.state.pack_choices = []
        self.state.selected_indexes = []
        self.state.pack_selected_indexes = []
        self.state.selected_pack_indexes = []
        self.state.cards_to_select = 0
        self.state.pack_cards_to_select = 0
        self.state.pack_selection_limit = 0
        self.state.pack_type = ""

    def _can_take_pack_item(self, item: Dict) -> bool:
        """Check inventory capacity for the normalized pack item."""
        if 'consumable' in item:
            return can_use_consumable_from_pack(self.state, item['consumable'])
        if 'joker' in item:
            return len(self.state.jokers) < self.state.joker_slots
        return True

    def _normalize_pack_contents(self, pack_type: str, pack_contents: List[Any]) -> List[Dict]:
        """Normalize shop pack payloads into a single pack-item structure."""
        normalized_contents: List[Dict] = []

        for item in pack_contents:
            normalized_item = self._normalize_pack_item(pack_type, item)
            if normalized_item is not None:
                normalized_contents.append(normalized_item)

        return normalized_contents

    def _normalize_pack_item(self, pack_type: str, item: Any) -> Optional[Dict]:
        """Normalize a single pack choice from raw shop output."""
        if isinstance(item, dict):
            if 'card' in item:
                normalized = dict(item)
                normalized['card'] = self._coerce_card(normalized['card'])
                return normalized if normalized['card'] is not None else None

            if 'joker' in item:
                normalized = dict(item)
                normalized['joker'] = self._coerce_joker(normalized['joker'])
                return normalized if normalized['joker'] is not None else None

            if 'joker_id' in item:
                joker = self._coerce_joker(item['joker_id'])
                return {'joker': joker} if joker is not None else None

            if 'consumable' in item:
                normalized = dict(item)
                normalized['consumable'] = self._coerce_consumable_name(normalized['consumable'])
                return normalized

            if 'card_id' in item:
                card = self._coerce_card(item['card_id'])
                return {'card': card} if card is not None else None

        if isinstance(item, Card):
            return {'card': item}

        if isinstance(item, int):
            card = self._coerce_card(item)
            return {'card': card} if card is not None else None

        if isinstance(item, str):
            if 'joker' in pack_type.lower():
                joker = self._coerce_joker(item)
                return {'joker': joker} if joker is not None else None
            return {'consumable': self._coerce_consumable_name(item)}

        if hasattr(item, 'rank') and hasattr(item, 'suit'):
            card = self._coerce_card(item)
            return {'card': card} if card is not None else None

        return None

    def _coerce_card(self, card_value: Any) -> Optional[Card]:
        """Convert raw card identifiers or card-like objects to core Card."""
        if isinstance(card_value, Card):
            return card_value

        if isinstance(card_value, int):
            if not (0 <= card_value < 52):
                return None
            rank = Rank((card_value // 4) + 2)
            suit = Suit(card_value % 4)
            return Card(rank=rank, suit=suit)

        if hasattr(card_value, 'rank') and hasattr(card_value, 'suit'):
            rank_value = getattr(card_value.rank, 'value', card_value.rank)
            suit_value = getattr(card_value.suit, 'value', card_value.suit)
            try:
                return Card(rank=Rank(int(rank_value)), suit=Suit(int(suit_value)))
            except (TypeError, ValueError):
                return None

        return None

    def _coerce_joker(self, joker_value: Any):
        """Convert a joker id/name/object into the shared JokerInfo object."""
        if hasattr(joker_value, 'id') and hasattr(joker_value, 'name'):
            return joker_value

        for joker in JOKER_LIBRARY:
            if joker_value == joker.id or joker_value == joker.name:
                return joker

        return None

    def _coerce_consumable_name(self, consumable_value: Any) -> str:
        """Normalize consumables to the string form used in UnifiedGameState."""
        if isinstance(consumable_value, str):
            return consumable_value
        if hasattr(consumable_value, 'name'):
            return consumable_value.name.replace('_', ' ').title()
        return str(consumable_value)
    
    def _format_pack_contents(self) -> List[str]:
        """Format pack contents for display."""
        formatted = []
        
        for item in self.pack_contents:
            if 'card' in item:
                # Playing card
                card = item['card']
                desc = f"{card.rank.name} of {card.suit.name}"
                if 'enhancement' in item and item['enhancement'] != Enhancement.NONE:
                    desc += f" ({item['enhancement'].name})"
                if 'edition' in item and item['edition'] != Edition.NONE:
                    desc += f" [{item['edition'].name}]"
                if 'seal' in item and item['seal'] != Seal.NONE:
                    desc += f" <{item['seal'].name}>"
                formatted.append(desc)
            
            elif 'consumable' in item:
                # Tarot/Planet/Spectral card
                formatted.append(item['consumable'])
            
            elif 'joker' in item:
                # Joker
                formatted.append(f"Joker: {item['joker'].name}")
            
            else:
                formatted.append("Unknown item")
        
        return formatted
    
    def _apply_pack_item(self, item: Dict) -> Tuple[float, Dict]:
        """Apply the selected pack item to game state."""
        info = {}
        reward = 0.0
        
        if 'card' in item:
            # Add playing card to deck
            card = item['card']
            card_idx = len(self.state.deck)
            self.state.deck.append(card)
            
            # Apply any enhancements/editions/seals
            if any(key in item for key in ['enhancement', 'edition', 'seal']):
                card_state = self.state.get_card_state(card_idx)
                card_state.enhancement = item.get('enhancement', Enhancement.NONE)
                card_state.edition = item.get('edition', Edition.NONE)
                card_state.seal = item.get('seal', Seal.NONE)
            
            info['card_added'] = f"{card.rank.name} of {card.suit.name}"
            reward = 3.0  # Base value for adding a card
            
            # Bonus for enhanced cards
            if item.get('enhancement', Enhancement.NONE) != Enhancement.NONE:
                reward += 2.0
            if item.get('edition', Edition.NONE) != Edition.NONE:
                reward += 3.0
            if item.get('seal', Seal.NONE) != Seal.NONE:
                reward += 2.0
        
        elif 'consumable' in item:
            reward, consumable_info = self._apply_pack_consumable(item['consumable'])
            info.update(consumable_info)
        
        elif 'joker' in item:
            # Add joker to collection
            if self.state.add_joker(item['joker']):
                info['joker_added'] = item['joker'].name
                reward = 15.0  # Jokers are very valuable
            else:
                info['error'] = 'No joker slots available'
                reward = -1.0
        
        return reward, info

    def _apply_pack_consumable(self, consumable_name: str) -> Tuple[float, Dict]:
        """Resolve supported pack consumables immediately instead of storing them."""
        target_cards = self._get_pack_consumable_targets(consumable_name)
        game_state = self.state.to_dict()
        game_state['deck'] = self.state.deck.copy()
        game_state['hand'] = [self.state.deck[idx] for idx in self.state.hand_indexes if 0 <= idx < len(self.state.deck)]
        game_state['consumables'] = self.state.consumables.copy()

        result = self.consumable_manager.use_consumable(consumable_name, game_state, target_cards)
        if not result.get('success'):
            return -1.0, {'error': f'Pack consumable not currently supported: {consumable_name}'}

        reward = 0.0
        info: Dict[str, Any] = {
            'consumable_used': consumable_name,
            'consumable_result': result.get('message', ''),
        }

        money_gained = int(result.get('money_gained', 0) or 0)
        if money_gained:
            self.state.money += money_gained
            reward += money_gained / 2.0
            info['money_gained'] = money_gained

        hand_size_change = int(result.get('hand_size_change', 0) or 0)
        if hand_size_change:
            self.state.hand_size = max(1, self.state.hand_size + hand_size_change)
            reward += abs(hand_size_change) * 2.0
            info['hand_size'] = self.state.hand_size

        if result.get('cards_affected'):
            reward += self._apply_card_modifications(result['cards_affected'])

        for created_item in result.get('items_created', []):
            if len(self.state.consumables) < self.state.consumable_slots:
                self.state.consumables.append(str(created_item))
                reward += 3.0

        for created_joker in result.get('jokers_created', []):
            joker_info = self._lookup_joker(created_joker)
            if joker_info is not None and self.state.add_joker(joker_info):
                reward += 8.0

        destroyed_cards = result.get('cards_destroyed', [])
        if destroyed_cards:
            self.state.deck = [card for card in self.state.deck if card not in destroyed_cards]
            reward += float(len(destroyed_cards))
            info['cards_destroyed'] = len(destroyed_cards)

        created_cards = result.get('cards_created', [])
        if created_cards:
            self.state.deck.extend(created_cards)
            reward += float(len(created_cards))
            info['cards_created'] = len(created_cards)

        planet_used = result.get('planet_used')
        if planet_used:
            self._apply_planet_level(planet_used)
            reward += 8.0

        if consumable_name == 'Black Hole':
            self._apply_black_hole_levels()
            reward += 10.0

        if result.get('success') and (is_tarot_consumable_name(consumable_name) or is_planet_consumable_name(consumable_name)):
            self.state.last_tarot_planet_consumable = consumable_name

        return reward, info

    def _get_pack_consumable_targets(self, consumable_name: str) -> List[Any]:
        """Use a stable prefix of the current hand as the MVP pack target pool."""
        target_count = get_pack_consumable_target_count(consumable_name)
        if target_count <= 0:
            return []

        targets: List[Any] = []
        for card_idx in self.state.hand_indexes:
            if 0 <= card_idx < len(self.state.deck):
                targets.append(CardAdapter.to_consumable_format(self.state.deck[card_idx], card_idx, self.state))
                if len(targets) >= target_count:
                    break
        return targets

    def _apply_card_modifications(self, affected_cards: List[Any]) -> float:
        """Persist card mutations from immediate consumable resolution."""
        for affected in affected_cards:
            card_idx = getattr(affected, 'card_idx', None)
            if card_idx is None or not (0 <= card_idx < len(self.state.deck)):
                continue

            original = self.state.deck[card_idx]
            updated_rank = getattr(affected, 'rank', original.rank)
            updated_suit = getattr(affected, 'suit', original.suit)
            self.state.deck[card_idx] = replace(original, rank=updated_rank, suit=updated_suit)

            card_state = self.state.get_card_state(card_idx)
            if hasattr(affected, 'enhancement'):
                card_state.enhancement = affected.enhancement
            if hasattr(affected, 'edition'):
                card_state.edition = affected.edition
            if hasattr(affected, 'seal'):
                card_state.seal = affected.seal

        return len(affected_cards) * 2.0

    def _lookup_joker(self, joker_value: Any):
        """Resolve a created joker name/object into shared JokerInfo."""
        if hasattr(joker_value, 'id') and hasattr(joker_value, 'name'):
            return joker_value

        joker_name = None
        if isinstance(joker_value, str):
            joker_name = joker_value
        elif isinstance(joker_value, dict):
            joker_name = joker_value.get('name')

        if joker_name:
            for joker_info in JOKER_LIBRARY:
                if joker_info.name == joker_name:
                    return joker_info
        return None

    def _apply_planet_level(self, planet_name: str) -> None:
        """Apply the hand-level upgrade from a planet card."""
        planet_map = {
            'Mercury': HandType.ONE_PAIR,
            'Venus': HandType.TWO_PAIR,
            'Earth': HandType.THREE_KIND,
            'Mars': HandType.STRAIGHT,
            'Jupiter': HandType.FLUSH,
            'Saturn': HandType.FULL_HOUSE,
            'Uranus': HandType.FOUR_KIND,
            'Neptune': HandType.STRAIGHT_FLUSH,
            'Pluto': HandType.HIGH_CARD,
            'Planet X': HandType.FIVE_KIND,
            'Ceres': HandType.FLUSH_HOUSE,
            'Eris': HandType.FLUSH_FIVE,
        }
        hand_type = planet_map.get(planet_name)
        if hand_type is not None:
            self.state.hand_levels[hand_type] = self.state.hand_levels.get(hand_type, 1) + 1

    def _apply_black_hole_levels(self) -> None:
        """Upgrade every tracked hand level by one."""
        for hand_type in HandType:
            self.state.hand_levels[hand_type] = self.state.hand_levels.get(hand_type, 1) + 1

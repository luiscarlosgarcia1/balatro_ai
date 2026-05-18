"""Pack opening phase handler for Balatro RL environment.

This module handles the pack opening phase where players select
cards from booster packs.
"""

from typing import Any, Dict, List, Optional, Tuple

from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.jokers import JOKER_LIBRARY


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
    
    def open_pack(self, pack_type: str, pack_contents: List[Dict]) -> Dict:
        """Initialize pack opening with contents.
        
        Args:
            pack_type: Type of pack being opened
            pack_contents: List of card/item dictionaries in the pack
            
        Returns:
            Info dictionary about the pack
        """
        self.pack_type = pack_type
        self.pack_contents = self._normalize_pack_contents(pack_type, pack_contents)
        self.selected_indexes = []
        
        # Determine how many cards can be selected
        self.cards_to_select = self._get_cards_to_select(pack_type)
        
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
        
        # Select the card
        self.selected_indexes.append(card_idx)
        self._sync_pack_state_to_unified_state()
        selected_item = self.pack_contents[card_idx]
        
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
            # Add consumable to inventory
            if len(self.state.consumables) < self.state.consumable_slots:
                self.state.consumables.append(item['consumable'])
                info['consumable_added'] = item['consumable']
                
                # Value based on consumable type
                if 'Planet' in item['consumable'] or item['consumable'].startswith(('Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto')):
                    reward = 8.0  # Planets are very valuable
                elif 'The' in item['consumable']:  # Tarot cards
                    reward = 5.0
                else:  # Spectral cards
                    reward = 10.0  # Spectral cards are rare and powerful
            else:
                info['error'] = 'No consumable slots available'
                reward = -1.0
        
        elif 'joker' in item:
            # Add joker to collection
            if self.state.add_joker(item['joker']):
                info['joker_added'] = item['joker'].name
                reward = 15.0  # Jokers are very valuable
            else:
                info['error'] = 'No joker slots available'
                reward = -1.0
        
        return reward, info

"""balatro_gym/balatro_game_v2.py - Simple game engine for Balatro environment"""

from typing import List, Tuple, Any, Optional
from enum import IntEnum
from balatro_gym.scoring.scoring_engine import HandType
from balatro_gym.core.cards import Card, Rank, Suit

class GameState(IntEnum):
    PLAYING = 0
    SHOP = 1
    GAME_OVER = 2

class BalatroGame:
    """Basic game engine that handles card mechanics"""
    
    def __init__(self, engine=None):
        self.engine = engine
        self.deck: List[Card] = []
        self.draw_pile_indexes: List[int] = []
        self.discard_pile_indexes: List[int] = []
        self.play_area_indexes: List[int] = []
        self.hand_indexes: List[int] = []
        self.highlighted_indexes: List[int] = []
        self.round_hands = 4
        self.round_discards = 3
        self.round_score = 0
        self.hand_size = 8
        self.discards = 3
        self.state = GameState.PLAYING
        self.blinds = [300, 450, 600]  # Small, big, boss
        self.blind_index = 0
        
    def highlight_card(self, idx: int):
        """Mark a card as selected/highlighted"""
        if idx not in self.highlighted_indexes and idx < len(self.hand_indexes):
            self.highlighted_indexes.append(idx)
    
    def unhighlight_card(self, idx: int):
        """Unmark a card"""
        if idx in self.highlighted_indexes:
            self.highlighted_indexes.remove(idx)
    
    def _classify_hand(self, cards: List[Card]) -> Tuple[HandType, Any]:
        """Classify poker hand from list of cards"""
        if not cards:
            return HandType.HIGH_CARD, None
            
        # Count ranks and suits
        rank_counts = {}
        suit_counts = {}
        ranks = []
        
        for card in cards:
            rank = card.rank.value
            suit = card.suit.value
            
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
            ranks.append(rank)
        
        # Sort rank counts
        counts = sorted(rank_counts.values(), reverse=True)
        is_flush = len(suit_counts) == 1 and len(cards) >= 5
        
        # Check for straight
        sorted_ranks = sorted(set(ranks))
        is_straight = False
        if len(sorted_ranks) >= 5:
            # Check for regular straight
            for i in range(len(sorted_ranks) - 4):
                if sorted_ranks[i+4] - sorted_ranks[i] == 4:
                    is_straight = True
                    break
            # Check for ace-low straight (A,2,3,4,5)
            if not is_straight and 14 in sorted_ranks and set([2,3,4,5]).issubset(set(sorted_ranks)):
                is_straight = True
        
        # Classify hand
        if is_straight and is_flush and len(cards) >= 5:
            return HandType.STRAIGHT_FLUSH, None
        elif len(counts) > 0 and counts[0] == 4:
            return HandType.FOUR_KIND, None
        elif len(counts) >= 2 and counts[0] == 3 and counts[1] == 2:
            return HandType.FULL_HOUSE, None
        elif is_flush and len(cards) >= 5:
            return HandType.FLUSH, None
        elif is_straight and len(cards) >= 5:
            return HandType.STRAIGHT, None
        elif len(counts) > 0 and counts[0] == 3:
            return HandType.THREE_KIND, None
        elif len(counts) >= 2 and counts[0] == 2 and counts[1] == 2:
            return HandType.TWO_PAIR, None
        elif len(counts) > 0 and counts[0] == 2:
            return HandType.ONE_PAIR, None
        else:
            return HandType.HIGH_CARD, None
    
    def _draw_cards(self):
        """Draw cards to fill hand up to hand_size"""
        self._ensure_card_zones()

        # Draw cards to fill hand
        cards_to_draw = min(self.hand_size - len(self.hand_indexes), len(self.draw_pile_indexes))
        for _ in range(cards_to_draw):
            self.hand_indexes.append(self.draw_pile_indexes.pop(0))

    def _ensure_card_zones(self):
        """Initialize and prune card-zone indexes without making discards draw-eligible."""
        valid_indexes = set(range(len(self.deck)))
        had_zone_state = bool(
            self.draw_pile_indexes or self.discard_pile_indexes or self.play_area_indexes
        )

        def unique_valid(indexes, excluded=None):
            excluded = excluded or set()
            result = []
            seen = set()
            for idx in indexes:
                if idx in valid_indexes and idx not in excluded and idx not in seen:
                    result.append(idx)
                    seen.add(idx)
            return result

        self.hand_indexes = unique_valid(self.hand_indexes)
        occupied = set(self.hand_indexes)
        self.play_area_indexes = unique_valid(self.play_area_indexes, occupied)
        occupied.update(self.play_area_indexes)
        self.discard_pile_indexes = unique_valid(self.discard_pile_indexes, occupied)
        occupied.update(self.discard_pile_indexes)
        self.draw_pile_indexes = unique_valid(self.draw_pile_indexes, occupied)

        occupied = (
            set(self.hand_indexes)
            | set(self.draw_pile_indexes)
            | set(self.discard_pile_indexes)
            | set(self.play_area_indexes)
        )
        missing = [idx for idx in range(len(self.deck)) if idx not in occupied]
        if not had_zone_state:
            self.draw_pile_indexes = missing
        else:
            self.draw_pile_indexes.extend(missing)
    
    def discard_hand(self):
        """Discard highlighted cards and draw new ones"""
        if self.round_discards <= 0:
            return False
            
        discarded_indexes = []
        for idx in sorted(self.highlighted_indexes, reverse=True):
            if idx < len(self.hand_indexes):
                discarded_indexes.append(self.hand_indexes.pop(idx))
        
        self.highlighted_indexes = []
        self.round_discards -= 1
        self.discard_pile_indexes.extend(reversed(discarded_indexes))
        
        # Draw new cards
        self._draw_cards()
        return True
    
    def play_hand(self):
        """Play the highlighted cards"""
        if self.round_hands <= 0:
            return None
            
        # Get the actual cards
        played_cards = []
        for idx in self.highlighted_indexes:
            if idx < len(self.hand_indexes):
                card_idx = self.hand_indexes[idx]
                if card_idx < len(self.deck):
                    played_cards.append(self.deck[card_idx])
        
        if not played_cards:
            return None
        
        # Classify the hand
        hand_type, _ = self._classify_hand(played_cards)
        
        # Calculate score (simplified)
        if self.engine:
            chips, mult = self.engine.get_hand_chips_mult(hand_type)
            score = chips * mult
        else:
            score = 100  # Default score
        
        self.round_score += score
        self.round_hands -= 1
        
        # Move played cards through play, then discard.
        played_indexes = []
        for idx in sorted(self.highlighted_indexes, reverse=True):
            if idx < len(self.hand_indexes):
                played_indexes.append(self.hand_indexes.pop(idx))
        
        self.highlighted_indexes = []
        self.play_area_indexes.extend(reversed(played_indexes))
        self.discard_pile_indexes.extend(self.play_area_indexes)
        self.play_area_indexes = []
        
        # Draw new cards
        self._draw_cards()
        
        return hand_type, score
    
    def reset_round(self):
        """Reset for new round"""
        self.round_hands = 4
        self.round_discards = 3
        self.round_score = 0
        self.draw_pile_indexes = list(range(len(self.deck)))
        self.discard_pile_indexes = []
        self.play_area_indexes = []
        self.hand_indexes = []
        self.highlighted_indexes = []
        self._draw_cards()
    
    def get_hand_cards(self) -> List[Card]:
        """Get the actual card objects in hand"""
        cards = []
        for idx in self.hand_indexes:
            if idx < len(self.deck):
                cards.append(self.deck[idx])
        return cards
    
    def get_highlighted_cards(self) -> List[Card]:
        """Get the highlighted card objects"""
        cards = []
        for idx in self.highlighted_indexes:
            if idx < len(self.hand_indexes):
                card_idx = self.hand_indexes[idx]
                if card_idx < len(self.deck):
                    cards.append(self.deck[card_idx])
        return cards

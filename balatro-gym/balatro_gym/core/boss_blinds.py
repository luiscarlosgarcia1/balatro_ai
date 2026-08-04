"""balatro_gym/boss_blinds.py - Complete Boss Blind System

Implements all boss blinds from Balatro with their unique debuff effects.
Boss blinds appear every 3rd round (ante X.3) and have special abilities that
make the round more challenging.
"""

from __future__ import annotations
from enum import IntEnum, auto
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import random

# ---------------------------------------------------------------------------
# Boss Blind Types
# ---------------------------------------------------------------------------

class BossBlindType(IntEnum):
    # Common Boss Blinds
    THE_HOOK = auto()      # Discards 2 random cards per hand
    THE_WALL = auto()      # Extra large blind (2x base chips)
    THE_WHEEL = auto()     # 1 in 7 cards get drawn face down
    THE_HOUSE = auto()     # First hand drawn face down
    THE_MARK = auto()      # All face cards drawn face down
    THE_FISH = auto()      # Cards drawn face down after each hand played
    THE_PSYCHIC = auto()   # Must play 5 cards
    THE_GOAD = auto()      # All Spades are debuffed
    THE_WATER = auto()     # Start with 0 discards
    THE_WINDOW = auto()    # All Diamonds are debuffed
    THE_MANACLE = auto()   # -1 Hand Size
    THE_EYE = auto()       # No repeat hand types this round
    THE_MOUTH = auto()     # Play only 1 hand type this round
    THE_PLANT = auto()     # All face cards are debuffed
    THE_SERPENT = auto()   # After each hand, always draw 3 cards
    THE_PILLAR = auto()    # Cards played previously are debuffed
    THE_NEEDLE = auto()    # Play only 1 hand
    THE_HEAD = auto()      # All Hearts are debuffed
    THE_CLUB = auto()      # All Clubs are debuffed
    THE_TOOTH = auto()     # Lose $1 per card played
    THE_FLINT = auto()     # Base chips and mult halved
    THE_OX = auto()        # Most-played hand sets money to $0
    THE_ARM = auto()       # Decrease level of played poker hand
    THE_VIOLET = auto()    # All cards are debuffed
    THE_VERDANT = auto()   # Required cards scale up by 1 per hand until 7
    THE_AMBER = auto()     # Flips and shuffles all Jokers
    THE_CRIMSON = auto()   # All Heart cards are flipped
    THE_CERULEAN = auto()  # All cards in deck are flipped

@dataclass
class BossBlind:
    """Boss blind configuration"""
    blind_type: BossBlindType
    name: str
    description: str
    mult: float = 1.0  # Chip requirement multiplier
    money_reward: int = 5  # Extra money for defeating
    min_ante: int = 1
    showdown: bool = False
    
    # Effect functions
    on_round_start: Optional[Callable] = None
    on_hand_drawn: Optional[Callable] = None
    on_card_played: Optional[Callable] = None
    on_hand_scored: Optional[Callable] = None
    on_discard: Optional[Callable] = None
    can_play_hand: Optional[Callable] = None
    modify_card_score: Optional[Callable] = None

# ---------------------------------------------------------------------------
# Boss Blind Definitions
# ---------------------------------------------------------------------------

BOSS_BLINDS: Dict[BossBlindType, BossBlind] = {
    BossBlindType.THE_HOOK: BossBlind(
        blind_type=BossBlindType.THE_HOOK,
        name="The Hook",
        description="Discards 2 random cards per hand",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_WALL: BossBlind(
        blind_type=BossBlindType.THE_WALL,
        name="The Wall",
        description="Extra large blind",
        mult=4.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_WHEEL: BossBlind(
        blind_type=BossBlindType.THE_WHEEL,
        name="The Wheel",
        description="1 in 7 cards get drawn face down",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_HOUSE: BossBlind(
        blind_type=BossBlindType.THE_HOUSE,
        name="The House",
        description="First hand drawn face down",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_MARK: BossBlind(
        blind_type=BossBlindType.THE_MARK,
        name="The Mark",
        description="All face cards drawn face down",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_FISH: BossBlind(
        blind_type=BossBlindType.THE_FISH,
        name="The Fish",
        description="Cards drawn face down after each hand played",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_PSYCHIC: BossBlind(
        blind_type=BossBlindType.THE_PSYCHIC,
        name="The Psychic",
        description="Must play 5 cards",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_GOAD: BossBlind(
        blind_type=BossBlindType.THE_GOAD,
        name="The Goad",
        description="All Spades are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_WATER: BossBlind(
        blind_type=BossBlindType.THE_WATER,
        name="The Water",
        description="Start with 0 discards",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_WINDOW: BossBlind(
        blind_type=BossBlindType.THE_WINDOW,
        name="The Window",
        description="All Diamonds are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_MANACLE: BossBlind(
        blind_type=BossBlindType.THE_MANACLE,
        name="The Manacle",
        description="-1 Hand Size",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_EYE: BossBlind(
        blind_type=BossBlindType.THE_EYE,
        name="The Eye",
        description="No repeat hand types this round",
        mult=2.0,
        money_reward=5,
        min_ante=3
    ),
    
    BossBlindType.THE_MOUTH: BossBlind(
        blind_type=BossBlindType.THE_MOUTH,
        name="The Mouth",
        description="Play only 1 hand type this round",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_PLANT: BossBlind(
        blind_type=BossBlindType.THE_PLANT,
        name="The Plant",
        description="All face cards are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=4
    ),
    
    BossBlindType.THE_SERPENT: BossBlind(
        blind_type=BossBlindType.THE_SERPENT,
        name="The Serpent",
        description="After each hand, always draw 3 cards",
        mult=2.0,
        money_reward=5,
        min_ante=5
    ),
    
    BossBlindType.THE_PILLAR: BossBlind(
        blind_type=BossBlindType.THE_PILLAR,
        name="The Pillar",
        description="Cards played previously are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_NEEDLE: BossBlind(
        blind_type=BossBlindType.THE_NEEDLE,
        name="The Needle",
        description="Play only 1 hand",
        mult=1.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_HEAD: BossBlind(
        blind_type=BossBlindType.THE_HEAD,
        name="The Head",
        description="All Hearts are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_CLUB: BossBlind(
        blind_type=BossBlindType.THE_CLUB,
        name="The Club",
        description="All Clubs are debuffed",
        mult=2.0,
        money_reward=5,
        min_ante=1
    ),
    
    BossBlindType.THE_TOOTH: BossBlind(
        blind_type=BossBlindType.THE_TOOTH,
        name="The Tooth",
        description="Lose $1 per card played",
        mult=2.0,
        money_reward=5,
        min_ante=3
    ),
    
    BossBlindType.THE_FLINT: BossBlind(
        blind_type=BossBlindType.THE_FLINT,
        name="The Flint",
        description="Base chips and mult halved",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_OX: BossBlind(
        blind_type=BossBlindType.THE_OX,
        name="The Ox",
        description="Playing the most played hand sets money to $0",
        mult=2.0,
        money_reward=5,
        min_ante=6
    ),
    
    BossBlindType.THE_ARM: BossBlind(
        blind_type=BossBlindType.THE_ARM,
        name="The Arm",
        description="Decrease level of played poker hand",
        mult=2.0,
        money_reward=5,
        min_ante=2
    ),
    
    BossBlindType.THE_VIOLET: BossBlind(
        blind_type=BossBlindType.THE_VIOLET,
        name="Violet Vessel",
        description="Very large blind",
        mult=6.0,
        money_reward=8,
        min_ante=10,
        showdown=True
    ),
    
    BossBlindType.THE_VERDANT: BossBlind(
        blind_type=BossBlindType.THE_VERDANT,
        name="Verdant Leaf",
        description="All cards debuffed until 1 Joker sold",
        mult=2.0,
        money_reward=8,
        min_ante=10,
        showdown=True
    ),
    
    BossBlindType.THE_AMBER: BossBlind(
        blind_type=BossBlindType.THE_AMBER,
        name="Amber Acorn",
        description="Flips and shuffles all Jokers",
        mult=2.0,
        money_reward=8,
        min_ante=10,
        showdown=True
    ),
    
    BossBlindType.THE_CRIMSON: BossBlind(
        blind_type=BossBlindType.THE_CRIMSON,
        name="Crimson Heart",
        description="One random Joker disabled every hand",
        mult=2.0,
        money_reward=8,
        min_ante=10,
        showdown=True
    ),
    
    BossBlindType.THE_CERULEAN: BossBlind(
        blind_type=BossBlindType.THE_CERULEAN,
        name="Cerulean Bell",
        description="Forces 1 card to always be selected",
        mult=2.0,
        money_reward=8,
        min_ante=10,
        showdown=True
    ),
}

# ---------------------------------------------------------------------------
# Boss Blind Manager
# ---------------------------------------------------------------------------

class BossBlindManager:
    """Manages boss blind effects and state"""
    
    def __init__(self, rng: Any | None = None):
        self.active_blind: Optional[BossBlind] = None
        self.blind_state: Dict[str, Any] = {}
        self.rng = rng
        
    def activate_boss_blind(self, blind_type: BossBlindType, game_state: Dict) -> Dict[str, Any]:
        """Activate a boss blind and apply initial effects"""
        self.active_blind = BOSS_BLINDS[blind_type]
        self.blind_state = {
            'played_hand_types': set(),
            'played_cards': set(),
            'first_hand': True,
            'prepped': False,
            'hands_played': 0,
            'cards_required': 5,  # For The Verdant
            'disabled_joker_slots': 0,
            'face_down_cards': set(),
            'forced_card_ref': None,
            'original_discards': int(game_state.get('discards_left', 0) or 0),
            'original_hands': int(game_state.get('hands_left', 0) or 0),
            'original_hand_size': int(game_state.get('hand_size', 0) or 0),
        }
        
        effects = {
            'message': f"{self.active_blind.name}: {self.active_blind.description}",
            'chip_mult': self.active_blind.mult,
            'modifications': {}
        }
        
        # Apply initial effects based on blind type
        if blind_type == BossBlindType.THE_WATER:
            effects['modifications']['discards'] = 0
            
        elif blind_type == BossBlindType.THE_MANACLE:
            effects['modifications']['hand_size'] = -1
            
        elif blind_type == BossBlindType.THE_NEEDLE:
            effects['modifications']['hands'] = 1

        elif blind_type == BossBlindType.THE_AMBER:
            joker_indexes = self._shuffle_amber_jokers(len(game_state.get('jokers', [])))
            effects['modifications']['joker_order'] = joker_indexes
            effects['modifications']['hidden_joker_indexes'] = list(range(len(joker_indexes)))
        elif blind_type == BossBlindType.THE_CRIMSON:
            # Crimson consumes an already-armed prep state on the first hand draw.
            self.blind_state['prepped'] = True
            
        return effects
    
    def on_hand_drawn(self, hand_cards: List[Any], game_state: Dict) -> Dict[str, Any]:
        """Apply effects when hand is drawn"""
        if not self.active_blind:
            return {}
            
        effects = {'face_down_cards': [], 'discarded_cards': []}
        
        if self.active_blind.blind_type == BossBlindType.THE_WHEEL:
            # Balatro scales Wheel by the run's normal probability layer.
            flip_chance = self._normal_probability(game_state) / 7
            for i, card in enumerate(hand_cards):
                if self.rng is not None:
                    roll = self.rng.get_float('boss_abilities')
                else:
                    roll = random.random()
                if roll < flip_chance:
                    effects['face_down_cards'].append(i)
                    
        elif self.active_blind.blind_type == BossBlindType.THE_HOUSE:
            # First hand all face down
            if self.blind_state['first_hand'] and game_state.get('discards_used_this_round', 0) == 0:
                effects['face_down_cards'] = list(range(len(hand_cards)))
                
        elif self.active_blind.blind_type == BossBlindType.THE_MARK:
            # Face cards face down
            for i, card in enumerate(hand_cards):
                if self._is_face_card(card):
                    effects['face_down_cards'].append(i)
                    
        elif self.active_blind.blind_type == BossBlindType.THE_FISH:
            # All face down on the draw after a hand is played.
            if self.blind_state.get('prepped'):
                effects['face_down_cards'] = list(range(len(hand_cards)))
                self.blind_state['prepped'] = False

        elif self.active_blind.blind_type == BossBlindType.THE_CRIMSON:
            joker_count = int(game_state.get('all_joker_count', len(game_state.get('jokers', []))))
            if self.blind_state.get('prepped') and joker_count > 0:
                joker_entries = list(game_state.get('jokers', []) or [])
                candidate_indexes = [
                    index
                    for index, joker in enumerate(joker_entries[:joker_count])
                    if not (
                        bool(joker.get('disabled', False))
                        if isinstance(joker, dict)
                        else bool(getattr(joker, 'disabled', False))
                    )
                ]
                if joker_count < 2 or not candidate_indexes:
                    candidate_indexes = list(range(joker_count))
                if self.rng is not None:
                    disabled = self.rng.choice('boss_abilities', candidate_indexes)
                else:
                    disabled = random.choice(candidate_indexes)
                effects['disabled_joker_indexes'] = [disabled]
            self.blind_state['prepped'] = False

        elif self.active_blind.blind_type == BossBlindType.THE_CERULEAN:
            if hand_cards:
                forced = None
                forced_ref = self.blind_state.get('forced_card_ref')
                if forced_ref is not None:
                    for i, card in enumerate(hand_cards):
                        if id(card) == forced_ref:
                            forced = i
                            break
                if forced is None:
                    indexes = list(range(len(hand_cards)))
                    if self.rng is not None:
                        forced = self.rng.choice('boss_abilities', indexes)
                    else:
                        forced = random.choice(indexes)
                    self.blind_state['forced_card_ref'] = id(hand_cards[forced])
                effects['forced_selected_card'] = forced
        
        return effects

    def on_press_play(
        self,
        hand_cards: List[Any],
        selected_indexes: List[int],
        game_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply effects that trigger when the player presses play."""
        if not self.active_blind:
            return {}

        effects: Dict[str, Any] = {}
        blind_type = self.active_blind.blind_type
        if blind_type == BossBlindType.THE_FISH:
            self.blind_state['prepped'] = True
            return effects
        if blind_type == BossBlindType.THE_CRIMSON:
            self.blind_state['prepped'] = True
            return effects
        if blind_type == BossBlindType.THE_TOOTH:
            effects['money'] = max(0, int(game_state.get('money', 0)) - len(selected_indexes))
            return effects
        if blind_type == BossBlindType.THE_HOOK and hand_cards:
            indexes = list(range(len(hand_cards)))
            discard_count = min(2, len(indexes))
            if discard_count <= 0:
                return effects

            if self.rng is not None:
                discarded_cards = self.rng.sample('boss_abilities', indexes, discard_count)
            else:
                discarded_cards = random.sample(indexes, discard_count)
            effects['discarded_cards'] = discarded_cards
        return effects
    
    def can_play_hand(self, selected_cards: List[Any], hand_type: str) -> Tuple[bool, str]:
        """Check if hand can be played given boss blind restrictions"""
        if not self.active_blind:
            return True, ""
            
        if self.active_blind.blind_type == BossBlindType.THE_PSYCHIC:
            # Must play exactly 5 cards
            if len(selected_cards) != 5:
                return False, "Must play exactly 5 cards"
                
        elif self.active_blind.blind_type == BossBlindType.THE_EYE:
            # No repeat hand types
            if hand_type in self.blind_state['played_hand_types']:
                return False, f"Cannot play {hand_type} again"
                
        elif self.active_blind.blind_type == BossBlindType.THE_MOUTH:
            # Only one hand type allowed
            if self.blind_state['played_hand_types'] and hand_type not in self.blind_state['played_hand_types']:
                allowed = list(self.blind_state['played_hand_types'])[0]
                return False, f"Can only play {allowed}"
                
        return True, ""
    
    def modify_scoring(self, base_chips: int, base_mult: int, 
                      played_cards: List[Any], hand_type: str) -> Tuple[int, int]:
        """Modify scoring based on boss blind effects"""
        if not self.active_blind:
            return base_chips, base_mult
            
        chips = base_chips
        mult = base_mult
        
        # Debuff effects
        if self.active_blind.blind_type == BossBlindType.THE_FLINT:
            # Halve base values
            chips = int(chips * 0.5 + 0.5)
            mult = max(1, int(mult * 0.5 + 0.5))
            
        return chips, mult
    
    def _is_card_debuffed(self, card) -> bool:
        """Check if a card is debuffed by current boss blind"""
        if not self.active_blind:
            return False
            
        # Suit debuffs
        if hasattr(card, 'suit'):
            suit = self._suit_name(card)
            if self.active_blind.blind_type == BossBlindType.THE_GOAD and suit == 'Spades':
                return True
            elif self.active_blind.blind_type == BossBlindType.THE_WINDOW and suit == 'Diamonds':
                return True
            elif self.active_blind.blind_type == BossBlindType.THE_HEAD and suit == 'Hearts':
                return True
            elif self.active_blind.blind_type == BossBlindType.THE_CLUB and suit == 'Clubs':
                return True
                
        # Rank debuffs
        if hasattr(card, 'rank'):
            if self.active_blind.blind_type == BossBlindType.THE_PLANT and self._is_face_card(card):
                return True
                
        # Universal debuffs
        # Previously played cards
        if self.active_blind.blind_type == BossBlindType.THE_PILLAR:
            card_id = getattr(card, 'id', None) or id(card)
            played_this_ante = getattr(getattr(card, "card_state", None), "played_this_ante", False)
            if played_this_ante or card_id in self.blind_state.get('played_cards', set()):
                return True

        if self.active_blind.blind_type == BossBlindType.THE_VERDANT:
            return True
        
        return False

    @staticmethod
    def _rank_value(card: Any) -> int:
        rank = getattr(card, "rank", 0)
        return rank.value if hasattr(rank, "value") else int(rank or 0)

    @staticmethod
    def _suit_name(card: Any) -> str:
        suit = getattr(card, "suit", "")
        if hasattr(suit, "name"):
            return str(suit.name).replace("_", " ").title()
        return str(suit).replace("_", " ").title()

    def _is_face_card(self, card: Any) -> bool:
        return self._rank_value(card) in {11, 12, 13}

    @staticmethod
    def _normal_probability(game_state: Dict[str, Any]) -> float:
        """Return the run's normal probability multiplier for boss chance effects."""
        jokers = list(game_state.get("jokers", []) or [])
        multiplier = 1.0
        for joker in jokers:
            if isinstance(joker, dict):
                joker_name = joker.get("name")
                disabled = bool(joker.get("disabled", False))
            else:
                joker_name = getattr(joker, "name", joker)
                disabled = bool(getattr(joker, "disabled", False))
            if disabled:
                continue
            if joker_name == "Oops! All 6s":
                multiplier *= 2.0
        return multiplier
    
    def on_hand_scored(self, played_cards: List[Any], hand_type: str, game_state: Dict):
        """Update state after hand is scored"""
        if not self.active_blind:
            return
            
        # Update played hand types
        self.blind_state['played_hand_types'].add(hand_type)
        game_state['boss_played_hand_types'] = sorted(self.blind_state['played_hand_types'])
        self.blind_state['first_hand'] = False
        self.blind_state['hands_played'] += 1
        
        # Track played cards for The Pillar
        if self.active_blind.blind_type == BossBlindType.THE_PILLAR:
            for card in played_cards:
                card_id = getattr(card, 'id', None) or id(card)
                self.blind_state['played_cards'].add(card_id)
                
    def get_disabled_joker_count(self) -> int:
        """Get number of disabled joker slots"""
        return self.blind_state.get('disabled_joker_slots', 0)

    def _shuffle_amber_jokers(self, joker_count: int) -> List[int]:
        """Mirror Amber Acorn's three deterministic Lua-side shuffles."""
        joker_indexes = list(range(joker_count))
        if joker_count <= 1:
            return joker_indexes

        for _ in range(3):
            if self.rng is not None:
                self.rng.shuffle('boss_abilities', joker_indexes)
            else:
                random.shuffle(joker_indexes)
        return joker_indexes

    def clear_cerulean_forced_selection(self, state: Any | None = None) -> None:
        """Forget Cerulean's forced-card identity before a discard redraw."""
        self.blind_state['forced_card_ref'] = None
        if state is not None:
            state.boss_forced_selected_card = None

    def disable_boss_blind(
        self,
        state: Any,
        game: Any | None = None,
        *,
        restore_round_resources: bool = True,
        preserve_boss_round_identity: bool = False,
        draw_restored_manacle_card: bool = True,
        restore_chip_thresholds: bool = True,
    ) -> None:
        """Disable the active boss blind and revert modeled stateful effects."""
        blind = self.active_blind
        blind_type = getattr(blind, "blind_type", getattr(state, "active_boss_blind", None))
        if blind_type is None:
            return

        original_discards = int(self.blind_state.get('original_discards', getattr(state, 'discards_left', 0)) or 0)
        original_hands = int(self.blind_state.get('original_hands', getattr(state, 'hands_left', 0)) or 0)
        original_hand_size = int(self.blind_state.get('original_hand_size', getattr(state, 'hand_size', 0)) or 0)
        base_chips = self.blind_state.get('base_chips')

        if blind_type == BossBlindType.THE_WATER and restore_round_resources:
            state.discards_left = original_discards
            if game is not None and hasattr(game, 'round_discards'):
                game.round_discards = original_discards

        if blind_type == BossBlindType.THE_NEEDLE and restore_round_resources:
            state.hands_left = original_hands
            if game is not None and hasattr(game, 'round_hands'):
                game.round_hands = original_hands

        if blind_type == BossBlindType.THE_MANACLE and restore_round_resources:
            restored_hand_size = max(1, int(getattr(state, 'hand_size', 0) or 0) + 1)

            state.hand_size = restored_hand_size
            if game is not None and hasattr(game, 'hand_size'):
                game.hand_size = restored_hand_size
            if (
                draw_restored_manacle_card
                and len(getattr(state, 'hand_indexes', [])) < state.hand_size
                and getattr(state, 'draw_pile_indexes', [])
            ):
                cards_to_draw = min(state.hand_size - len(state.hand_indexes), len(state.draw_pile_indexes))
                for _ in range(cards_to_draw):
                    state.hand_indexes.append(state.draw_pile_indexes.pop(0))
                if game is not None and hasattr(game, 'hand_indexes'):
                    game.hand_indexes = state.hand_indexes.copy()
                    if hasattr(game, 'draw_pile_indexes'):
                        game.draw_pile_indexes = state.draw_pile_indexes.copy()

        if (
            restore_chip_thresholds
            and base_chips is not None
            and blind_type in {BossBlindType.THE_WALL, BossBlindType.THE_VIOLET}
        ):
            state.chips_needed = int(base_chips)
            if game is not None and hasattr(game, 'blinds') and hasattr(game, 'blind_index'):
                blind_index = int(getattr(game, 'blind_index', 2))
                if 0 <= blind_index < len(game.blinds):
                    game.blinds[blind_index] = state.chips_needed

        state.face_down_cards = []
        state.force_draw_count = None
        state.boss_disabled_joker_indexes = []
        state.hidden_joker_indexes = []
        state.disabled_joker_slots = 0
        state.boss_forced_selected_card = None
        state.boss_discard_random_count = 0
        state.boss_played_hand_types = []
        state.boss_round_ox_target_hand = None

        for card_state in getattr(state, 'card_states', {}).values():
            card_state.is_face_down = False
            card_state.is_debuffed = False

        state.boss_blind_active = False
        state.active_boss_blind = blind_type if preserve_boss_round_identity else None
        self.deactivate()
    
    def deactivate(self):
        """Clear boss blind effects"""
        self.active_blind = None
        self.blind_state = {}

# ---------------------------------------------------------------------------
# Integration with Environment
# ---------------------------------------------------------------------------

def select_boss_blind(
    ante: int,
    exclude: Optional[List[BossBlindType]] = None,
    rng: Any | None = None,
    bosses_used: Optional[Dict[BossBlindType, int]] = None,
    win_ante: int = 8,
) -> BossBlindType:
    """Select a Balatro-eligible boss and increment its offer usage."""
    ante_for_eligibility = max(1, ante)
    excluded = set(exclude or [])
    eligible_blinds: List[BossBlindType] = []

    for blind_type, blind in BOSS_BLINDS.items():
        if blind_type in excluded:
            continue

        is_showdown_round = ante % win_ante == 0 and ante >= 2
        if blind.showdown:
            if is_showdown_round:
                eligible_blinds.append(blind_type)
        elif blind.min_ante <= ante_for_eligibility and not is_showdown_round:
            eligible_blinds.append(blind_type)

    if not eligible_blinds:
        for blind_type, blind in BOSS_BLINDS.items():
            if blind_type not in excluded and not blind.showdown:
                eligible_blinds.append(blind_type)

    usage = bosses_used if bosses_used is not None else {}
    min_use = min(usage.get(blind_type, 0) for blind_type in eligible_blinds)
    least_used_blinds = [
        blind_type
        for blind_type in eligible_blinds
        if usage.get(blind_type, 0) == min_use
    ]

    if rng is not None:
        selected = rng.choice('blind_selection', least_used_blinds)
    else:
        selected = random.choice(least_used_blinds)

    usage[selected] = usage.get(selected, 0) + 1
    return selected

# ---------------------------------------------------------------------------
# Example Usage in Environment
# ---------------------------------------------------------------------------

"""
# In your BalatroEnv class:

def __init__(self):
    # ... existing init code ...
    self.boss_blind_manager = BossBlindManager()
    self.active_boss_blind = None

def _step_blind_select(self, action: int):
    # ... existing code ...
    
    if blind_type == 2:  # Boss blind
        # Select and activate boss blind
        boss_type = select_boss_blind(self.ante)
        effects = self.boss_blind_manager.activate_boss_blind(boss_type, self.game_state)
        
        # Apply chip multiplier
        self.chips_needed = int(self.chips_needed * effects['chip_mult'])
        
        # Apply modifications
        if 'discards' in effects['modifications']:
            self.game.discards = effects['modifications']['discards']
        if 'hand_size' in effects['modifications']:
            self.game.hand_size += effects['modifications']['hand_size']
        if 'hands' in effects['modifications']:
            self.game.hands = effects['modifications']['hands']
            
        self.active_boss_blind = boss_type
        info['boss_blind'] = self.boss_blind_manager.active_blind.name
        info['boss_effect'] = self.boss_blind_manager.active_blind.description

def _step_play(self, action: int):
    # When drawing cards
    if need_to_draw:
        effects = self.boss_blind_manager.on_hand_drawn(hand_cards, self.game_state)
        # Apply face down effects
        # Apply discard effects
    
    # Before playing hand
    if action == ACTION_PLAY_HAND:
        can_play, message = self.boss_blind_manager.can_play_hand(selected_cards, hand_type)
        if not can_play:
            return self._get_observation(), -1.0, False, False, {'error': message}
    
    # When scoring
    base_chips, base_mult = self.engine.get_hand_chips_mult(hand_type)
    chips, mult = self.boss_blind_manager.modify_scoring(base_chips, base_mult, played_cards, hand_type)
    
    # After scoring
    self.boss_blind_manager.on_hand_scored(played_cards, hand_type, self.game_state)

def _advance_round(self):
    # ... existing code ...
    
    # Deactivate boss blind when round ends
    if self.boss_blind_manager.active_blind:
        # Award extra money for beating boss
        self.player.chips += self.boss_blind_manager.active_blind.money_reward
        self.boss_blind_manager.deactivate()
        self.active_boss_blind = None
"""

"""State management for Balatro RL environment.

This module contains all state-related classes including the unified game state
that serves as the single source of truth for the entire game, and card state
tracking for enhancements, editions, and seals.
"""

from dataclasses import dataclass, field
import random
from typing import Dict, List, Any, Optional
from enum import Enum

from balatro_gym.core.cards import Card, Enhancement, Edition, Rank, Seal, Suit
from balatro_gym.core.constants import Phase
from balatro_gym.scoring.scoring_engine import HandType
from balatro_gym.core.jokers import JOKER_LIBRARY, JOKER_RARITY_BY_ID, JokerInfo
from balatro_gym.core.boss_blinds import BossBlindType


@dataclass
class CardState:
    """Tracks per-card state including enhancements, editions, and seals."""
    
    card_index: int
    enhancement: Enhancement = Enhancement.NONE
    edition: Edition = Edition.NONE
    seal: Seal = Seal.NONE
    
    # Tracking for effects
    times_played: int = 0
    times_scored: int = 0
    times_discarded: int = 0
    times_held: int = 0
    
    # Special flags
    is_debuffed: bool = False
    is_face_down: bool = False
    is_destroyed: bool = False
    played_this_ante: bool = False
    
    def calculate_chip_bonus(self, base_chips: int) -> int:
        """Calculate modified chip value based on enhancements."""
        if self.enhancement == Enhancement.BONUS:
            return base_chips + 30
        elif self.enhancement == Enhancement.STONE:
            return 50  # Stone cards always give +50 chips
        else:
            return base_chips
    
    def calculate_mult_bonus(self, base_mult: int) -> int:
        """Calculate modified mult value based on enhancements."""
        if self.enhancement == Enhancement.MULT:
            return base_mult + 4
        else:
            return base_mult
    
    def get_x_mult(self) -> float:
        """Get multiplicative mult from enhancements."""
        if self.enhancement == Enhancement.GLASS:
            return 2.0
        return 1.0
    
    def copy(self) -> 'CardState':
        """Create a deep copy of the card state."""
        return CardState(
            card_index=self.card_index,
            enhancement=self.enhancement,
            edition=self.edition,
            seal=self.seal,
            times_played=self.times_played,
            times_scored=self.times_scored,
            times_discarded=self.times_discarded,
            times_held=self.times_held,
            is_debuffed=self.is_debuffed,
            is_face_down=self.is_face_down,
            is_destroyed=self.is_destroyed,
            played_this_ante=self.played_this_ante
        )


@dataclass
class UnifiedGameState:
    """Single source of truth for all game state.
    
    This class contains all game state that needs to be tracked across
    different systems. It serves as the central state store that all
    game systems read from and write to.
    """
    
    # Core game state
    ante: int = 1
    round: int = 1  # 1=small, 2=big, 3=boss
    phase: Phase = Phase.BLIND_SELECT
    chips_needed: int = 300
    chips_scored: int = 0  # Total career chips scored
    round_chips_scored: int = 0  # Chips scored in current round only
    money: int = 4
    win_ante: int = 8
    won: bool = False
    game_over: bool = False
    round_eval_cashout: int = 0
    round_eval_completed_round: Optional[int] = None
    
    # Cards and hands
    deck: List[Card] = field(default_factory=list)
    draw_pile_indexes: List[int] = field(default_factory=list)
    discard_pile_indexes: List[int] = field(default_factory=list)
    play_area_indexes: List[int] = field(default_factory=list)
    hand_indexes: List[int] = field(default_factory=list)  # Indexes into deck
    selected_cards: List[int] = field(default_factory=list)  # Indexes into hand_indexes
    hands_left: int = 4
    discards_left: int = 3
    hand_size: int = 8
    money_per_hand: Optional[int] = None
    money_per_discard: Optional[int] = None
    no_extra_hand_money: bool = False
    no_interest: bool = False
    
    # Collections
    jokers: List[JokerInfo] = field(default_factory=list)
    consumables: List[str] = field(default_factory=list)  # Consumable names
    vouchers: List[str] = field(default_factory=list)  # Voucher names
    joker_slots: int = 5
    consumable_slots: int = 2
    last_tarot_planet_consumable: Optional[str] = None
    
    # Shop state
    shop_inventory: List[Any] = field(default_factory=list)
    shop_reroll_cost: int = 5
    pending_pack_consumable: Optional[str] = None
    pending_pack_index: Optional[int] = None
    
    # Statistics
    hands_played_total: int = 0
    hands_played_ante: int = 0
    last_hand_played: Optional[str] = None
    last_held_card_indexes: Optional[List[int]] = None
    best_hand_this_ante: int = 0
    jokers_sold: int = 0
    cards_discarded_total: int = 0
    discards_used_this_round: int = 0
    rerolls_used: int = 0
    shop_visits: int = 0
    unique_planet_cards_used: List[str] = field(default_factory=list)
    
    # Hand levels (HandType -> level)
    hand_levels: Dict[HandType, int] = field(default_factory=dict)
    
    # Card states (card index -> CardState)
    card_states: Dict[int, CardState] = field(default_factory=dict)
    
    # Boss blind state
    active_boss_blind: Optional[BossBlindType] = None
    pending_boss_blind: Optional[BossBlindType] = None
    boss_blind_active: bool = False
    boss_blind_rerolls_used_ante: int = 0
    bosses_used: Dict[BossBlindType, int] = field(default_factory=dict)
    face_down_cards: List[int] = field(default_factory=list)  # Indexes into hand_indexes
    force_draw_count: Optional[int] = None  # For The Serpent boss
    disabled_joker_slots: int = 0  # For The Plant boss
    boss_disabled_joker_indexes: List[int] = field(default_factory=list)
    hidden_joker_indexes: List[int] = field(default_factory=list)
    boss_forced_selected_card: Optional[int] = None
    boss_discard_random_count: int = 0
    boss_played_hand_types: List[str] = field(default_factory=list)
    boss_round_ox_target_hand: Optional[HandType] = None
    
    # Special game modes/effects
    eternal_jokers: List[int] = field(default_factory=list)  # Indexes of eternal jokers
    perishable_counters: Dict[int, int] = field(default_factory=dict)  # Joker index -> rounds left
    rental_jokers: List[int] = field(default_factory=list)  # Indexes of rental jokers
    rocket_payouts: Dict[int, int] = field(default_factory=dict)  # Joker index -> current round-end payout
    negative_jokers: List[int] = field(default_factory=list)  # Indexes of jokers with Negative edition
    negative_consumables: List[int] = field(default_factory=list)  # Indexes of consumables with Negative edition
    invisible_joker_rounds: Dict[int, int] = field(default_factory=dict)  # Joker index -> rounds survived
    madness_xmult: Dict[int, float] = field(default_factory=dict)  # Joker index -> persistent xMult
    joker_sell_value_bonuses: Dict[int, int] = field(default_factory=dict)  # Joker index -> extra sell value
    consumable_sell_value_bonuses: Dict[int, int] = field(default_factory=dict)  # Consumable index -> extra sell value
    burglar_bonus_hands_this_round: int = 0
    certificate_card_created_this_blind: bool = False
    passive_hand_size_bonus_applied: int = 0
    passive_hands_bonus_applied: int = 0
    passive_discards_bonus_applied: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for joker effects and other systems.
        
        This is used by various game systems that expect state in dictionary format.
        """
        # Get cards in hand
        hand_cards = []
        for idx in self.hand_indexes:
            if 0 <= idx < len(self.deck):
                hand_cards.append(self.deck[idx])
        
        return {
            # Core state
            'deck': self.deck,
            'hand': hand_cards,
            'jokers': [
                {
                    'name': j.name,
                    'id': j.id,
                    'base_cost': j.base_cost,
                    'sell_value': self.get_joker_sell_value(i),
                    'disabled': i in self.boss_disabled_joker_indexes,
                    'hidden': i in self.hidden_joker_indexes,
                }
                for i, j in enumerate(self.jokers)
            ],
            'consumables': self.consumables,
            'consumable_sell_value_bonuses': self.consumable_sell_value_bonuses.copy(),
            'vouchers': self.vouchers,
            'money': self.money,
            'win_ante': self.win_ante,
            'won': self.won,
            'game_over': self.game_over,
            'round_eval_cashout': self.round_eval_cashout,
            'round_eval_completed_round': self.round_eval_completed_round,
            'ante': self.ante,
            'round': self.round,
            'phase': self.phase.value,
            
            # Hand/discard state
            'draw_pile_indexes': self.draw_pile_indexes,
            'discard_pile_indexes': self.discard_pile_indexes,
            'play_area_indexes': self.play_area_indexes,
            'hands_left': self.hands_left,
            'discards_left': self.discards_left,
            'hand_size': self.hand_size,
            'money_per_hand': self.money_per_hand,
            'money_per_discard': self.money_per_discard,
            'no_extra_hand_money': self.no_extra_hand_money,
            'no_interest': self.no_interest,
            'joker_slots': self.joker_slots,
            'consumable_slots': self.consumable_slots,
            'last_tarot_planet_consumable': self.last_tarot_planet_consumable,
            
            # Statistics
            'hands_played': self.hands_played_total,
            'hands_played_ante': self.hands_played_ante,
            'last_hand_played': self.last_hand_played,
            'last_held_card_indexes': self.last_held_card_indexes,
            'round_chips_scored': self.round_chips_scored,
            'chips_scored': self.chips_scored,
            'chips_needed': self.chips_needed,
            'discards_used_this_round': self.discards_used_this_round,
            'pending_pack_consumable': self.pending_pack_consumable,
            'pending_pack_index': self.pending_pack_index,
            
            # Special states
            'boss_blind_active': self.boss_blind_active,
            'active_boss_blind': self.active_boss_blind.name if self.active_boss_blind else None,
            'pending_boss_blind': self.pending_boss_blind.name if self.pending_boss_blind else None,
            'bosses_used': {boss.name: count for boss, count in self.bosses_used.items()},
            'face_down_cards': self.face_down_cards,
            'hidden_joker_indexes': self.hidden_joker_indexes.copy(),
            'boss_played_hand_types': self.boss_played_hand_types.copy(),
            'boss_round_ox_target_hand': (
                self.boss_round_ox_target_hand.name.replace('_', ' ').title()
                if self.boss_round_ox_target_hand is not None
                else None
            ),
            
            # Collections info
            'joker_count': len(self.jokers),
            'all_joker_count': len(self.jokers),
            'boss_disabled_joker_indexes': self.boss_disabled_joker_indexes.copy(),
            'consumable_count': self.active_consumable_count(),
            'voucher_count': len(self.vouchers),
            'unique_planet_cards_used': self.unique_planet_cards_used.copy(),
            'negative_joker_indexes': self.negative_jokers.copy(),
            'negative_consumable_indexes': self.negative_consumables.copy(),
            'invisible_joker_rounds': self.invisible_joker_rounds.copy(),
            'madness_xmult': self.madness_xmult.copy(),
            'burglar_bonus_hands_this_round': self.burglar_bonus_hands_this_round,
            'certificate_card_created_this_blind': self.certificate_card_created_this_blind,
        }
    
    def get_card_state(self, card_index: int) -> CardState:
        """Get or create card state for a given card index."""
        if card_index not in self.card_states:
            self.card_states[card_index] = CardState(card_index)
        return self.card_states[card_index]
    
    def copy(self) -> 'UnifiedGameState':
        """Create a deep copy of the entire game state."""
        return UnifiedGameState(
            # Core state
            ante=self.ante,
            round=self.round,
            phase=self.phase,
            chips_needed=self.chips_needed,
            chips_scored=self.chips_scored,
            round_chips_scored=self.round_chips_scored,
            money=self.money,
            win_ante=self.win_ante,
            won=self.won,
            game_over=self.game_over,
            round_eval_cashout=self.round_eval_cashout,
            round_eval_completed_round=self.round_eval_completed_round,
            
            # Cards - need to copy the list but Card objects are immutable
            deck=self.deck.copy() if self.deck else [],
            draw_pile_indexes=self.draw_pile_indexes.copy(),
            discard_pile_indexes=self.discard_pile_indexes.copy(),
            play_area_indexes=self.play_area_indexes.copy(),
            hand_indexes=self.hand_indexes.copy(),
            selected_cards=self.selected_cards.copy(),
            hands_left=self.hands_left,
            discards_left=self.discards_left,
            hand_size=self.hand_size,
            money_per_hand=self.money_per_hand,
            money_per_discard=self.money_per_discard,
            no_extra_hand_money=self.no_extra_hand_money,
            no_interest=self.no_interest,
            
            # Collections - JokerInfo objects are immutable
            jokers=self.jokers.copy(),
            consumables=self.consumables.copy(),
            vouchers=self.vouchers.copy(),
            joker_slots=self.joker_slots,
            consumable_slots=self.consumable_slots,
            last_tarot_planet_consumable=self.last_tarot_planet_consumable,
            
            # Shop
            shop_inventory=self.shop_inventory.copy(),
            shop_reroll_cost=self.shop_reroll_cost,
            pending_pack_consumable=self.pending_pack_consumable,
            pending_pack_index=self.pending_pack_index,
            
            # Statistics
            hands_played_total=self.hands_played_total,
            hands_played_ante=self.hands_played_ante,
            last_hand_played=self.last_hand_played,
            last_held_card_indexes=self.last_held_card_indexes.copy() if self.last_held_card_indexes is not None else None,
            best_hand_this_ante=self.best_hand_this_ante,
            jokers_sold=self.jokers_sold,
            cards_discarded_total=self.cards_discarded_total,
            discards_used_this_round=self.discards_used_this_round,
            rerolls_used=self.rerolls_used,
            shop_visits=self.shop_visits,
            unique_planet_cards_used=self.unique_planet_cards_used.copy(),
            
            # Levels and states - need deep copies
            hand_levels=self.hand_levels.copy(),
            card_states={k: v.copy() for k, v in self.card_states.items()},
            
            # Boss blind
            active_boss_blind=self.active_boss_blind,
            pending_boss_blind=self.pending_boss_blind,
            boss_blind_active=self.boss_blind_active,
            boss_blind_rerolls_used_ante=self.boss_blind_rerolls_used_ante,
            bosses_used=self.bosses_used.copy(),
            face_down_cards=self.face_down_cards.copy(),
            force_draw_count=self.force_draw_count,
            disabled_joker_slots=self.disabled_joker_slots,
            boss_disabled_joker_indexes=self.boss_disabled_joker_indexes.copy(),
            hidden_joker_indexes=self.hidden_joker_indexes.copy(),
            boss_forced_selected_card=self.boss_forced_selected_card,
            boss_discard_random_count=self.boss_discard_random_count,
            boss_played_hand_types=self.boss_played_hand_types.copy(),
            boss_round_ox_target_hand=self.boss_round_ox_target_hand,
            
            # Special modes
            eternal_jokers=self.eternal_jokers.copy(),
            perishable_counters=self.perishable_counters.copy(),
            rental_jokers=self.rental_jokers.copy(),
            rocket_payouts=self.rocket_payouts.copy(),
            negative_jokers=self.negative_jokers.copy(),
            negative_consumables=self.negative_consumables.copy(),
            invisible_joker_rounds=self.invisible_joker_rounds.copy(),
            madness_xmult=self.madness_xmult.copy(),
            joker_sell_value_bonuses=self.joker_sell_value_bonuses.copy(),
            consumable_sell_value_bonuses=self.consumable_sell_value_bonuses.copy(),
            burglar_bonus_hands_this_round=self.burglar_bonus_hands_this_round,
            certificate_card_created_this_blind=self.certificate_card_created_this_blind,
            passive_hand_size_bonus_applied=self.passive_hand_size_bonus_applied,
            passive_hands_bonus_applied=self.passive_hands_bonus_applied,
            passive_discards_bonus_applied=self.passive_discards_bonus_applied,
        )
    
    def reset_round_state(self):
        """Reset state for a new round (but not a new ante)."""
        self.round_chips_scored = 0
        self.discards_used_this_round = 0
        self.draw_pile_indexes = list(range(len(self.deck)))
        self.discard_pile_indexes = []
        self.play_area_indexes = []
        self.hand_indexes = []
        self.last_hand_played = None
        self.last_held_card_indexes = None
        self.face_down_cards = []
        self.force_draw_count = None
        self.boss_disabled_joker_indexes = []
        self.hidden_joker_indexes = []
        self.boss_forced_selected_card = None
        self.boss_discard_random_count = 0
        self.boss_played_hand_types = []
        self.boss_round_ox_target_hand = None
        self.burglar_bonus_hands_this_round = 0
        self.certificate_card_created_this_blind = False
        
        # Reset per-round card tracking
        for card_state in self.card_states.values():
            card_state.is_face_down = False
            card_state.is_debuffed = False

        self.sync_passive_joker_effects()

        if self.phase == Phase.BLIND_SELECT:
            self._advance_invisible_joker_rounds()
        if self.phase == Phase.BLIND_SELECT:
            if self.round < 3:
                self._apply_madness_on_blind_selected()
            self._apply_burglar_on_blind_selected()
            self._apply_blind_setting_joker_creation_effects()
    
    def reset_ante_state(self):
        """Reset state for a new ante."""
        self.reset_round_state()
        self.hands_played_ante = 0
        self.best_hand_this_ante = 0
        self.boss_blind_active = False
        self.active_boss_blind = None
        self.pending_boss_blind = None
        self.boss_blind_rerolls_used_ante = 0
        self.disabled_joker_slots = 0
        self.boss_disabled_joker_indexes = []
        self.hidden_joker_indexes = []
        self.boss_forced_selected_card = None
        self.boss_discard_random_count = 0
        self.boss_played_hand_types = []
        self.boss_round_ox_target_hand = None
        
        for card_state in self.card_states.values():
            card_state.played_this_ante = False

        # Update perishable counters
        expired_jokers = []
        for joker_idx, rounds_left in self.perishable_counters.items():
            self.perishable_counters[joker_idx] = rounds_left - 1
            if self.perishable_counters[joker_idx] <= 0:
                expired_jokers.append(joker_idx)

        # Remove expired perishable jokers
        for joker_idx in sorted(expired_jokers, reverse=True):
            self.remove_joker(joker_idx)
    
    def add_joker(self, joker: JokerInfo, eternal: bool = False, 
                  perishable: bool = False, rental: bool = False) -> bool:
        """Add a joker with optional modifiers."""
        if len(self.jokers) >= self.joker_slots:
            return False
        
        self.jokers.append(joker)
        joker_idx = len(self.jokers) - 1
        
        if eternal:
            self.eternal_jokers.append(joker_idx)
        if perishable:
            self.perishable_counters[joker_idx] = 5  # 5 rounds before perishing
        if rental:
            self.rental_jokers.append(joker_idx)
        if joker.name == "Rocket":
            self.rocket_payouts[joker_idx] = 1
        if joker.name == "Invisible Joker":
            self.invisible_joker_rounds[joker_idx] = 0
        if joker.name == "Madness":
            self.madness_xmult[joker_idx] = 1.0
        self.sync_passive_joker_effects()
        
        return True

    def add_consumable(self, consumable: str, *, negative: bool = False) -> bool:
        """Add a consumable, letting Negative copies overflow normal capacity."""
        if not negative and self.active_consumable_count() >= self.consumable_slots:
            return False

        self.consumables.append(consumable)
        if negative:
            self.negative_consumables.append(len(self.consumables) - 1)
        return True

    def remove_consumable(self, consumable_idx: int) -> Optional[str]:
        """Remove a consumable while remapping Negative edition indexes."""
        if not (0 <= consumable_idx < len(self.consumables)):
            return None

        removed = self.consumables.pop(consumable_idx)
        self.negative_consumables = [
            idx - 1 if idx > consumable_idx else idx
            for idx in self.negative_consumables
            if idx != consumable_idx
        ]
        self.consumable_sell_value_bonuses = self._remap_consumable_index_dict_after_removal(
            self.consumable_sell_value_bonuses,
            consumable_idx,
            len(self.consumables) + 1,
        )
        return removed

    def active_consumable_count(self) -> int:
        """Return the number of non-Negative consumables that consume slots."""
        negative_indexes = {idx for idx in self.negative_consumables if 0 <= idx < len(self.consumables)}
        return sum(1 for idx in range(len(self.consumables)) if idx not in negative_indexes)

    def has_negative_consumable(self, consumable_idx: int) -> bool:
        return consumable_idx in self.negative_consumables

    def has_negative_joker(self, joker_idx: int) -> bool:
        return joker_idx in self.negative_jokers
    
    def remove_joker(self, joker_idx: int) -> Optional[JokerInfo]:
        """Remove a joker by index, handling all associated state."""
        if not (0 <= joker_idx < len(self.jokers)):
            return None
        
        # Check if joker is eternal
        if joker_idx in self.eternal_jokers:
            return None  # Can't remove eternal jokers
        
        removed = self.jokers.pop(joker_idx)
        
        # Clean up associated state
        if joker_idx in self.eternal_jokers:
            self.eternal_jokers.remove(joker_idx)
        if joker_idx in self.perishable_counters:
            del self.perishable_counters[joker_idx]
        if joker_idx in self.rental_jokers:
            self.rental_jokers.remove(joker_idx)
        if joker_idx in self.rocket_payouts:
            del self.rocket_payouts[joker_idx]
        if joker_idx in self.negative_jokers:
            self.negative_jokers.remove(joker_idx)
        if joker_idx in self.invisible_joker_rounds:
            del self.invisible_joker_rounds[joker_idx]
        if joker_idx in self.madness_xmult:
            del self.madness_xmult[joker_idx]
        
        # Adjust indices for remaining jokers
        self.eternal_jokers = [idx - 1 if idx > joker_idx else idx 
                               for idx in self.eternal_jokers]
        self.rental_jokers = [idx - 1 if idx > joker_idx else idx 
                             for idx in self.rental_jokers]
        self.negative_jokers = [idx - 1 if idx > joker_idx else idx
                                for idx in self.negative_jokers]
        self.boss_disabled_joker_indexes = [
            idx - 1 if idx > joker_idx else idx
            for idx in self.boss_disabled_joker_indexes
            if idx != joker_idx
        ]
        self.hidden_joker_indexes = [
            idx - 1 if idx > joker_idx else idx
            for idx in self.hidden_joker_indexes
            if idx != joker_idx
        ]
        
        # Adjust perishable counters
        new_perishable = {}
        for idx, count in self.perishable_counters.items():
            new_idx = idx - 1 if idx > joker_idx else idx
            if new_idx >= 0:
                new_perishable[new_idx] = count
        self.perishable_counters = new_perishable

        new_rocket_payouts = {}
        for idx, payout in self.rocket_payouts.items():
            new_idx = idx - 1 if idx > joker_idx else idx
            if new_idx >= 0:
                new_rocket_payouts[new_idx] = payout
        self.rocket_payouts = new_rocket_payouts
        self.invisible_joker_rounds = self._remap_joker_index_dict(self.invisible_joker_rounds, {
            old_idx: (old_idx - 1 if old_idx > joker_idx else old_idx)
            for old_idx in range(len(self.jokers) + 1)
            if old_idx != joker_idx
        })
        self.madness_xmult = self._remap_joker_index_dict(self.madness_xmult, {
            old_idx: (old_idx - 1 if old_idx > joker_idx else old_idx)
            for old_idx in range(len(self.jokers) + 1)
            if old_idx != joker_idx
        })
        self.joker_sell_value_bonuses = self._remap_joker_index_dict(self.joker_sell_value_bonuses, {
            old_idx: (old_idx - 1 if old_idx > joker_idx else old_idx)
            for old_idx in range(len(self.jokers) + 1)
            if old_idx != joker_idx
        })
        self.sync_passive_joker_effects()
        
        return removed

    def is_joker_debuffed(self, joker_idx: int) -> bool:
        return joker_idx in self.boss_disabled_joker_indexes

    def get_credit_card_count(self) -> int:
        return sum(
            1
            for joker_idx, joker in enumerate(self.jokers)
            if joker.name == "Credit Card" and not self.is_joker_debuffed(joker_idx)
        )

    def get_debt_floor(self) -> int:
        return -20 * self.get_credit_card_count()

    def available_shop_money(self) -> int:
        return self.money - self.get_debt_floor()

    def can_afford_shop_cost(self, cost: int) -> bool:
        return int(cost) <= self.available_shop_money()

    def get_joker_sell_value(self, joker_idx: int) -> int:
        if not (0 <= joker_idx < len(self.jokers)):
            return 0

        joker = self.jokers[joker_idx]
        base_value = max(3, joker.base_cost // 2)
        if joker.name == "Egg":
            base_value = 5
        elif joker.name == "Gift Card":
            base_value = 0
        return base_value + int(self.joker_sell_value_bonuses.get(joker_idx, 0) or 0)

    def get_consumable_sell_value(self, consumable_idx: int) -> int:
        if not (0 <= consumable_idx < len(self.consumables)):
            return 0

        consumable_name = self.consumables[consumable_idx]
        spectral_names = {
            'Familiar', 'Grim', 'Incantation', 'Talisman', 'Aura', 'Wraith',
            'Sigil', 'Ouija', 'Ectoplasm', 'Immolate', 'Ankh', 'Deja Vu',
            'Hex', 'Trance', 'Medium', 'Cryptid', 'The Soul', 'Black Hole',
        }
        base_value = 2 if consumable_name in spectral_names else 1
        return base_value + int(self.consumable_sell_value_bonuses.get(consumable_idx, 0) or 0)

    def add_joker_sell_value_bonus(self, joker_idx: int, amount: int) -> None:
        if not (0 <= joker_idx < len(self.jokers)):
            return
        self.joker_sell_value_bonuses[joker_idx] = int(self.joker_sell_value_bonuses.get(joker_idx, 0) or 0) + int(amount)

    def add_consumable_sell_value_bonus(self, consumable_idx: int, amount: int) -> None:
        if not (0 <= consumable_idx < len(self.consumables)):
            return
        self.consumable_sell_value_bonuses[consumable_idx] = (
            int(self.consumable_sell_value_bonuses.get(consumable_idx, 0) or 0) + int(amount)
        )

    def add_sell_value_bonus_to_all_owned(self, amount: int) -> None:
        for joker_idx in range(len(self.jokers)):
            self.add_joker_sell_value_bonus(joker_idx, amount)
        for consumable_idx in range(len(self.consumables)):
            self.add_consumable_sell_value_bonus(consumable_idx, amount)

    def record_planet_card_used(self, planet_name: str) -> None:
        """Track unique Planet consumables used across the run."""
        if planet_name not in self.unique_planet_cards_used:
            self.unique_planet_cards_used.append(planet_name)

    def get_rocket_payout(self, joker_idx: int) -> int:
        """Return the current Rocket payout for a joker slot."""
        return int(self.rocket_payouts.get(joker_idx, 1))

    def increase_rocket_payouts(self, increase: int = 2) -> None:
        """Increase all Rocket jokers' future payout after a boss defeat."""
        for joker_idx, joker in enumerate(self.jokers):
            if joker.name == "Rocket":
                self.rocket_payouts[joker_idx] = self.get_rocket_payout(joker_idx) + increase

    def reorder_jokers(self, order: List[int]) -> None:
        """Reorder jokers and remap all joker-indexed side tables to match."""
        if sorted(order) != list(range(len(self.jokers))):
            return

        self.jokers = [self.jokers[i] for i in order]
        old_to_new = {old_index: new_index for new_index, old_index in enumerate(order)}

        self.eternal_jokers = self._remap_joker_index_list(self.eternal_jokers, old_to_new)
        self.rental_jokers = self._remap_joker_index_list(self.rental_jokers, old_to_new)
        self.boss_disabled_joker_indexes = self._remap_joker_index_list(
            self.boss_disabled_joker_indexes,
            old_to_new,
        )
        self.hidden_joker_indexes = self._remap_joker_index_list(self.hidden_joker_indexes, old_to_new)
        self.perishable_counters = self._remap_joker_index_dict(self.perishable_counters, old_to_new)
        self.rocket_payouts = self._remap_joker_index_dict(self.rocket_payouts, old_to_new)
        self.negative_jokers = self._remap_joker_index_list(self.negative_jokers, old_to_new)
        self.invisible_joker_rounds = self._remap_joker_index_dict(self.invisible_joker_rounds, old_to_new)
        self.madness_xmult = self._remap_joker_index_dict(self.madness_xmult, old_to_new)
        self.joker_sell_value_bonuses = self._remap_joker_index_dict(self.joker_sell_value_bonuses, old_to_new)
    
    def get_active_joker_count(self) -> int:
        """Get number of active (non-disabled) joker slots."""
        disabled_count = max(self.disabled_joker_slots, len(self.boss_disabled_joker_indexes))
        return max(0, len(self.jokers) - disabled_count)
    
    def get_hand_cards(self) -> List[Card]:
        """Get the actual Card objects currently in hand."""
        cards = []
        for idx in self.hand_indexes:
            if 0 <= idx < len(self.deck):
                cards.append(self.deck[idx])
        return cards
    
    def get_selected_cards(self) -> List[Card]:
        """Get the actual Card objects currently selected."""
        cards = []
        for hand_idx in self.selected_cards:
            if 0 <= hand_idx < len(self.hand_indexes):
                deck_idx = self.hand_indexes[hand_idx]
                if 0 <= deck_idx < len(self.deck):
                    cards.append(self.deck[deck_idx])
        return cards

    def copy_joker_modifiers(self, source_idx: int, dest_idx: int, *, copy_negative: bool = True) -> None:
        """Copy persistent joker stickers/state from one slot to another."""
        if source_idx in self.eternal_jokers:
            self.eternal_jokers.append(dest_idx)
        if source_idx in self.rental_jokers:
            self.rental_jokers.append(dest_idx)
        if source_idx in self.negative_jokers and copy_negative:
            self.negative_jokers.append(dest_idx)
        if source_idx in self.perishable_counters:
            self.perishable_counters[dest_idx] = int(self.perishable_counters[source_idx])
        if source_idx in self.rocket_payouts:
            self.rocket_payouts[dest_idx] = int(self.rocket_payouts[source_idx])
        if source_idx in self.invisible_joker_rounds:
            self.invisible_joker_rounds[dest_idx] = int(self.invisible_joker_rounds[source_idx])
        if source_idx in self.madness_xmult:
            self.madness_xmult[dest_idx] = float(self.madness_xmult[source_idx])

    def sync_passive_joker_effects(self) -> None:
        """Apply or remove passive joker stat bonuses based on active debuff state."""
        hand_size_bonus, hands_bonus, discards_bonus = self._passive_joker_bonuses()

        hand_size_delta = hand_size_bonus - self.passive_hand_size_bonus_applied
        hands_delta = hands_bonus - self.passive_hands_bonus_applied
        discards_delta = discards_bonus - self.passive_discards_bonus_applied

        if hand_size_delta:
            self.hand_size = max(1, int(self.hand_size) + hand_size_delta)
        if hands_delta:
            self.hands_left = max(0, int(self.hands_left) + hands_delta)
        if discards_delta:
            self.discards_left = max(0, int(self.discards_left) + discards_delta)

        self.passive_hand_size_bonus_applied = hand_size_bonus
        self.passive_hands_bonus_applied = hands_bonus
        self.passive_discards_bonus_applied = discards_bonus

    def _passive_joker_bonuses(self) -> tuple[int, int, int]:
        hand_size_bonus = 0
        hands_bonus = 0
        discards_bonus = 0

        disabled_indexes = set(self.boss_disabled_joker_indexes)
        for joker_idx, joker in enumerate(self.jokers):
            if joker_idx in disabled_indexes:
                continue
            if joker.name == "Juggler":
                hand_size_bonus += 1
            elif joker.name == "Troubadour":
                hand_size_bonus += 2
                hands_bonus -= 1
            elif joker.name == "Drunkard":
                discards_bonus += 1
            elif joker.name == "Merry Andy":
                hands_bonus -= 1
                discards_bonus += 3

        return hand_size_bonus, hands_bonus, discards_bonus

    def _apply_blind_setting_joker_creation_effects(self) -> None:
        common_jokers = [
            joker for joker in JOKER_LIBRARY
            if joker.base_cost > 0 and JOKER_RARITY_BY_ID.get(joker.id) == 1
        ]
        tarot_cards = [
            'The Fool', 'The Magician', 'The High Priestess', 'The Empress',
            'The Emperor', 'The Hierophant', 'The Lovers', 'The Chariot',
            'Strength', 'The Hermit', 'Wheel of Fortune', 'Justice',
            'The Hanged Man', 'Death', 'Temperance', 'The Devil',
            'The Tower', 'The Star', 'The Moon', 'The Sun',
            'Judgement', 'The World'
        ]

        for joker_idx, joker in enumerate(list(self.jokers)):
            if joker_idx in self.boss_disabled_joker_indexes:
                continue

            if joker.name == "Riff-Raff":
                for _ in range(2):
                    if len(self.jokers) >= self.joker_slots or not common_jokers:
                        break
                    self.add_joker(random.choice(common_jokers))
            elif joker.name == "Marble Joker":
                card_idx = len(self.deck)
                self.deck.append(
                    Card(
                        rank=random.choice(list(Rank)),
                        suit=random.choice(list(Suit)),
                    )
                )
                self.draw_pile_indexes.append(card_idx)
                self.get_card_state(card_idx).enhancement = Enhancement.STONE
            elif joker.name == "Cartomancer":
                if self.active_consumable_count() < self.consumable_slots:
                    self.add_consumable(random.choice(tarot_cards))

    def _apply_burglar_on_blind_selected(self) -> None:
        burglar_count = sum(1 for joker in self.jokers if joker.name == "Burglar")
        if burglar_count <= 0:
            return

        hands_added = 3 * burglar_count
        self.burglar_bonus_hands_this_round = hands_added
        self.hands_left += hands_added
        self.discards_left = 0

    def _advance_invisible_joker_rounds(self) -> None:
        for joker_idx, joker in enumerate(self.jokers):
            if joker.name == "Invisible Joker":
                self.invisible_joker_rounds[joker_idx] = int(self.invisible_joker_rounds.get(joker_idx, 0)) + 1

    def _apply_madness_on_blind_selected(self) -> None:
        joker_index = 0
        while joker_index < len(self.jokers):
            joker = self.jokers[joker_index]
            if joker.name != "Madness":
                joker_index += 1
                continue

            self.madness_xmult[joker_index] = round(self.madness_xmult.get(joker_index, 1.0) + 0.5, 10)
            candidate_indexes = [
                idx for idx, other in enumerate(self.jokers)
                if idx != joker_index and idx not in self.eternal_jokers
            ]
            if candidate_indexes:
                self.remove_joker(candidate_indexes[0])
                if candidate_indexes[0] < joker_index:
                    joker_index -= 1
            joker_index += 1

    @staticmethod
    def _remap_joker_index_list(indexes: List[int], old_to_new: Dict[int, int]) -> List[int]:
        remapped = []
        for raw_index in indexes:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index in old_to_new:
                remapped.append(old_to_new[index])
        return sorted(remapped)

    @staticmethod
    def _remap_joker_index_dict(values: Dict[int, Any], old_to_new: Dict[int, int]) -> Dict[int, Any]:
        remapped: Dict[int, Any] = {}
        for raw_index, value in values.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index in old_to_new:
                remapped[old_to_new[index]] = value
        return remapped

    @staticmethod
    def _remap_consumable_index_dict_after_removal(
        values: Dict[int, Any],
        removed_idx: int,
        previous_count: int,
    ) -> Dict[int, Any]:
        old_to_new = {
            old_idx: (old_idx - 1 if old_idx > removed_idx else old_idx)
            for old_idx in range(previous_count)
            if old_idx != removed_idx
        }
        remapped: Dict[int, Any] = {}
        for raw_index, value in values.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index in old_to_new:
                remapped[old_to_new[index]] = value
        return remapped

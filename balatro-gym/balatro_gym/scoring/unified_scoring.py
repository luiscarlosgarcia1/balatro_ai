"""balatro_gym/unified_scoring.py - Unified scoring system that properly integrates joker effects

This fixes the mismatch between CompleteJokerEffects and ScoreEngine by:
1. Tracking chips and mult separately throughout the calculation
2. Applying effects in the correct order (base -> additions -> multipliers)
3. Using a consistent effect format across all systems
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

from balatro_gym.core.cards import (
    Edition,
    EditionEffects,
    Enhancement,
    EnhancementEffects,
    Seal,
)
from balatro_gym.scoring.scoring_engine import ScoreEngine, HandType
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects

# ---------------------------------------------------------------------------
# Unified Effect Format
# ---------------------------------------------------------------------------

@dataclass
class ScoringEffect:
    """Unified format for all scoring effects"""
    chips_add: int = 0          # Add to chips (before mult)
    mult_add: int = 0           # Add to mult (before multiplication)
    chips_mult: float = 1.0     # Multiply chips
    mult_mult: float = 1.0      # Multiply mult
    x_mult: float = 1.0         # Final score multiplier
    money: int = 0              # Money gained
    retriggers: int = 0         # Card retriggers
    message: str = ""           # Debug message

    def combine(self, other: 'ScoringEffect') -> 'ScoringEffect':
        """Combine two effects"""
        return ScoringEffect(
            chips_add=self.chips_add + other.chips_add,
            mult_add=self.mult_add + other.mult_add,
            chips_mult=self.chips_mult * other.chips_mult,
            mult_mult=self.mult_mult * other.mult_mult,
            x_mult=self.x_mult * other.x_mult,
            money=self.money + other.money,
            retriggers=self.retriggers + other.retriggers,
            message=f"{self.message}; {other.message}" if self.message and other.message else self.message or other.message
        )

# ---------------------------------------------------------------------------
# Effect Converter
# ---------------------------------------------------------------------------

class EffectConverter:
    """Converts CompleteJokerEffects output to unified format"""
    
    @staticmethod
    def convert_joker_effect(effect_dict: Optional[Dict]) -> ScoringEffect:
        """Convert joker effect dictionary to ScoringEffect"""
        if not effect_dict:
            return ScoringEffect()
        
        # Handle different effect formats from CompleteJokerEffects
        
        # Basic format: {'chips': 50, 'mult': 4, 'x_mult': 2.0}
        if isinstance(effect_dict, dict):
            return ScoringEffect(
                chips_add=effect_dict.get('chips', 0),
                mult_add=effect_dict.get('mult', 0),
                x_mult=effect_dict.get('x_mult', 1.0),
                money=effect_dict.get('money', 0),
                retriggers=effect_dict.get('retriggers', 0),
                message=effect_dict.get('message', '')
            )
        
        # Handle numeric returns (some jokers return just a multiplier)
        elif isinstance(effect_dict, (int, float)):
            # Assume it's a mult addition
            return ScoringEffect(mult_add=int(effect_dict))
        
        return ScoringEffect()

# ---------------------------------------------------------------------------
# Unified Scoring Context
# ---------------------------------------------------------------------------

@dataclass
class ScoringContext:
    """Complete context for scoring a hand"""
    cards: List[Any]              # Card objects
    scoring_cards: List[Any]      # Cards that count for the hand
    hand_type: HandType           # Poker hand type
    hand_type_name: str          # Human-readable name
    game_state: Dict             # Full game state
    
    # Scoring components
    base_chips: int = 0
    base_mult: int = 0
    card_chips: int = 0          # Chips from card values
    blind_modifier: Any = None   # Callable for boss blind base hand modification
    
    # Phases for effects
    phase: str = 'scoring'       # Current phase


LUA_SCORING_STAGES: Tuple[str, ...] = (
    "base_hand",
    "before_scoring_jokers",
    "blind_modification",
    "scoring_card_effects",
    "repetitions",
    "held_card_effects",
    "joker_edition_chip_mult_effects",
    "joker_main_effects",
    "joker_on_joker_effects",
    "joker_edition_x_mult_effects",
    "final_scoring_step",
    "destruction_hooks",
    "after_hand_effects",
)

# ---------------------------------------------------------------------------
# Unified Scorer
# ---------------------------------------------------------------------------

class UnifiedScorer:
    """Unified scoring system that properly integrates all effects"""
    
    def __init__(self, score_engine: ScoreEngine, joker_effects: CompleteJokerEffects):
        self.engine = score_engine
        self.joker_effects = joker_effects
        self.effect_converter = EffectConverter()

    @staticmethod
    def _joker_name(joker_entry: Any) -> Optional[str]:
        """Return the joker name from supported state/scoring representations."""
        if isinstance(joker_entry, str):
            return joker_entry
        if isinstance(joker_entry, dict):
            name = joker_entry.get('name')
            return name if isinstance(name, str) else None
        name = getattr(joker_entry, 'name', None)
        return name if isinstance(name, str) else None

    def _iter_joker_names(self, game_state: Dict[str, Any]):
        for joker_entry in game_state.get('jokers', []):
            joker_name = self._joker_name(joker_entry)
            if joker_name:
                yield joker_name

    def _iter_jokers(self, game_state: Dict[str, Any]):
        for joker_index, joker_entry in enumerate(game_state.get('jokers', [])):
            joker_name = self._joker_name(joker_entry)
            if joker_name:
                yield joker_index, joker_name

    @staticmethod
    def _enum_value(value: Any, enum_type: type[IntEnum], aliases: Dict[str, str]) -> IntEnum:
        if isinstance(value, enum_type):
            return value
        if isinstance(value, IntEnum):
            key = aliases.get(value.name, value.name)
            return enum_type.__members__.get(key, enum_type.NONE)
        if isinstance(value, str):
            key = value.strip().replace(" ", "_").replace("-", "_").upper()
            key = aliases.get(key, key)
            return enum_type.__members__.get(key, enum_type.NONE)
        return enum_type.NONE

    @classmethod
    def _card_enhancement(cls, card: Any) -> Enhancement:
        return cls._enum_value(getattr(card, "enhancement", Enhancement.NONE), Enhancement, {})

    @classmethod
    def _card_edition(cls, card: Any) -> Edition:
        return cls._enum_value(
            getattr(card, "edition", Edition.NONE),
            Edition,
            {"HOLO": "HOLOGRAPHIC"},
        )

    @classmethod
    def _card_seal(cls, card: Any) -> Seal:
        return cls._enum_value(getattr(card, "seal", Seal.NONE), Seal, {})

    @staticmethod
    def _base_card_chips(card: Any, enhancement: Enhancement) -> int:
        if enhancement == Enhancement.STONE:
            return 0
        if hasattr(card, 'base_value'):
            return int(card.base_value)
        if hasattr(card, 'chip_value') and not hasattr(card, 'enhancement'):
            return int(card.chip_value())

        rank = getattr(card, 'rank', 0)
        if isinstance(rank, IntEnum):
            rank = rank.value
        return 11 if rank == 14 else min(int(rank or 0), 10)

    def _score_card_once(self, card: Any) -> Tuple[int, int, float]:
        if self._is_card_debuffed(card):
            return 0, 0, 1.0

        enhancement = self._card_enhancement(card)
        edition = self._card_edition(card)
        base_card_chips = self._base_card_chips(card, enhancement)
        chips = (
            base_card_chips
            + EnhancementEffects.get_chip_bonus(enhancement, base_card_chips)
            + EditionEffects.get_chip_bonus(edition)
        )
        mult = (
            EnhancementEffects.get_mult_bonus(enhancement)
            + EditionEffects.get_mult_bonus(edition)
        )
        x_mult = (
            EnhancementEffects.get_mult_multiplier(enhancement, in_hand=False)
            * EditionEffects.get_mult_multiplier(edition)
        )
        return chips, mult, x_mult

    def _score_card_with_side_effects(
        self,
        card: Any,
        breakdown: Dict[str, Any],
    ) -> Tuple[int, int, float]:
        chips, mult, x_mult = self._score_card_once(card)
        if self._is_card_debuffed(card):
            breakdown['effects_applied'].append("Debuffed card: no card or individual joker effects")
            return chips, mult, x_mult

        card_state = getattr(card, "card_state", None)
        card_idx = getattr(card_state, "card_index", None)
        if card_state is not None:
            card_state.times_scored += 1

            if self._card_enhancement(card) == Enhancement.LUCKY:
                mult_roll = self._rng_float("card_enhancement")
                money_roll = self._rng_float("card_enhancement")
                lucky_mult, lucky_money = EnhancementEffects.get_lucky_bonus(mult_roll, money_roll)
                mult += lucky_mult
                breakdown["money_gained"] += lucky_money
                if lucky_mult or lucky_money:
                    breakdown['effects_applied'].append(
                        f"Lucky card: +{lucky_mult}m +${lucky_money}"
                    )

            if self._card_seal(card) == Seal.GOLD:
                breakdown["money_gained"] += 3

            if (
                card_idx is not None
                and self._card_enhancement(card) == Enhancement.GLASS
                and self._rng_float("card_enhancement") < 0.25
            ):
                breakdown["cards_to_destroy"].append(card_idx)

        return chips, mult, x_mult

    def _rng_float(self, stream: str) -> float:
        rng = getattr(self.joker_effects, "rng", None)
        if rng is not None and hasattr(rng, "get_float"):
            return rng.get_float(stream)
        fallback = getattr(self.joker_effects, "_fallback_rng", None)
        if fallback is not None:
            return fallback.random()
        return 1.0

    @staticmethod
    def _is_card_debuffed(card: Any) -> bool:
        card_state = getattr(card, "card_state", None)
        return bool(
            getattr(card, "is_debuffed", False)
            or getattr(card_state, "is_debuffed", False)
        )

    def _apply_individual_jokers(
        self,
        card: Any,
        context: ScoringContext,
        collect_retriggers: bool,
        breakdown: Dict[str, Any],
    ) -> ScoringEffect:
        card_context = {
            'phase': 'individual_scoring',
            'card': card,
            'cards': context.cards,
            'scoring_cards': context.scoring_cards,
            'hand_type': context.hand_type_name
        }
        combined = ScoringEffect()

        for joker_index, joker_name in self._iter_jokers(context.game_state):
            joker = type('Joker', (), {'name': joker_name})
            card_context['joker_index'] = joker_index
            raw_effect = self.joker_effects.apply_joker_effect(joker, card_context, context.game_state)
            effect = self.effect_converter.convert_joker_effect(raw_effect)
            if not collect_retriggers:
                effect.retriggers = 0
            combined = combined.combine(effect)
            self._record_raw_side_effects(raw_effect, breakdown)

            if effect.chips_add or effect.mult_add or effect.x_mult != 1.0:
                card_str = f"{getattr(card, 'rank', '?')} of {getattr(card, 'suit', '?')}"
                breakdown['effects_applied'].append(
                    f"{joker_name} on {card_str}: +{effect.chips_add}c +{effect.mult_add}m x{effect.x_mult}"
                )

        return combined

    @staticmethod
    def _record_raw_side_effects(raw_effect: Optional[Dict], breakdown: Dict[str, Any]) -> None:
        if not isinstance(raw_effect, dict):
            return
        created_consumable = raw_effect.get('created_consumable')
        if created_consumable:
            breakdown.setdefault('consumables_created', []).append(created_consumable)

    def _base_hand_values(self, context: ScoringContext) -> Tuple[int, int]:
        base_chips = context.base_chips
        base_mult = context.base_mult
        if not base_chips or not base_mult:
            base_chips, base_mult = self.engine.get_hand_chips_mult(context.hand_type)
        return base_chips, base_mult

    def _blind_modified_base_values(
        self,
        context: ScoringContext,
        base_chips: int,
        base_mult: int,
    ) -> Tuple[int, int]:
        if context.blind_modifier is not None:
            return context.blind_modifier(
                base_chips,
                base_mult,
                context.cards,
                context.hand_type_name,
            )

        if context.game_state.get("active_boss_blind") == "THE_FLINT":
            return int(base_chips * 0.5 + 0.5), max(1, int(base_mult * 0.5 + 0.5))

        return base_chips, base_mult

    def _apply_joker_phase(
        self,
        phase: str,
        context: ScoringContext,
        breakdown: Dict[str, Any],
        *,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> ScoringEffect:
        phase_context = {
            'phase': phase,
            'cards': context.cards,
            'scoring_cards': context.scoring_cards,
            'hand_type': context.hand_type_name,
        }
        if extra_context:
            phase_context.update(extra_context)

        combined = ScoringEffect()
        for joker_index, joker_name in self._iter_jokers(context.game_state):
            joker = type('Joker', (), {'name': joker_name})
            phase_context['joker_index'] = joker_index
            raw_effect = self.joker_effects.apply_joker_effect(joker, phase_context, context.game_state)
            effect = self.effect_converter.convert_joker_effect(raw_effect)
            self._record_raw_side_effects(raw_effect, breakdown)
            combined = combined.combine(effect)

            if effect.chips_add or effect.mult_add or effect.x_mult != 1.0:
                label = self._stage_label(phase)
                breakdown['effects_applied'].append(
                    f"{joker_name} ({label}): +{effect.chips_add}c +{effect.mult_add}m x{effect.x_mult}"
                )

        return combined

    @staticmethod
    def _stage_label(phase: str) -> str:
        return phase.replace("_", " ")

    @staticmethod
    def _apply_effect_to_totals(
        chips: int,
        mult: int,
        x_mult: float,
        effect: ScoringEffect,
    ) -> Tuple[int, int, float]:
        chips += effect.chips_add
        mult += effect.mult_add
        chips = int(chips * effect.chips_mult)
        mult = int(mult * effect.mult_mult)
        x_mult *= effect.x_mult
        return chips, mult, x_mult

    def _apply_held_card_base_effects(
        self,
        context: ScoringContext,
        breakdown: Dict[str, Any],
    ) -> ScoringEffect:
        """Apply non-joker effects from cards remaining in hand."""
        held_effect = ScoringEffect()
        for held_card in context.game_state.get("held_cards", []):
            if self._is_card_debuffed(held_card):
                continue

            enhancement = self._card_enhancement(held_card)
            x_mult = EnhancementEffects.get_mult_multiplier(enhancement, in_hand=True)
            if x_mult != 1.0:
                held_effect = held_effect.combine(
                    ScoringEffect(x_mult=x_mult, message="Held card")
                )
                breakdown["effects_applied"].append(
                    f"Held card ({enhancement.name.title()}): x{x_mult}"
                )

        return held_effect
    
    def score_hand(self, context: ScoringContext) -> Tuple[int, Dict[str, Any]]:
        """
        Score a hand with all effects properly applied
        
        Returns:
            (final_score, scoring_breakdown)
        """
        self.joker_effects.reset_scoring_hand_state(context.game_state)

        base_chips, base_mult = self._base_hand_values(context)
        chips = base_chips
        mult = base_mult
        x_mult = 1.0

        breakdown = {
            'base_chips': base_chips,
            'base_mult': base_mult,
            'card_chips': 0,
            'joker_chips': 0,
            'joker_mult': 0,
            'joker_x_mult': 1.0,
            'consumables_created': [],
            'cards_to_destroy': [],
            'money_gained': 0,
            'effects_applied': [],
            'stage_order': list(LUA_SCORING_STAGES),
        }

        before_effect = self._apply_joker_phase("before_scoring", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, before_effect)

        modified_base_chips, modified_base_mult = self._blind_modified_base_values(
            context,
            base_chips,
            base_mult,
        )
        chips += modified_base_chips - base_chips
        mult += modified_base_mult - base_mult

        card_chip_total = 0
        card_enhancement_mult = 0
        card_enhancement_x_mult = 1.0
        card_retriggers = 0

        individual_chips = 0
        individual_mult = 0
        individual_x_mult = 1.0

        for card in context.scoring_cards:
            if self._is_card_debuffed(card):
                breakdown['effects_applied'].append("Debuffed card: no card or individual joker effects")
                continue

            chips_once, mult_once, x_mult_once = self._score_card_with_side_effects(card, breakdown)
            card_chip_total += chips_once
            card_enhancement_mult += mult_once
            card_enhancement_x_mult *= x_mult_once
            chips += chips_once
            mult += mult_once
            x_mult *= x_mult_once

            effect = self._apply_individual_jokers(card, context, True, breakdown)
            individual_chips += effect.chips_add
            individual_mult += effect.mult_add
            individual_x_mult *= effect.x_mult
            breakdown["money_gained"] += effect.money

            retriggers = int(self._card_seal(card) == Seal.RED) + effect.retriggers
            card_retriggers += retriggers
            for _ in range(retriggers):
                chips_once, mult_once, x_mult_once = self._score_card_with_side_effects(card, breakdown)
                card_chip_total += chips_once
                card_enhancement_mult += mult_once
                card_enhancement_x_mult *= x_mult_once
                chips += chips_once
                mult += mult_once
                x_mult *= x_mult_once

                repeat_effect = self._apply_individual_jokers(card, context, False, breakdown)
                individual_chips += repeat_effect.chips_add
                individual_mult += repeat_effect.mult_add
                individual_x_mult *= repeat_effect.x_mult
                breakdown["money_gained"] += repeat_effect.money

        chips += individual_chips
        mult += individual_mult
        x_mult *= individual_x_mult

        breakdown['joker_chips'] += individual_chips
        breakdown['joker_mult'] += individual_mult
        breakdown['joker_x_mult'] *= individual_x_mult

        held_card_effect = self._apply_held_card_base_effects(context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, held_card_effect)

        held_effect = self._apply_joker_phase("held_card", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, held_effect)

        edition_chip_mult_effect = self._apply_joker_phase("joker_edition_chip_mult", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, edition_chip_mult_effect)

        main_effect = self._apply_joker_phase("scoring", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, main_effect)

        joker_on_joker_effect = self._apply_joker_phase("joker_on_joker", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, joker_on_joker_effect)

        edition_x_mult_effect = self._apply_joker_phase("joker_edition_x_mult", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, edition_x_mult_effect)

        final_step_effect = self._apply_joker_phase("final_scoring_step", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, final_step_effect)

        destruction_effect = self._apply_joker_phase("destroying_card", context, breakdown)
        chips, mult, x_mult = self._apply_effect_to_totals(chips, mult, x_mult, destruction_effect)

        after_hand_effect = self._apply_joker_phase("after_hand", context, breakdown)

        phase_effects = (
            before_effect,
            held_effect,
            edition_chip_mult_effect,
            main_effect,
            joker_on_joker_effect,
            edition_x_mult_effect,
            final_step_effect,
            destruction_effect,
            after_hand_effect,
        )
        for effect in phase_effects:
            breakdown["money_gained"] += effect.money
            breakdown['joker_chips'] += effect.chips_add
            breakdown['joker_mult'] += effect.mult_add
            breakdown['joker_x_mult'] *= effect.x_mult

        final_score = int(chips * mult * x_mult)

        money_gained = int(breakdown["money_gained"])
        if money_gained > 0:
            context.game_state['money'] = context.game_state.get('money', 0) + money_gained

        breakdown['final_chips'] = chips
        breakdown['final_mult'] = mult
        breakdown['final_x_mult'] = x_mult
        breakdown['blind_modified_base_chips'] = modified_base_chips
        breakdown['blind_modified_base_mult'] = modified_base_mult
        breakdown['final_score'] = final_score
        breakdown['money_gained'] = money_gained
        breakdown['card_chips'] = card_chip_total
        breakdown['card_mult'] = card_enhancement_mult
        breakdown['card_x_mult'] = card_enhancement_x_mult
        breakdown['card_retriggers'] = card_retriggers
        
        return final_score, breakdown

# ---------------------------------------------------------------------------
# Integration Helper
# ---------------------------------------------------------------------------

def create_unified_scorer(engine: ScoreEngine, joker_effects: CompleteJokerEffects) -> UnifiedScorer:
    """Create a unified scorer instance"""
    return UnifiedScorer(engine, joker_effects)

# ---------------------------------------------------------------------------
# Usage Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create components
    engine = ScoreEngine()
    joker_effects = CompleteJokerEffects()
    scorer = UnifiedScorer(engine, joker_effects)
    
    # Example hand
    cards = [
        type('Card', (), {'rank': 14, 'suit': 'Hearts', 'base_value': 11, 'enhancement': None}),
        type('Card', (), {'rank': 14, 'suit': 'Spades', 'base_value': 11, 'enhancement': 'mult'}),
        type('Card', (), {'rank': 2, 'suit': 'Hearts', 'base_value': 2, 'enhancement': None}),
        type('Card', (), {'rank': 3, 'suit': 'Clubs', 'base_value': 3, 'enhancement': None}),
        type('Card', (), {'rank': 5, 'suit': 'Diamonds', 'base_value': 5, 'enhancement': None}),
    ]
    
    # Create context
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards[:2],  # Just the pair of aces
        hand_type=HandType.ONE_PAIR,
        hand_type_name='Pair',
        game_state={
            'jokers': ['Joker', 'Greedy Joker', 'Fibonacci'],
            'money': 10
        }
    )
    
    # Score the hand
    score, breakdown = scorer.score_hand(context)
    
    print(f"Final Score: {score}")
    print("\nBreakdown:")
    for key, value in breakdown.items():
        if key != 'effects_applied':
            print(f"  {key}: {value}")
    
    print("\nEffects Applied:")
    for effect in breakdown['effects_applied']:
        print(f"  - {effect}")

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


@dataclass
class ScoringTotals:
    """Mutable running score totals following Lua event order."""

    chips: int
    mult: float
    score_mult: float
    x_mult: float = 1.0
    deferred_x_mult: float = 1.0


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
        base_card_chips = self._base_card_chips(card, enhancement)
        chips = (
            base_card_chips
            + EnhancementEffects.get_chip_bonus(enhancement, base_card_chips)
        )
        mult = EnhancementEffects.get_mult_bonus(enhancement)
        x_mult = EnhancementEffects.get_mult_multiplier(enhancement, in_hand=False)
        return chips, mult, x_mult

    def _card_edition_effect(self, card: Any) -> ScoringEffect:
        if self._is_card_debuffed(card):
            return ScoringEffect()

        edition = self._card_edition(card)
        return ScoringEffect(
            chips_add=EditionEffects.get_chip_bonus(edition),
            mult_add=EditionEffects.get_mult_bonus(edition),
            x_mult=EditionEffects.get_mult_multiplier(edition),
        )

    def _score_card_with_side_effects(
        self,
        card: Any,
        breakdown: Dict[str, Any],
    ) -> ScoringEffect:
        chips, mult, x_mult = self._score_card_once(card)
        if self._is_card_debuffed(card):
            breakdown['effects_applied'].append("Debuffed card: no card or individual joker effects")
            return ScoringEffect()

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
                breakdown.setdefault("_glass_cards_to_destroy", []).append(card_idx)

        return ScoringEffect(chips_add=chips, mult_add=mult, x_mult=x_mult)

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

    @staticmethod
    def _card_label(card: Any) -> str:
        rank = getattr(card, "rank", "?")
        suit = getattr(card, "suit", "?")
        rank_name = getattr(rank, "name", rank)
        suit_name = getattr(suit, "name", suit)
        return f"{rank_name} of {suit_name}"

    @staticmethod
    def _card_index(card: Any) -> Optional[int]:
        card_state = getattr(card, "card_state", None)
        return getattr(card_state, "card_index", None)

    def _append_trace(
        self,
        breakdown: Dict[str, Any],
        *,
        stage: str,
        event: str,
        totals: Optional[ScoringTotals] = None,
        card: Any = None,
        repetition_index: Optional[int] = None,
        source: Optional[str] = None,
        effect: Optional[ScoringEffect] = None,
        applies_to_score: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        trace_entry: Dict[str, Any] = {
            "stage": stage,
            "event": event,
            "applies_to_score": applies_to_score,
        }
        if card is not None:
            trace_entry["card"] = self._card_label(card)
            trace_entry["card_index"] = self._card_index(card)
        if repetition_index is not None:
            trace_entry["repetition_index"] = repetition_index
        if source is not None:
            trace_entry["source"] = source
        if effect is not None:
            trace_entry.update(
                {
                    "chips_add": effect.chips_add,
                    "mult_add": effect.mult_add,
                    "chips_mult": effect.chips_mult,
                    "mult_mult": effect.mult_mult,
                    "x_mult": effect.x_mult,
                    "money": effect.money,
                    "retriggers": effect.retriggers,
                }
            )
            if effect.message:
                trace_entry["message"] = effect.message
        if totals is not None:
            trace_entry.update(
                {
                    "chips_total": totals.chips,
                    "mult_total": totals.mult,
                    "x_mult_total": totals.x_mult,
                }
            )
        if extra:
            trace_entry.update(extra)
        breakdown.setdefault("scoring_trace", []).append(trace_entry)

    def _apply_individual_jokers(
        self,
        card: Any,
        context: ScoringContext,
        breakdown: Dict[str, Any],
        *,
        phase: str = "individual_scoring",
        preserve_retriggers: bool = False,
        stage_name: str = "scoring_card_effects",
        repetition_index: int,
    ) -> ScoringEffect:
        card_context = {
            'phase': phase,
            'card': card,
            'cards': context.cards,
            'scoring_cards': context.scoring_cards,
            'hand_type': context.hand_type_name,
        }
        combined = ScoringEffect()

        for joker_index, joker_name in self._iter_jokers(context.game_state):
            joker = type('Joker', (), {'name': joker_name})
            card_context['joker_index'] = joker_index
            raw_effect = self.joker_effects.apply_joker_effect(joker, card_context, context.game_state)
            effect = self.effect_converter.convert_joker_effect(raw_effect)
            if not preserve_retriggers:
                effect.retriggers = 0
            combined = combined.combine(effect)
            self._record_raw_side_effects(raw_effect, breakdown)

            if effect.chips_add or effect.mult_add or effect.x_mult != 1.0:
                breakdown['effects_applied'].append(
                    f"{joker_name} on {self._card_label(card)}: +{effect.chips_add}c +{effect.mult_add}m x{effect.x_mult}"
                )
            self._append_trace(
                breakdown,
                stage=stage_name if repetition_index == 0 else "repetitions",
                event="individual_joker_effect",
                card=card,
                repetition_index=repetition_index,
                source=joker_name,
                effect=effect,
                applies_to_score=True,
            )

        return combined

    @staticmethod
    def _record_raw_side_effects(raw_effect: Optional[Dict], breakdown: Dict[str, Any]) -> None:
        if not isinstance(raw_effect, dict):
            return
        created_consumable = raw_effect.get('created_consumable')
        if created_consumable:
            breakdown.setdefault('consumables_created', []).append(created_consumable)

    @staticmethod
    def _effect_present(effect: ScoringEffect) -> bool:
        return any(
            (
                effect.chips_add,
                effect.mult_add,
                effect.money,
                effect.retriggers,
                effect.message,
                effect.chips_mult != 1.0,
                effect.mult_mult != 1.0,
                effect.x_mult != 1.0,
            )
        )

    def _joker_retrigger_count(
        self,
        *,
        card: Any,
        context: ScoringContext,
        phase: str,
        effects_present: bool = True,
    ) -> int:
        getter = getattr(self.joker_effects, "get_retrigger_count", None)
        if getter is None:
            return 0

        retriggers = 0
        for joker_index, joker_name in self._iter_jokers(context.game_state):
            joker = type('Joker', (), {'name': joker_name})
            retriggers += int(
                getter(
                    joker,
                    {
                        "phase": phase,
                        "card": card,
                        "cards": context.cards,
                        "scoring_cards": context.scoring_cards,
                        "hand_type": context.hand_type_name,
                        "is_first_scoring_card": bool(context.scoring_cards and context.scoring_cards[0] is card),
                        "effects_present": effects_present,
                        "joker_index": joker_index,
                    },
                    context.game_state,
                )
                or 0
            )
        return retriggers

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
        stage_name: Optional[str] = None,
        applies_to_score: bool = True,
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
            self._append_trace(
                breakdown,
                stage=stage_name or phase,
                event="joker_phase_effect",
                source=joker_name,
                effect=effect,
                applies_to_score=applies_to_score,
                extra={"phase": phase},
            )

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
        totals: ScoringTotals,
        effect: ScoringEffect,
        *,
        apply_x_immediately: bool = False,
    ) -> None:
        totals.chips += effect.chips_add
        totals.mult += effect.mult_add
        totals.score_mult += effect.mult_add
        totals.chips = int(totals.chips * effect.chips_mult)
        totals.mult *= effect.mult_mult
        totals.score_mult *= effect.mult_mult
        if apply_x_immediately:
            totals.score_mult *= effect.x_mult
        else:
            totals.deferred_x_mult *= effect.x_mult
        totals.x_mult *= effect.x_mult

    def _held_card_base_effect(self, held_card: Any, breakdown: Dict[str, Any]) -> ScoringEffect:
        if self._is_card_debuffed(held_card):
            return ScoringEffect()

        enhancement = self._card_enhancement(held_card)
        x_mult = EnhancementEffects.get_mult_multiplier(enhancement, in_hand=True)
        if x_mult != 1.0:
            breakdown["effects_applied"].append(
                f"Held card ({enhancement.name.title()}): x{x_mult}"
            )
            return ScoringEffect(x_mult=x_mult, message="Held card")
        return ScoringEffect()

    def _played_card_retrigger_count(
        self,
        card: Any,
        context: ScoringContext,
    ) -> int:
        return int(self._card_seal(card) == Seal.RED) + self._joker_retrigger_count(
            card=card,
            context=context,
            phase="played_card",
        )

    def _held_card_retrigger_count(
        self,
        held_card: Any,
        context: ScoringContext,
        *,
        effects_present: bool,
    ) -> int:
        if not effects_present:
            return 0
        return int(self._card_seal(held_card) == Seal.RED) + self._joker_retrigger_count(
            card=held_card,
            context=context,
            phase="held_card",
            effects_present=True,
        )

    def _apply_effect_breakdown(
        self,
        breakdown: Dict[str, Any],
        effect: ScoringEffect,
    ) -> None:
        breakdown["money_gained"] += effect.money
        breakdown["joker_chips"] += effect.chips_add
        breakdown["joker_mult"] += effect.mult_add
        breakdown["joker_x_mult"] *= effect.x_mult

    def _apply_scoring_card_event(
        self,
        *,
        card: Any,
        repetition_index: int,
        context: ScoringContext,
        totals: ScoringTotals,
        breakdown: Dict[str, Any],
        card_breakdown: Dict[str, Any],
        cached_individual_effect: Optional[ScoringEffect] = None,
        preserve_retriggers: bool = False,
    ) -> ScoringEffect:
        stage_name = "scoring_card_effects" if repetition_index == 0 else "repetitions"
        event_effect = self._score_card_with_side_effects(card, breakdown)
        self._apply_effect_to_totals(totals, event_effect, apply_x_immediately=True)
        card_breakdown["chips"] += event_effect.chips_add
        card_breakdown["mult"] += event_effect.mult_add
        card_breakdown["x_mult"] *= event_effect.x_mult
        self._append_trace(
            breakdown,
            stage=stage_name,
            event="playing_card_base_enhancement",
            card=card,
            repetition_index=repetition_index,
            source="playing_card",
            effect=event_effect,
            totals=totals,
        )

        individual_effect = cached_individual_effect or self._apply_individual_jokers(
            card,
            context,
            breakdown,
            preserve_retriggers=preserve_retriggers,
            repetition_index=repetition_index,
        )
        self._apply_effect_to_totals(totals, individual_effect, apply_x_immediately=True)
        self._apply_effect_breakdown(breakdown, individual_effect)

        edition_effect = self._card_edition_effect(card)
        self._apply_effect_to_totals(totals, edition_effect, apply_x_immediately=True)
        card_breakdown["chips"] += edition_effect.chips_add
        card_breakdown["mult"] += edition_effect.mult_add
        card_breakdown["x_mult"] *= edition_effect.x_mult
        self._append_trace(
            breakdown,
            stage=stage_name,
            event="playing_card_edition",
            card=card,
            repetition_index=repetition_index,
            source="edition",
            effect=edition_effect,
            totals=totals,
        )

        return individual_effect

    def _resolve_scoring_card(
        self,
        card: Any,
        context: ScoringContext,
        totals: ScoringTotals,
        breakdown: Dict[str, Any],
        card_breakdown: Dict[str, Any],
    ) -> int:
        if self._is_card_debuffed(card):
            breakdown['effects_applied'].append("Debuffed card: no card or individual joker effects")
            self._append_trace(
                breakdown,
                stage="scoring_card_effects",
                event="debuffed_scoring_card",
                card=card,
                totals=totals,
            )
            return 0

        retrigger_getter = getattr(self.joker_effects, "get_retrigger_count", None)
        if retrigger_getter is not None:
            retriggers = self._played_card_retrigger_count(card, context)
            self._append_trace(
                breakdown,
                stage="repetitions",
                event="repetition_discovery",
                card=card,
                repetition_index=0,
                source="red_seal_and_jokers",
                effect=ScoringEffect(retriggers=retriggers),
                totals=totals,
                extra={
                    "red_seal_retriggers": int(self._card_seal(card) == Seal.RED),
                    "joker_retriggers": max(0, retriggers - int(self._card_seal(card) == Seal.RED)),
                    "total_retriggers": retriggers,
                },
            )
            self._apply_scoring_card_event(
                card=card,
                repetition_index=0,
                context=context,
                totals=totals,
                breakdown=breakdown,
                card_breakdown=card_breakdown,
            )
        else:
            first_individual_effect = self._apply_scoring_card_event(
                card=card,
                repetition_index=0,
                context=context,
                totals=totals,
                breakdown=breakdown,
                card_breakdown=card_breakdown,
                preserve_retriggers=True,
            )
            retriggers = int(self._card_seal(card) == Seal.RED) + first_individual_effect.retriggers
            self._append_trace(
                breakdown,
                stage="repetitions",
                event="repetition_discovery",
                card=card,
                repetition_index=0,
                source="red_seal_and_jokers",
                effect=ScoringEffect(retriggers=retriggers),
                totals=totals,
                extra={
                    "red_seal_retriggers": int(self._card_seal(card) == Seal.RED),
                    "joker_retriggers": first_individual_effect.retriggers,
                    "total_retriggers": retriggers,
                },
            )

        for repetition_index in range(1, retriggers + 1):
            self._apply_scoring_card_event(
                card=card,
                repetition_index=repetition_index,
                context=context,
                totals=totals,
                breakdown=breakdown,
                card_breakdown=card_breakdown,
            )

        return retriggers

    def _resolve_held_card(
        self,
        held_card: Any,
        context: ScoringContext,
        totals: ScoringTotals,
        breakdown: Dict[str, Any],
    ) -> int:
        if self._is_card_debuffed(held_card):
            self._append_trace(
                breakdown,
                stage="held_card_effects",
                event="held_card_debuffed",
                card=held_card,
                totals=totals,
            )
            return 0

        base_effect = self._held_card_base_effect(held_card, breakdown)
        self._apply_effect_to_totals(totals, base_effect)
        self._append_trace(
            breakdown,
            stage="held_card_effects",
            event="held_card_base_effect",
            card=held_card,
            repetition_index=0,
            source="held_card",
            effect=base_effect,
            totals=totals,
        )

        joker_effect = self._apply_individual_jokers(
            held_card,
            context,
            breakdown,
            phase="held_card",
            stage_name="held_card_effects",
            repetition_index=0,
        )
        self._apply_effect_to_totals(totals, joker_effect)
        self._apply_effect_breakdown(breakdown, joker_effect)

        effects_present = self._effect_present(base_effect) or self._effect_present(joker_effect)
        retriggers = self._held_card_retrigger_count(
            held_card,
            context,
            effects_present=effects_present,
        )
        self._append_trace(
            breakdown,
            stage="held_card_effects",
            event="held_repetition_discovery",
            card=held_card,
            repetition_index=0,
            source="red_seal_and_jokers",
            effect=ScoringEffect(retriggers=retriggers),
            totals=totals,
            extra={
                "effects_present": effects_present,
                "red_seal_retriggers": int(self._card_seal(held_card) == Seal.RED) if effects_present else 0,
                "joker_retriggers": max(0, retriggers - (int(self._card_seal(held_card) == Seal.RED) if effects_present else 0)),
                "total_retriggers": retriggers,
            },
        )

        for repetition_index in range(1, retriggers + 1):
            repeat_base_effect = self._held_card_base_effect(held_card, breakdown)
            self._apply_effect_to_totals(totals, repeat_base_effect)
            self._append_trace(
                breakdown,
                stage="held_card_effects",
                event="held_card_base_effect",
                card=held_card,
                repetition_index=repetition_index,
                source="held_card",
                effect=repeat_base_effect,
                totals=totals,
            )
            repeat_joker_effect = self._apply_individual_jokers(
                held_card,
                context,
                breakdown,
                phase="held_card",
                stage_name="held_card_effects",
                repetition_index=repetition_index,
            )
            self._apply_effect_to_totals(totals, repeat_joker_effect)
            self._apply_effect_breakdown(breakdown, repeat_joker_effect)

        return retriggers

    def _apply_scoring_card_destruction_hooks(
        self,
        context: ScoringContext,
        breakdown: Dict[str, Any],
    ) -> ScoringEffect:
        combined = ScoringEffect()
        pending_glass = set(breakdown.pop("_glass_cards_to_destroy", []))

        for card in context.scoring_cards:
            phase_effect = self._apply_joker_phase(
                "destroying_card",
                context,
                breakdown,
                extra_context={"destroying_card": card},
                stage_name="destruction_hooks",
                applies_to_score=False,
            )
            combined = combined.combine(phase_effect)
            card_index = self._card_index(card)
            if card_index is not None and card_index in pending_glass:
                if card_index not in breakdown["cards_to_destroy"]:
                    breakdown["cards_to_destroy"].append(card_index)
                self._append_trace(
                    breakdown,
                    stage="destruction_hooks",
                    event="playing_card_destroyed",
                    card=card,
                    source="glass_card",
                    applies_to_score=False,
                )

        return combined
    
    def score_hand(self, context: ScoringContext) -> Tuple[int, Dict[str, Any]]:
        """
        Score a hand with all effects properly applied
        
        Returns:
            (final_score, scoring_breakdown)
        """
        self.joker_effects.reset_scoring_hand_state(context.game_state)

        base_chips, base_mult = self._base_hand_values(context)
        totals = ScoringTotals(
            chips=base_chips,
            mult=float(base_mult),
            score_mult=float(base_mult),
        )

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
            'scoring_trace': [],
        }
        self._append_trace(
            breakdown,
            stage="base_hand",
            event="base_hand",
            totals=totals,
            source=context.hand_type_name,
        )

        before_effect = self._apply_joker_phase(
            "before_scoring",
            context,
            breakdown,
            stage_name="before_scoring_jokers",
        )
        self._apply_effect_to_totals(totals, before_effect)
        self._apply_effect_breakdown(breakdown, before_effect)
        self._append_trace(
            breakdown,
            stage="before_scoring_jokers",
            event="phase_totals",
            totals=totals,
            source="before_scoring",
            effect=before_effect,
        )

        modified_base_chips, modified_base_mult = self._blind_modified_base_values(
            context,
            base_chips,
            base_mult,
        )
        blind_effect = ScoringEffect(
            chips_add=modified_base_chips - base_chips,
            mult_add=modified_base_mult - base_mult,
        )
        self._apply_effect_to_totals(totals, blind_effect)
        self._append_trace(
            breakdown,
            stage="blind_modification",
            event="blind_modification",
            totals=totals,
            source=context.game_state.get("active_boss_blind") or "blind_modifier",
            effect=blind_effect,
        )

        card_chip_total = 0
        card_enhancement_mult = 0
        card_enhancement_x_mult = 1.0
        card_retriggers = 0

        for card in context.scoring_cards:
            per_card = {"chips": 0, "mult": 0, "x_mult": 1.0}
            card_retriggers += self._resolve_scoring_card(card, context, totals, breakdown, per_card)
            card_chip_total += per_card["chips"]
            card_enhancement_mult += per_card["mult"]
            card_enhancement_x_mult *= per_card["x_mult"]

        held_retriggers = 0
        for held_card in context.game_state.get("held_cards", []):
            held_retriggers += self._resolve_held_card(held_card, context, totals, breakdown)
        self._append_trace(
            breakdown,
            stage="held_card_effects",
            event="held_card_phase_totals",
            totals=totals,
            source="held_cards",
            effect=ScoringEffect(retriggers=held_retriggers),
        )

        self._apply_joker_phase(
            "held_card",
            context,
            breakdown,
            stage_name="held_card_effects",
            applies_to_score=False,
        )

        edition_chip_mult_effect = self._apply_joker_phase(
            "joker_edition_chip_mult",
            context,
            breakdown,
            stage_name="joker_edition_chip_mult_effects",
        )
        self._apply_effect_to_totals(totals, edition_chip_mult_effect)
        self._apply_effect_breakdown(breakdown, edition_chip_mult_effect)

        main_effect = self._apply_joker_phase(
            "scoring",
            context,
            breakdown,
            stage_name="joker_main_effects",
        )
        self._apply_effect_to_totals(totals, main_effect)
        self._apply_effect_breakdown(breakdown, main_effect)

        joker_on_joker_effect = self._apply_joker_phase(
            "joker_on_joker",
            context,
            breakdown,
            stage_name="joker_on_joker_effects",
        )
        self._apply_effect_to_totals(totals, joker_on_joker_effect)
        self._apply_effect_breakdown(breakdown, joker_on_joker_effect)

        edition_x_mult_effect = self._apply_joker_phase(
            "joker_edition_x_mult",
            context,
            breakdown,
            stage_name="joker_edition_x_mult_effects",
        )
        self._apply_effect_to_totals(totals, edition_x_mult_effect)
        self._apply_effect_breakdown(breakdown, edition_x_mult_effect)

        final_step_effect = self._apply_joker_phase(
            "final_scoring_step",
            context,
            breakdown,
            stage_name="final_scoring_step",
        )
        self._apply_effect_to_totals(totals, final_step_effect)
        self._apply_effect_breakdown(breakdown, final_step_effect)

        destruction_effect = self._apply_scoring_card_destruction_hooks(context, breakdown)
        self._apply_effect_breakdown(breakdown, destruction_effect)

        after_hand_effect = self._apply_joker_phase(
            "after_hand",
            context,
            breakdown,
            stage_name="after_hand_effects",
            applies_to_score=False,
        )
        self._apply_effect_breakdown(breakdown, after_hand_effect)

        final_score = int(totals.chips * totals.score_mult * totals.deferred_x_mult)

        money_gained = int(breakdown["money_gained"])
        if money_gained > 0:
            context.game_state['money'] = context.game_state.get('money', 0) + money_gained

        breakdown['final_chips'] = totals.chips
        breakdown['final_mult'] = totals.mult
        breakdown['final_x_mult'] = totals.x_mult
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

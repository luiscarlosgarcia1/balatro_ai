"""Helpers for adapting cards between environment subsystems."""

from __future__ import annotations

from typing import Any, Optional

from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core_utils.state import CardState, UnifiedGameState


class CardAdapter:
    """Convert between the internal card model and subsystem-specific shapes."""

    @staticmethod
    def from_game_card(game_card: Any) -> Card:
        """Convert legacy card-like objects into the core Card type."""
        if hasattr(game_card, "rank") and hasattr(game_card, "suit"):
            rank_value = (
                game_card.rank.value + 2
                if hasattr(game_card.rank, "value")
                else game_card.rank
            )
            suit_value = (
                game_card.suit.value
                if hasattr(game_card.suit, "value")
                else game_card.suit
            )
            return Card(rank=Rank(rank_value), suit=Suit(suit_value))
        return game_card

    @staticmethod
    def to_scoring_format(
        card: Card,
        card_idx: Optional[int] = None,
        state: Optional[UnifiedGameState] = None,
    ) -> Any:
        """Create the card-like object expected by the scoring stack."""
        base_chips = card.rank.base_chips
        card_state = None
        if state is not None and card_idx is not None:
            card_state = state.card_states.get(card_idx)
            if card_state is None:
                card_state = CardState(card_idx)

        if card_state and card_state.enhancement == Enhancement.STONE:
            rank_value = 0
            suit_name = "Stone"
        else:
            rank_value = card.rank.value
            suit_name = card.suit.name.title()

        chip_value = (
            card_state.calculate_chip_bonus(base_chips)
            if card_state is not None
            else base_chips
        )

        return type(
            "ScoringCard",
            (),
            {
                "rank": rank_value,
                "suit": suit_name,
                "base_value": base_chips,
                "chip_value": lambda: chip_value,
                "enhancement": card_state.enhancement if card_state else Enhancement.NONE,
                "edition": card_state.edition if card_state else Edition.NONE,
                "seal": card_state.seal if card_state else Seal.NONE,
                "card_state": card_state,
                "original_card": card,
            },
        )

    @staticmethod
    def to_consumable_format(
        card: Card,
        card_idx: Optional[int] = None,
        state: Optional[UnifiedGameState] = None,
    ) -> Any:
        """Create the card-like object expected by consumable handlers."""
        card_state = None
        if state is not None and card_idx is not None:
            card_state = state.card_states.get(card_idx)
            if card_state is None:
                card_state = CardState(card_idx)

        return type(
            "ConsumableCard",
            (),
            {
                "rank": card.rank,
                "suit": card.suit,
                "enhancement": card_state.enhancement if card_state else Enhancement.NONE,
                "edition": card_state.edition if card_state else Edition.NONE,
                "seal": card_state.seal if card_state else Seal.NONE,
                "card_idx": card_idx,
            },
        )

    @staticmethod
    def encode_to_int(card: Card) -> int:
        """Encode a card into the observation integer representation."""
        return int(card)

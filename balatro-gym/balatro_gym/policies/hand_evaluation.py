"""Canonical card normalization and immediate hand evaluation rules."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


RANK_VALUES = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10}
FACE_CHIPS = {"A": 11, "K": 10, "Q": 10, "J": 10, "T": 10}
POKER_CATEGORIES = (
    "High Card",
    "Pair",
    "Two Pair",
    "Three of a Kind",
    "Straight",
    "Flush",
    "Full House",
    "Four of a Kind",
    "Straight Flush",
)


def card_value(card: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    """Return the bridge's card-value payload, tolerating fixture shorthand."""
    return card.get("value", card) if isinstance(card, Mapping) else {}


def card_rank_name(card: Mapping[str, Any] | Any) -> str:
    return str(card_value(card).get("rank", ""))


def card_rank(card: Mapping[str, Any] | Any) -> int:
    rank = card_rank_name(card)
    return RANK_VALUES.get(rank.upper(), int(rank) if rank.isdigit() else 0)


def card_suit(card: Mapping[str, Any] | Any) -> str | None:
    suit = card_value(card).get("suit")
    return str(suit) if suit is not None else None


def card_chips(card: Mapping[str, Any] | Any) -> int:
    value = card_value(card)
    rank = card_rank_name(card)
    return int(value.get("chips", FACE_CHIPS.get(rank.upper(), int(rank) if rank.isdigit() else 0)))


def poker_category(cards: Sequence[Mapping[str, Any] | Any]) -> str:
    ranks = [card_rank(card) for card in cards]
    suits = [card_suit(card) for card in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)
    is_flush = len(cards) >= 5 and len(set(suits)) == 1 and suits[0] is not None
    unique_ranks = sorted(set(ranks))
    is_straight = len(cards) == 5 and (
        unique_ranks == list(range(unique_ranks[0], unique_ranks[0] + 5))
        or unique_ranks == [2, 3, 4, 5, 14]
    )
    if is_flush and is_straight:
        return "Straight Flush"
    if counts and counts[0] == 4:
        return "Four of a Kind"
    if counts and counts[0] == 3 and len(counts) > 1 and counts[1] == 2:
        return "Full House"
    if is_flush:
        return "Flush"
    if is_straight:
        return "Straight"
    if counts and counts[0] == 3:
        return "Three of a Kind"
    if sum(count == 2 for count in counts) >= 2:
        return "Two Pair"
    if counts and counts[0] == 2:
        return "Pair"
    return "High Card"

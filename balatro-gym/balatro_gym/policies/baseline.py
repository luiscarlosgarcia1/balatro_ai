"""The transparent deterministic legal-policy baseline."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from balatro_gym.environments.live import ActionKind, LegalAction, RoundTacticsObservation

from .policy import Policy


DISCARD_SCORE_THRESHOLD = 20
POKER_RANKS = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10}
# Balatro scoring gives face cards 10 chips, while poker matching still orders them.
CARD_CHIPS = {"A": 11, "K": 10, "Q": 10, "J": 10, "T": 10}


class DeterministicLegalHeuristic:
    """Choose immediate-scoring plays, or a settled deterministic discard."""

    revision = "deterministic-legal-heuristic/v1"

    def select_action(
        self,
        observation: RoundTacticsObservation,
        legal_action_mask: Sequence[LegalAction],
    ) -> LegalAction:
        if not legal_action_mask:
            raise ValueError("Round Tactics policy requires a non-empty legal action mask")

        plays = [action for action in legal_action_mask if action.kind == ActionKind.PLAY]
        best_play = min(
            plays,
            key=lambda action: (
                -self._immediate_score(observation, action),
                len(action.indices),
                action.indices,
            ),
            default=None,
        )
        if (
            best_play is not None
            and (self._immediate_score(observation, best_play) >= DISCARD_SCORE_THRESHOLD
            or observation.discards_left <= 0)
        ):
            return best_play

        discards = [
            action for action in legal_action_mask if action.kind == ActionKind.DISCARD
        ]
        if discards:
            retained = self._retained_indices(observation)
            desired = self._discard_indices(observation, retained)
            exact_match = next(
                (action for action in discards if action.indices == desired), None
            )
            if exact_match is not None:
                return exact_match
            return min(discards, key=lambda action: self._discard_priority(observation, action))
        if best_play is not None:
            return best_play
        return min(legal_action_mask, key=lambda action: (action.kind, action.indices))

    def _immediate_score(
        self, observation: RoundTacticsObservation, action: LegalAction
    ) -> int:
        cards = tuple(observation.hand[index] for index in action.indices)
        category = self._poker_category(cards)
        hand_values = observation.poker_hands.get(category, {})
        chips = int(hand_values.get("chips", 0)) + sum(
            self._card_chips(card) for card in cards
        )
        return chips * int(hand_values.get("mult", 1))

    def _retained_indices(self, observation: RoundTacticsObservation) -> set[int]:
        ranks = [self._rank(card) for card in observation.hand]
        rank_counts = Counter(ranks)
        made = {index for index, rank in enumerate(ranks) if rank_counts[rank] >= 2}
        if made:
            return made

        suits = [self._suit(card) for card in observation.hand]
        suit_counts = Counter(suit for suit in suits if suit is not None)
        largest_suit = max(suit_counts.values(), default=0)
        if largest_suit >= 2:
            candidates = [suit for suit, count in suit_counts.items() if count == largest_suit]
            selected_suit = max(
                candidates,
                key=lambda suit: tuple(
                    sorted(
                        (ranks[index], index)
                        for index, card_suit in enumerate(suits)
                        if card_suit == suit
                    )
                ),
            )
            return {index for index, suit in enumerate(suits) if suit == selected_suit}

        sequence = self._longest_rank_sequence(ranks)
        if len(sequence) >= 2:
            return sequence
        return {max(range(len(ranks)), key=lambda index: (ranks[index], -index))}

    @staticmethod
    def _discard_indices(
        observation: RoundTacticsObservation, retained: set[int]
    ) -> tuple[int, ...]:
        ranked = sorted(
            (index for index in range(len(observation.hand)) if index not in retained),
            key=lambda index: (
                DeterministicLegalHeuristic._rank(observation.hand[index]),
                index,
            ),
            reverse=True,
        )
        return tuple(sorted(ranked[:5]))

    @staticmethod
    def _discard_priority(
        observation: RoundTacticsObservation, action: LegalAction
    ) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...]]:
        ranked_cards = tuple(
            sorted(
                (
                    (DeterministicLegalHeuristic._rank(observation.hand[index]), index)
                    for index in action.indices
                ),
                reverse=True,
            )
        )
        return tuple((-rank, -index) for rank, index in ranked_cards), action.indices

    @staticmethod
    def _longest_rank_sequence(ranks: Sequence[int]) -> set[int]:
        by_rank: dict[int, int] = {}
        for index, rank in enumerate(ranks):
            by_rank.setdefault(rank, index)
        best: tuple[int, ...] = ()
        current: list[int] = []
        previous: int | None = None
        for rank in sorted(by_rank):
            if previous is None or rank <= previous + 2:
                current.append(by_rank[rank])
            else:
                current = [by_rank[rank]]
            if len(current) > len(best):
                best = tuple(current)
            previous = rank
        return set(best)

    @staticmethod
    def _poker_category(cards: Sequence[dict[str, Any] | Any]) -> str:
        ranks = [DeterministicLegalHeuristic._rank(card) for card in cards]
        suits = [DeterministicLegalHeuristic._suit(card) for card in cards]
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

    @staticmethod
    def _card_chips(card: dict[str, Any] | Any) -> int:
        value = card.get("value", {}) if isinstance(card, dict) else {}
        rank = str(value.get("rank", card.get("rank", "0") if isinstance(card, dict) else "0"))
        return int(value.get("chips", CARD_CHIPS.get(rank.upper(), int(rank) if rank.isdigit() else 0)))

    @staticmethod
    def _rank(card: dict[str, Any] | Any) -> int:
        value = card.get("value", {}) if isinstance(card, dict) else {}
        rank = str(value.get("rank", card.get("rank", "0") if isinstance(card, dict) else "0"))
        return POKER_RANKS.get(rank.upper(), int(rank) if rank.isdigit() else 0)

    @staticmethod
    def _suit(card: dict[str, Any] | Any) -> str | None:
        value = card.get("value", {}) if isinstance(card, dict) else {}
        suit = value.get("suit", card.get("suit") if isinstance(card, dict) else None)
        return str(suit) if suit is not None else None

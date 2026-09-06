"""The transparent deterministic legal-policy baseline."""

from __future__ import annotations

from collections.abc import Sequence

from balatro_gym.environments.live import ActionKind, LegalAction, RoundTacticsObservation

from .hand_evaluation import card_chips, card_rank, card_suit, poker_category
from .policy import Policy


DISCARD_SCORE_THRESHOLD = 20
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
        category = poker_category(cards)
        hand_values = observation.poker_hands.get(category, {})
        chips = int(hand_values.get("chips", 0)) + sum(
            card_chips(card) for card in cards
        )
        return chips * int(hand_values.get("mult", 1))

    def _retained_indices(self, observation: RoundTacticsObservation) -> set[int]:
        ranks = [card_rank(card) for card in observation.hand]
        rank_counts: dict[int, int] = {rank: ranks.count(rank) for rank in set(ranks)}
        made = {index for index, rank in enumerate(ranks) if rank_counts[rank] >= 2}
        if made:
            return made

        suits = [card_suit(card) for card in observation.hand]
        suit_counts = {suit: suits.count(suit) for suit in set(suits) if suit is not None}
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
                card_rank(observation.hand[index]),
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
                    (card_rank(observation.hand[index]), index)
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

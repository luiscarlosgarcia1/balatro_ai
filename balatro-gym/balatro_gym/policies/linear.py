"""The fixed-feature deterministic linear Round Tactics policy."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

from balatro_gym.environments.live import ActionKind, LegalAction, RoundTacticsObservation

from .hand_evaluation import (
    POKER_CATEGORIES,
    card_chips,
    card_rank_name,
    card_suit,
    poker_category,
)
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
SUITS = ("Spades", "Hearts", "Clubs", "Diamonds")
@dataclass(frozen=True)
class FeatureLayout:
    """The versioned, fixed-order feature vector contract for linear weights."""

    revision: str = "round-tactics-linear-features/v1"
    parameter_count: int = 35
    immediate_chips_index: int = 6
    immediate_multiplier_index: int = 7
    projected_score_index: int = 8
    category_indices: tuple[int, ...] = tuple(range(9, 18))


FEATURE_LAYOUT = FeatureLayout()


@dataclass(frozen=True)
class PolicyRevisionMetadata:
    """The immutable provenance required to reproduce a trained policy."""

    training_rng_seed: int
    population_size: int
    elite_count: int
    smoothing_previous_weight: float
    smoothing_elite_weight: float
    generation_count: int
    initial_mean: float
    initial_standard_deviation: float
    standard_deviation_floor: float
    selected_checkpoint_generation: int
    selected_checkpoint_candidate_index: int
    manifest_version: str
    development_seeds: tuple[str, ...]
    feature_layout_revision: str = FEATURE_LAYOUT.revision


class LinearLegalActionPolicy:
    """Score only actions in the supplied mask using shared linear parameters."""

    def __init__(
        self,
        parameters: Sequence[float],
        *,
        revision_metadata: PolicyRevisionMetadata | None = None,
    ) -> None:
        self.parameters = tuple(float(parameter) for parameter in parameters)
        if len(self.parameters) != FEATURE_LAYOUT.parameter_count:
            raise ValueError(
                "linear policy parameters must match the versioned feature layout"
            )
        if (
            revision_metadata is not None
            and revision_metadata.feature_layout_revision != FEATURE_LAYOUT.revision
        ):
            raise ValueError("policy revision metadata does not match the feature layout")
        self.revision_metadata = revision_metadata

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("linear policy checkpoints are immutable")
        super().__setattr__(name, value)

    @property
    def revision(self) -> str:
        if self.revision_metadata is None:
            return f"linear-legal-action/{FEATURE_LAYOUT.revision}"
        metadata = self.revision_metadata
        parameter_digest = sha256(repr(self.parameters).encode()).hexdigest()[:12]
        return (
            f"cem-linear/{metadata.feature_layout_revision}/"
            f"manifest-{metadata.manifest_version}/seed-{metadata.training_rng_seed}/"
            f"population-{metadata.population_size}-elites-{metadata.elite_count}/"
            f"smooth-{metadata.smoothing_previous_weight}-{metadata.smoothing_elite_weight}/"
            f"distribution-{metadata.initial_mean}-{metadata.initial_standard_deviation}-"
            f"floor-{metadata.standard_deviation_floor}/"
            f"generations-{metadata.generation_count}/"
            f"checkpoint-{metadata.selected_checkpoint_generation}-"
            f"{metadata.selected_checkpoint_candidate_index}/weights-{parameter_digest}"
        )

    def select_action(
        self,
        observation: RoundTacticsObservation,
        legal_action_mask: Sequence[LegalAction],
    ) -> LegalAction:
        if not legal_action_mask:
            raise ValueError("Round Tactics policy requires a non-empty legal action mask")
        return min(
            legal_action_mask,
            key=lambda action: (
                -self.score_action(observation, action),
                0 if action.kind == ActionKind.PLAY else 1,
                action.indices,
            ),
        )

    def score_action(
        self, observation: RoundTacticsObservation, action: LegalAction
    ) -> float:
        return sum(
            parameter * feature
            for parameter, feature in zip(
                self.parameters, self.features_for(observation, action), strict=True
            )
        )

    def features_for(
        self, observation: RoundTacticsObservation, action: LegalAction
    ) -> tuple[float, ...]:
        if action.kind == ActionKind.PLAY:
            chips, multiplier, category = self._immediate_hand_values(observation, action)
            projected_score = chips * multiplier
        else:
            chips = multiplier = projected_score = 0.0
            category = None
        rank_counts, suit_counts = self._counts(observation, action)
        category_features = tuple(
            1.0 if category == known_category else 0.0 for known_category in POKER_CATEGORIES
        )
        features = (
            1.0,
            1.0 if action.kind == ActionKind.PLAY else 0.0,
            self._ratio(observation.round_chips, observation.blind_target),
            self._ratio(observation.hands_left, 5),
            self._ratio(observation.discards_left, 3),
            self._ratio(len(action.indices), 5),
            self._ratio(chips, 100),
            self._ratio(multiplier, 20),
            self._ratio(projected_score, max(observation.blind_target, 1)),
            *category_features,
            *(self._ratio(rank_counts[rank], 5) for rank in RANKS),
            *(self._ratio(suit_counts[suit], 5) for suit in SUITS),
        )
        assert len(features) == FEATURE_LAYOUT.parameter_count
        return features

    def _immediate_hand_values(
        self, observation: RoundTacticsObservation, action: LegalAction
    ) -> tuple[float, float, str]:
        cards = tuple(observation.hand[index] for index in action.indices)
        category = poker_category(cards)
        values = observation.poker_hands.get(category, {})
        chips = float(values.get("chips", 0)) + sum(card_chips(card) for card in cards)
        multiplier = float(values.get("mult", 1))
        return chips, multiplier, category

    @staticmethod
    def _counts(
        observation: RoundTacticsObservation, action: LegalAction
    ) -> tuple[Counter[str], Counter[str]]:
        cards = tuple(observation.hand[index] for index in action.indices)
        return (
            Counter(card_rank_name(card) for card in cards),
            Counter(card_suit(card) for card in cards),
        )

    @staticmethod
    def _ratio(value: float | int, denominator: float | int) -> float:
        return float(value) / float(denominator) if denominator else 0.0

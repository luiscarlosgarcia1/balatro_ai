from __future__ import annotations

import pytest

from balatro_gym.environments.live import ActionKind, LegalAction
from balatro_gym.policies import FEATURE_LAYOUT, LinearLegalActionPolicy

from test_baseline_policy import card, observation


def test_linear_policy_scores_only_admitted_actions_and_resolves_equal_scores_canonically() -> None:
    policy = LinearLegalActionPolicy(parameters=(0.0,) * FEATURE_LAYOUT.parameter_count)
    state = observation((card("2", "Spades"), card("K", "Hearts")))
    mask = (
        LegalAction(ActionKind.DISCARD, (0,)),
        LegalAction(ActionKind.PLAY, (1,)),
        LegalAction(ActionKind.PLAY, (0,)),
    )

    assert policy.select_action(state, mask) == LegalAction(ActionKind.PLAY, (0,))


def test_linear_policy_uses_versioned_discard_zero_conventions() -> None:
    policy = LinearLegalActionPolicy(
        parameters=(0.0,) * FEATURE_LAYOUT.parameter_count
    )
    state = observation((card("2", "Spades"), card("2", "Hearts")))

    features = policy.features_for(state, LegalAction(ActionKind.DISCARD, (0, 1)))

    assert len(features) == FEATURE_LAYOUT.parameter_count
    assert features[FEATURE_LAYOUT.immediate_chips_index] == 0.0
    assert features[FEATURE_LAYOUT.immediate_multiplier_index] == 0.0
    assert features[FEATURE_LAYOUT.projected_score_index] == 0.0
    assert all(features[index] == 0.0 for index in FEATURE_LAYOUT.category_indices)


def test_linear_policy_parameters_are_immutable() -> None:
    policy = LinearLegalActionPolicy(parameters=(0.0,) * FEATURE_LAYOUT.parameter_count)

    with pytest.raises(AttributeError, match="immutable"):
        policy.parameters = (1.0,) * FEATURE_LAYOUT.parameter_count

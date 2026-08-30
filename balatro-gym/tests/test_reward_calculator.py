from types import SimpleNamespace

from balatro_gym.core_utils.provisional_reward_shaping import (
    ProvisionalRewardCalculator,
)
from balatro_gym.core_utils.reward_calculator import RewardCalculator
from balatro_gym.scoring.scoring_engine import HandType


def _card(rank_value: int):
    return SimpleNamespace(rank=SimpleNamespace(value=rank_value))


def test_reward_calculator_public_boundary_wraps_provisional_reward_shaping():
    calculator = RewardCalculator()

    assert calculator.__class__.__module__ == "balatro_gym.core_utils.reward_calculator"
    assert isinstance(calculator, ProvisionalRewardCalculator)


def test_reward_calculator_unverified_import_is_legacy_compatibility_shim():
    from balatro_gym.core_utils.unverified.reward_calculator import RewardCalculator as LegacyRewardCalculator

    assert LegacyRewardCalculator.__module__ == "balatro_gym.core_utils.provisional_reward_shaping"


def test_reward_calculator_penalizes_low_progress_single_card_high_card():
    calculator = RewardCalculator()

    reward = calculator.calculate_play_reward(
        old_score=0,
        new_score=12,
        chips_needed=300,
        final_score=12,
        hand_type=HandType.HIGH_CARD,
        cards_played=1,
        ante=1,
        hands_left=4,
        joker_names=[],
        selected_game_cards=[_card(5)],
    )

    assert reward["progress_delta"] < 2.0
    assert reward["weak_commitment"] == -6.0
    assert reward["blind_clear"] == 0.0


def test_reward_calculator_rewards_blind_clear_and_meaningful_progress():
    calculator = RewardCalculator()

    reward = calculator.calculate_play_reward(
        old_score=210,
        new_score=320,
        chips_needed=300,
        final_score=110,
        hand_type=HandType.ONE_PAIR,
        cards_played=2,
        ante=1,
        hands_left=3,
        joker_names=[],
        selected_game_cards=[_card(9), _card(9)],
    )

    assert reward["progress_delta"] > 0.0
    assert reward["blind_clear"] == 14.0
    assert reward["weak_commitment"] == 0.0


def test_reward_calculator_prefers_meaningful_pair_over_stalling_single_card():
    calculator = RewardCalculator()

    weak_reward = calculator.calculate_play_reward(
        old_score=0,
        new_score=12,
        chips_needed=300,
        final_score=12,
        hand_type=HandType.HIGH_CARD,
        cards_played=1,
        ante=1,
        hands_left=4,
        joker_names=[],
        selected_game_cards=[_card(5)],
    )
    pair_reward = calculator.calculate_play_reward(
        old_score=0,
        new_score=70,
        chips_needed=300,
        final_score=70,
        hand_type=HandType.ONE_PAIR,
        cards_played=2,
        ante=1,
        hands_left=4,
        joker_names=[],
        selected_game_cards=[_card(10), _card(10)],
    )

    assert pair_reward["progress_delta"] > weak_reward["progress_delta"]
    assert pair_reward["total_reward"] > weak_reward["total_reward"]


def test_reward_calculator_penalizes_late_stalling_single_card_more_when_progress_is_equal():
    calculator = RewardCalculator()

    safer_reward = calculator.calculate_play_reward(
        old_score=30,
        new_score=42,
        chips_needed=300,
        final_score=12,
        hand_type=HandType.HIGH_CARD,
        cards_played=1,
        ante=1,
        hands_left=4,
        joker_names=[],
        selected_game_cards=[_card(5)],
    )
    pressured_reward = calculator.calculate_play_reward(
        old_score=30,
        new_score=42,
        chips_needed=300,
        final_score=12,
        hand_type=HandType.HIGH_CARD,
        cards_played=1,
        ante=1,
        hands_left=1,
        joker_names=[],
        selected_game_cards=[_card(5)],
    )

    assert pressured_reward["weak_commitment"] < safer_reward["weak_commitment"]
    assert pressured_reward["total_reward"] < safer_reward["total_reward"]

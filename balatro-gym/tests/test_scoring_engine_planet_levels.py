import pytest

from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine


@pytest.mark.parametrize(
    ("hand_type", "expected_level_3"),
    [
        (HandType.HIGH_CARD, (25, 3)),
        (HandType.ONE_PAIR, (40, 4)),
        (HandType.TWO_PAIR, (60, 4)),
        (HandType.THREE_KIND, (70, 7)),
        (HandType.STRAIGHT, (90, 10)),
        (HandType.FLUSH, (65, 8)),
        (HandType.FULL_HOUSE, (90, 8)),
        (HandType.FOUR_KIND, (120, 13)),
        (HandType.STRAIGHT_FLUSH, (180, 16)),
        (HandType.FIVE_KIND, (190, 18)),
        (HandType.FLUSH_HOUSE, (220, 22)),
        (HandType.FLUSH_FIVE, (260, 22)),
    ],
)
def test_hand_levels_use_balatro_hand_specific_increments(hand_type, expected_level_3):
    engine = ScoreEngine()

    engine.set_hand_level(hand_type, 3)

    assert engine.get_hand_chips_mult(hand_type) == expected_level_3

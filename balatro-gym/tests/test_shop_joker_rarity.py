from __future__ import annotations

from balatro_gym.core.jokers import JOKER_LIBRARY, JOKER_RARITY_BY_ID
from balatro_gym.core.shop import PlayerState, Shop


class FixedRng:
    def __init__(self, rarity_roll: float):
        self.rarity_roll = rarity_roll

    def random(self) -> float:
        return self.rarity_roll

    def choice(self, sequence):
        return sequence[0]


def _shop_with_rarity_roll(rarity_roll: float) -> Shop:
    shop = Shop(1, PlayerState(chips=20), seed=1)
    shop.rng = FixedRng(rarity_roll)
    return shop


def test_choose_joker_rolls_common_uncommon_and_rare_rarity_before_pool_choice():
    cases = [
        (0.70, 1),
        (0.71, 2),
        (0.96, 3),
    ]

    for rarity_roll, expected_rarity in cases:
        joker = _shop_with_rarity_roll(rarity_roll)._choose_joker(set())

        assert JOKER_RARITY_BY_ID[joker.id] == expected_rarity


def test_choose_joker_never_rolls_legendary_without_legendary_path():
    shop = _shop_with_rarity_roll(0.99)

    for _ in range(10):
        joker = shop._choose_joker(set())

        assert joker.base_cost > 0
        assert JOKER_RARITY_BY_ID[joker.id] != 4


def test_choose_joker_empty_selected_rarity_pool_falls_back_to_base_joker():
    rare_joker_ids = {
        joker.id
        for joker in JOKER_LIBRARY
        if JOKER_RARITY_BY_ID[joker.id] == 3
    }
    shop = Shop(1, PlayerState(chips=20, jokers=list(rare_joker_ids)), seed=1)
    shop.rng = FixedRng(0.96)

    joker = shop._choose_joker(set())

    assert joker.id == 1
    assert joker.name == "Joker"

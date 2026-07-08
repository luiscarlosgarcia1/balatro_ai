from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.boss_blinds import BOSS_BLINDS, BossBlindManager, BossBlindType, select_boss_blind
from balatro_gym.core.constants import Action
from balatro_gym.core_utils.blind_scaling import get_blind_amount, get_blind_chips
from balatro_gym.core_utils.phase_handlers.blind_select import BlindSelectHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState


def test_blind_chips_match_balatro_default_scaling():
    expected = {
        1: (300, 450, 600),
        2: (800, 1200, 1600),
        3: (2000, 3000, 4000),
        4: (5000, 7500, 10000),
        5: (11000, 16500, 22000),
        6: (20000, 30000, 40000),
        7: (35000, 52500, 70000),
        8: (50000, 75000, 100000),
        9: (110000, 165000, 220000),
        10: (560000, 840000, 1120000),
    }

    for ante, (small, big, boss) in expected.items():
        assert get_blind_chips(ante, "small") == small
        assert get_blind_chips(ante, "big") == big
        assert get_blind_chips(ante, "boss") == boss

    assert get_blind_amount(0) == 100
    assert get_blind_chips(2, "boss", ante_scaling=2) == 3200


def test_boss_threshold_uses_absolute_boss_multiplier():
    state = UnifiedGameState(ante=2, round=3)
    game = SimpleNamespace(blinds=[0, 0, 0], blind_index=2)
    handler = BlindSelectHandler(state, game, BossBlindManager(), None, DeterministicRNG(1))

    state.pending_boss_blind = BossBlindType.THE_WALL
    reward, terminated, info = handler.step(Action.SELECT_BLIND_BASE + 2)

    assert terminated is False
    assert reward > 0
    assert state.chips_needed == 3200
    assert info["chips_needed"] == 3200
    assert info["chip_multiplier"] == 4.0


def test_boss_metadata_matches_balatro_names_and_multipliers():
    assert not hasattr(BossBlindType, "THE_OXIDE")
    assert BOSS_BLINDS[BossBlindType.THE_OX].name == "The Ox"
    assert BOSS_BLINDS[BossBlindType.THE_NEEDLE].mult == 1.0
    assert BOSS_BLINDS[BossBlindType.THE_WALL].mult == 4.0
    assert BOSS_BLINDS[BossBlindType.THE_VIOLET].name == "Violet Vessel"
    assert BOSS_BLINDS[BossBlindType.THE_VIOLET].mult == 6.0
    assert BOSS_BLINDS[BossBlindType.THE_VIOLET].money_reward == 8
    assert BOSS_BLINDS[BossBlindType.THE_CERULEAN].showdown is True


def test_boss_selection_uses_min_ante_showdown_and_minimum_use():
    class FirstChoiceRng:
        def choice(self, _stream, sequence):
            return sequence[0]

    bosses_used = {}
    ante_one_seen = {
        select_boss_blind(1, rng=FirstChoiceRng(), bosses_used=bosses_used)
        for _ in range(8)
    }

    assert ante_one_seen == {
        BossBlindType.THE_HOOK,
        BossBlindType.THE_PSYCHIC,
        BossBlindType.THE_GOAD,
        BossBlindType.THE_WINDOW,
        BossBlindType.THE_MANACLE,
        BossBlindType.THE_PILLAR,
        BossBlindType.THE_HEAD,
        BossBlindType.THE_CLUB,
    }
    assert all(count == 1 for count in bosses_used.values())

    ante_two = select_boss_blind(2, rng=FirstChoiceRng(), bosses_used=bosses_used)
    assert BOSS_BLINDS[ante_two].min_ante == 2

    showdown_used = {}
    showdown = select_boss_blind(8, rng=FirstChoiceRng(), bosses_used=showdown_used)
    assert BOSS_BLINDS[showdown].showdown is True
    assert showdown_used[showdown] == 1

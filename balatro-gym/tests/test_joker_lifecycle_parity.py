from types import SimpleNamespace

from balatro_gym.core.boss_blinds import BossBlindType
from balatro_gym.core.cards import Rank, Seal, Suit
from balatro_gym.core.constants import Phase
from balatro_gym.core.jokers import JOKER_LIBRARY
from balatro_gym.core_utils.joker_sale import sell_joker
from balatro_gym.core_utils.phase_handlers.shop_phase import ShopPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.environments.balatro_env_small import BalatroEnv


def _joker(name: str):
    return next(joker for joker in JOKER_LIBRARY if joker.name == name)


class _ChoiceRNG:
    def __init__(self, picked_index: int = 0):
        self.picked_index = picked_index

    def choice(self, _stream: str, sequence):
        return sequence[self.picked_index]


def test_invisible_joker_sale_duplicates_other_joker_when_row_is_full():
    state = UnifiedGameState(joker_slots=3)
    state.jokers = [_joker("Invisible Joker"), _joker("Greedy Joker"), _joker("Burglar")]
    state.negative_jokers = [1]
    state.invisible_joker_rounds = {0: 2}

    sold_joker, _sell_value, info = sell_joker(state, 0, rng=_ChoiceRNG(0))

    assert sold_joker.name == "Invisible Joker"
    assert [joker.name for joker in state.jokers] == ["Greedy Joker", "Burglar", "Greedy Joker"]
    assert state.negative_jokers == [0]
    assert info["invisible_duplicate"] == "Greedy Joker"


def test_invisible_joker_copy_resets_copied_invisible_round_counter():
    state = UnifiedGameState(joker_slots=2)
    state.jokers = [_joker("Invisible Joker"), _joker("Invisible Joker")]
    state.invisible_joker_rounds = {0: 2, 1: 5}

    sell_joker(state, 0, rng=_ChoiceRNG(0))

    assert [joker.name for joker in state.jokers] == ["Invisible Joker", "Invisible Joker"]
    assert state.invisible_joker_rounds == {0: 5, 1: 0}


def test_perkeo_creates_negative_consumable_copy_even_when_slots_are_full():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        round=1,
        consumables=["The Fool", "Hex"],
        consumable_slots=2,
    )
    state.jokers = [_joker("Perkeo")]
    handler = ShopPhaseHandler(state, _ChoiceRNG(0))

    _reward, _terminated, info = handler._handle_end_shop()

    assert state.phase == Phase.BLIND_SELECT
    assert state.consumables == ["The Fool", "Hex", "The Fool"]
    assert state.negative_consumables == [2]
    assert state.active_consumable_count() == 2
    assert info["perkeo_created"] == ["The Fool"]


def test_burglar_and_madness_apply_on_non_boss_blind_selection():
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        round=1,
        hands_left=4,
        discards_left=3,
    )
    state.jokers = [_joker("Burglar"), _joker("Joker"), _joker("Madness")]
    state.eternal_jokers = [0]

    state.reset_round_state()

    assert [joker.name for joker in state.jokers] == ["Burglar", "Madness"]
    assert state.hands_left == 7
    assert state.discards_left == 0
    assert state.burglar_bonus_hands_this_round == 3
    assert state.madness_xmult == {1: 1.5}


def test_madness_still_grows_when_no_non_eternal_joker_can_be_destroyed():
    state = UnifiedGameState(phase=Phase.BLIND_SELECT, round=2)
    state.jokers = [_joker("Madness"), _joker("Burglar")]
    state.eternal_jokers = [1]

    state.reset_round_state()

    assert [joker.name for joker in state.jokers] == ["Madness", "Burglar"]
    assert state.madness_xmult == {0: 1.5}


def test_burglar_applies_on_boss_blind_selection_without_triggering_madness():
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        round=3,
        hands_left=4,
        discards_left=3,
    )
    state.jokers = [_joker("Burglar"), _joker("Joker"), _joker("Madness")]

    state.reset_round_state()

    assert [joker.name for joker in state.jokers] == ["Burglar", "Joker", "Madness"]
    assert state.hands_left == 7
    assert state.discards_left == 0
    assert state.burglar_bonus_hands_this_round == 3
    assert state.madness_xmult == {}


def test_certificate_creates_persistent_debuffed_card_and_save_load_preserves_state(monkeypatch):
    env = BalatroEnv(seed=7)
    env.state.jokers = [_joker("Certificate")]
    env.state.boss_blind_active = True
    env.state.active_boss_blind = BossBlindType.THE_PLANT
    env.boss_blind_manager.activate_boss_blind(BossBlindType.THE_PLANT, env.state.to_dict())

    def _fake_get_int(_stream: str, low: int, high: int) -> int:
        if low == int(Rank.TWO) and high == int(Rank.ACE):
            return int(Rank.JACK)
        return int(Suit.CLUBS)

    monkeypatch.setattr(env.play_handler.rng, "get_int", _fake_get_int)
    monkeypatch.setattr(env.play_handler.rng, "choice", lambda _stream, sequence: Seal.BLUE)

    env._start_play_phase()
    created_card_idx = len(env.state.deck) - 1
    created_state = env.state.card_states[created_card_idx]

    assert len(env.state.deck) == 53
    assert created_card_idx in env.state.hand_indexes
    assert len(env.state.hand_indexes) == 9
    assert created_state.seal == Seal.BLUE
    assert created_state.is_debuffed is True
    assert env.state.certificate_card_created_this_blind is True

    env.play_handler._draw_new_hand()
    assert len(env.state.deck) == 53

    saved = env.save_state()
    restored = BalatroEnv(seed=11)
    restored.load_state(saved)

    restored_state = restored.state.card_states[created_card_idx]
    assert len(restored.state.deck) == 53
    assert created_card_idx in restored.state.hand_indexes
    assert restored_state.seal == Seal.BLUE
    assert restored_state.is_debuffed is True
    assert restored.state.certificate_card_created_this_blind is True


def test_certificate_card_participates_in_first_draw_boss_effects(monkeypatch):
    env = BalatroEnv(seed=19)
    env.state.jokers = [_joker("Certificate")]
    env.state.boss_blind_active = True
    env.state.active_boss_blind = BossBlindType.THE_CERULEAN
    env.boss_blind_manager.activate_boss_blind(BossBlindType.THE_CERULEAN, env.state.to_dict())

    def _fake_get_int(_stream: str, low: int, high: int) -> int:
        if low == int(Rank.TWO) and high == int(Rank.ACE):
            return int(Rank.FIVE)
        return int(Suit.CLUBS)

    monkeypatch.setattr(env.play_handler.rng, "get_int", _fake_get_int)
    monkeypatch.setattr(env.play_handler.rng, "choice", lambda _stream, sequence: Seal.GOLD)
    monkeypatch.setattr(env.boss_blind_manager.rng, "choice", lambda _stream, sequence: sequence[-1])

    env._start_play_phase()

    assert len(env.state.hand_indexes) == 9
    assert env.state.boss_forced_selected_card == 8
    assert env.state.selected_cards == [8]


def test_new_joker_state_tables_survive_environment_save_and_load():
    env = BalatroEnv(seed=13)
    env.state.jokers = [_joker("Invisible Joker"), _joker("Madness")]
    env.state.negative_jokers = [0]
    env.state.invisible_joker_rounds = {0: 2}
    env.state.madness_xmult = {1: 2.5}
    env.state.consumables = ["The Fool", "Hex", "The Fool"]
    env.state.negative_consumables = [2]

    saved = env.save_state()
    restored = BalatroEnv(seed=17)
    restored.load_state(saved)

    assert restored.state.negative_jokers == [0]
    assert restored.state.invisible_joker_rounds == {0: 2}
    assert restored.state.madness_xmult == {1: 2.5}
    assert restored.state.negative_consumables == [2]

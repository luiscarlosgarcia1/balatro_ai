from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.cards import Card, Rank, Seal, Suit
from balatro_gym.core.constants import Action
from balatro_gym.core_utils.mvp_contract import build_mvp_action_mask, can_use_consumable_from_pack
from balatro_gym.core_utils.phase_handlers.pack_open import PackOpenHandler
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState


def test_pack_mask_and_resolution_allow_generation_with_negative_consumable_overflow(monkeypatch):
    state = UnifiedGameState(
        consumables=["Hex", "The Fool"],
        consumable_slots=2,
    )
    state.negative_consumables = [1]
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)

    monkeypatch.setattr("random.choice", lambda sequence: "Mars")

    handler.open_pack("Arcana Pack", ["The High Priestess"])

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_FROM_PACK_BASE] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "The High Priestess"
    assert state.consumables == ["Hex", "The Fool", "Mars"]
    assert state.negative_consumables == [1]
    assert state.active_consumable_count() == 2


def test_blue_seal_round_end_planet_uses_active_consumable_slots():
    state = UnifiedGameState(
        consumables=["Hex", "The Fool"],
        consumable_slots=2,
        last_hand_played="One Pair",
        last_held_card_indexes=[0],
    )
    state.negative_consumables = [1]
    state.deck = [Card(Rank.ACE, Suit.SPADES)]
    state.get_card_state(0).seal = Seal.BLUE

    manager = RoundManager(
        state,
        SimpleNamespace(),
        SimpleNamespace(end_of_round_effects=lambda _state: []),
        boss_blind_manager=None,
    )

    manager._create_planets_from_held_blue_seals()

    assert state.consumables == ["Hex", "The Fool", "Mercury"]
    assert state.negative_consumables == [1]
    assert state.active_consumable_count() == 2


def test_pack_capacity_check_supports_state_like_stubs_with_negative_consumables():
    state = SimpleNamespace(
        consumables=["Hex", "The Fool"],
        negative_consumables=[1],
        consumable_slots=2,
        last_tarot_planet_consumable="Mars",
        hand_size=5,
    )

    assert can_use_consumable_from_pack(state, "The Fool") is True
    assert can_use_consumable_from_pack(state, "The High Priestess") is True

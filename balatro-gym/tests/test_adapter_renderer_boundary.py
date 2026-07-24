from __future__ import annotations

from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.constants import Phase
from balatro_gym.core_utils import renderer as renderer_module
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.provisional_renderer import ProvisionalConsoleRenderer
from balatro_gym.core_utils.state import UnifiedGameState


def test_scoring_adapter_preserves_base_value_and_modifier_state_for_parity():
    state = UnifiedGameState(
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
    )
    card_state = state.get_card_state(0)
    card_state.enhancement = Enhancement.BONUS
    card_state.edition = Edition.FOIL
    card_state.seal = Seal.GOLD
    card_state.is_debuffed = True

    scoring_card = CardAdapter.to_scoring_format(state.deck[0], 0, state)

    assert scoring_card.rank == Rank.ACE.value
    assert scoring_card.suit == "Spades"
    assert scoring_card.base_value == 11
    assert scoring_card.chip_value() == 41
    assert scoring_card.enhancement == Enhancement.BONUS
    assert scoring_card.edition == Edition.FOIL
    assert scoring_card.seal == Seal.GOLD
    assert scoring_card.is_debuffed is True
    assert scoring_card.card_state is card_state
    assert scoring_card.original_card == state.deck[0]


def test_scoring_adapter_marks_stone_cards_with_balatro_style_scoring_shape():
    state = UnifiedGameState(deck=[Card(Rank.SEVEN, Suit.HEARTS)])
    state.get_card_state(0).enhancement = Enhancement.STONE

    scoring_card = CardAdapter.to_scoring_format(state.deck[0], 0, state)

    assert scoring_card.rank == 0
    assert scoring_card.suit == "Stone"
    assert scoring_card.base_value == 7
    assert scoring_card.chip_value() == 50


def test_consumable_adapter_exposes_mutable_card_surface_and_index():
    state = UnifiedGameState(deck=[Card(Rank.TWO, Suit.CLUBS)])
    card_state = state.get_card_state(0)
    card_state.enhancement = Enhancement.GLASS
    card_state.edition = Edition.HOLOGRAPHIC
    card_state.seal = Seal.RED

    consumable_card = CardAdapter.to_consumable_format(state.deck[0], 0, state)

    assert consumable_card.rank == Rank.TWO
    assert consumable_card.suit == Suit.CLUBS
    assert consumable_card.enhancement == Enhancement.GLASS
    assert consumable_card.edition == Edition.HOLOGRAPHIC
    assert consumable_card.seal == Seal.RED
    assert consumable_card.card_idx == 0


def test_renderer_module_exposes_only_explicitly_provisional_renderer():
    assert renderer_module.ProvisionalConsoleRenderer is ProvisionalConsoleRenderer
    assert not hasattr(renderer_module, "ConsoleRenderer")


def test_provisional_renderer_renders_debug_snapshot(capsys):
    state = UnifiedGameState(
        ante=3,
        round=2,
        phase=Phase.PLAY,
        money=9,
        chips_needed=1200,
        round_chips_scored=450,
        hands_left=2,
        discards_left=1,
        deck=[Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)],
        hand_indexes=[0, 1],
    )

    ProvisionalConsoleRenderer().render(state)

    assert capsys.readouterr().out.splitlines() == [
        "Phase: PLAY",
        "Ante 3 Round 2 | Money $9 | Chips 450/1200",
        "Hands left: 2 | Discards left: 1",
        "Hand: ACE of SPADES, KING of HEARTS",
    ]

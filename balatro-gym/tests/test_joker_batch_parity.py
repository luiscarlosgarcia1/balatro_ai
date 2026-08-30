from types import SimpleNamespace

from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType
from balatro_gym.core.cards import Card, Enhancement, Rank, Suit
from balatro_gym.core.constants import Phase
from balatro_gym.core.jokers import JOKER_LIBRARY
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import ScoreEngine
from balatro_gym.scoring.unified_scoring import UnifiedScorer


def _joker(name: str):
    return next(joker for joker in JOKER_LIBRARY if joker.name == name)


def _make_play_handler(state: UnifiedGameState, boss_manager: BossBlindManager | None = None) -> PlayPhaseHandler:
    engine = ScoreEngine()
    game = BalatroGame()
    game.deck = state.deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = state.discard_pile_indexes.copy()
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    game.hand_size = state.hand_size
    game.discards = state.discards_left
    return PlayPhaseHandler(
        state,
        game,
        engine,
        UnifiedScorer(engine, CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        boss_manager or BossBlindManager(),
        DeterministicRNG(7),
    )


def test_passive_joker_stats_react_to_add_remove_and_debuff_state():
    state = UnifiedGameState()

    state.add_joker(_joker("Juggler"))
    state.add_joker(_joker("Troubadour"))
    state.add_joker(_joker("Drunkard"))
    state.add_joker(_joker("Merry Andy"))

    assert state.hand_size == 11
    assert state.hands_left == 2
    assert state.discards_left == 7

    state.boss_disabled_joker_indexes = [0, 1, 2, 3]
    state.sync_passive_joker_effects()

    assert state.hand_size == 8
    assert state.hands_left == 4
    assert state.discards_left == 3

    state.boss_disabled_joker_indexes = []
    state.sync_passive_joker_effects()
    state.remove_joker(3)

    assert state.hand_size == 11
    assert state.hands_left == 3
    assert state.discards_left == 4


def test_blind_setting_jokers_create_assets(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        round=1,
        deck=[Card(Rank.ACE, Suit.SPADES)],
        jokers=[_joker("Riff-Raff"), _joker("Marble Joker"), _joker("Cartomancer")],
        joker_slots=5,
        consumable_slots=2,
    )

    chosen_common = _joker("Joker")
    monkeypatch.setattr(
        "balatro_gym.core_utils.state.random.choice",
        lambda sequence: chosen_common if chosen_common in sequence else sequence[0],
    )

    state.reset_round_state()

    assert len(state.jokers) == 5
    assert [joker.name for joker in state.jokers[:3]] == ["Riff-Raff", "Marble Joker", "Cartomancer"]
    assert all(joker.name == "Joker" for joker in state.jokers[3:])
    assert len(state.deck) == 2
    assert state.get_card_state(1).enhancement == Enhancement.STONE
    assert state.draw_pile_indexes[-1] == 1
    assert len(state.consumables) == 1


def test_burnt_joker_upgrades_first_discard_hand_before_resolution():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.ACE, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS)],
        hand_indexes=[0, 1, 2],
        selected_cards=[0, 1],
        discards_left=3,
        jokers=[_joker("Burnt Joker")],
    )
    handler = _make_play_handler(state)

    reward, terminated, info = handler._handle_discard()

    assert reward >= 0.2
    assert terminated is False
    assert info["burnt_joker_upgraded_hand"] == "Pair"
    assert handler.engine.get_hand_level(handler.game._classify_hand([Card(Rank.ACE, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS)])[0]) == 2


def test_midas_mask_turns_scored_face_cards_gold_before_scoring():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.KING, Suit.SPADES)],
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        chips_needed=500,
        jokers=[_joker("Midas Mask"), _joker("Golden Ticket")],
    )
    handler = _make_play_handler(state)
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    reward, terminated, info = handler._handle_play_hand()

    assert reward >= 0.0
    assert terminated is False
    assert info["score_breakdown"]["money_gained"] == 4
    assert state.get_card_state(0).enhancement == Enhancement.GOLD


def test_sixth_sense_destroys_lone_first_hand_six_and_creates_spectral():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.SIX, Suit.SPADES)],
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        chips_needed=500,
        jokers=[_joker("Sixth Sense")],
        consumable_slots=1,
    )
    handler = _make_play_handler(state)
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    reward, terminated, _info = handler._handle_play_hand()

    assert reward >= 0.0
    assert terminated is False
    assert state.get_card_state(0).is_destroyed is True
    assert state.consumables == ["Spectral"]


def test_matador_pays_when_boss_triggers_during_hand_resolution():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        chips_needed=500,
        money=0,
        jokers=[_joker("Matador")],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_FLINT,
    )
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_FLINT, state.to_dict())
    handler = _make_play_handler(state, manager)
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    reward, terminated, info = handler._handle_play_hand()

    assert reward >= 0.0
    assert terminated is False
    assert info["matador_money"] == 8
    assert state.money == 8

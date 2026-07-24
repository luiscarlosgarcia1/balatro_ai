from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.boss_blinds import BOSS_BLINDS, BossBlindManager, BossBlindType, select_boss_blind
from balatro_gym.core.cards import Card, Enhancement, Rank, Seal, Suit
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.mvp_contract import build_mvp_action_mask
from balatro_gym.core_utils.blind_scaling import get_blind_amount, get_blind_chips
from balatro_gym.core_utils.phase_handlers.blind_select import BlindSelectHandler
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine
from balatro_gym.scoring.unified_scoring import ScoringContext, UnifiedScorer


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


def test_blind_amount_matches_lua_high_ante_rounding_curve():
    # Matches balatro_unpacked/functions/misc_functions.lua:get_blind_amount
    assert get_blind_amount(11) == 7_200_000
    assert get_blind_amount(12) == 300_000_000
    assert get_blind_amount(13) == 47_000_000_000


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


def test_suit_face_pillar_and_verdant_debuffs_use_card_enums_and_ante_state():
    state = UnifiedGameState(
        deck=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.TWO, Suit.CLUBS),
        ]
    )
    manager = BossBlindManager()

    manager.activate_boss_blind(BossBlindType.THE_GOAD, state.to_dict())
    assert manager._is_card_debuffed(state.deck[0]) is True
    assert manager._is_card_debuffed(state.deck[1]) is False

    manager.activate_boss_blind(BossBlindType.THE_PLANT, state.to_dict())
    assert manager._is_card_debuffed(state.deck[1]) is True
    assert manager._is_card_debuffed(state.deck[2]) is False

    state.get_card_state(2).played_this_ante = True
    scoring_card = CardAdapter.to_scoring_format(state.deck[2], 2, state)
    manager.activate_boss_blind(BossBlindType.THE_PILLAR, state.to_dict())
    assert manager._is_card_debuffed(scoring_card) is True

    manager.activate_boss_blind(BossBlindType.THE_VERDANT, state.to_dict())
    assert all(manager._is_card_debuffed(card) for card in state.deck)


def test_debuffed_scoring_card_contributes_no_card_or_legacy_side_effects():
    state = UnifiedGameState(
        deck=[Card(Rank.ACE, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS)],
        hand_indexes=[0, 1],
    )
    debuffed = state.get_card_state(0)
    debuffed.is_debuffed = True
    debuffed.enhancement = Enhancement.GLASS
    debuffed.seal = Seal.GOLD
    scoring_cards = [
        CardAdapter.to_scoring_format(state.deck[0], 0, state),
        CardAdapter.to_scoring_format(state.deck[1], 1, state),
    ]

    score, breakdown = UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(
        ScoringContext(
            cards=scoring_cards,
            scoring_cards=scoring_cards,
            hand_type=HandType.ONE_PAIR,
            hand_type_name="Pair",
            game_state=state.to_dict(),
        )
    )

    assert breakdown["card_chips"] == 11
    assert score == 42

    handler = PlayPhaseHandler(
        state,
        BalatroGame(),
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        BossBlindManager(),
        DeterministicRNG(1),
    )
    score_after_effects, extra_money, destroyed, _ = handler._apply_card_effects(
        scoring_cards,
        state.deck,
        100,
        "Pair",
    )
    assert score_after_effects == 100
    assert extra_money == 0
    assert destroyed == []
    assert state.get_card_state(0).times_scored == 0


def test_flint_halves_only_base_hand_values_with_balatro_rounding():
    state = UnifiedGameState(active_boss_blind=BossBlindType.THE_FLINT, boss_blind_active=True)
    score, breakdown = UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(
        ScoringContext(
            cards=[Card(Rank.ACE, Suit.SPADES)],
            scoring_cards=[Card(Rank.ACE, Suit.SPADES)],
            hand_type=HandType.HIGH_CARD,
            hand_type_name="High Card",
            game_state=state.to_dict(),
        )
    )

    assert breakdown["base_chips"] == 5
    assert breakdown["base_mult"] == 1
    assert breakdown["blind_modified_base_chips"] == 3
    assert breakdown["blind_modified_base_mult"] == 1
    assert score == 14


def test_psychic_and_cerulean_hide_invalid_play_actions_from_mask():
    psychic = UnifiedGameState(
        phase=Phase.PLAY,
        active_boss_blind=BossBlindType.THE_PSYCHIC,
        boss_blind_active=True,
        deck=[Card(Rank.TWO, Suit.CLUBS)] * 5,
        hand_indexes=list(range(5)),
        selected_cards=[0, 1, 2, 3],
    )
    psychic_mask = build_mvp_action_mask(psychic)
    assert psychic_mask[Action.PLAY_HAND] == 0

    psychic.selected_cards = [0, 1, 2, 3, 4]
    psychic_mask = build_mvp_action_mask(psychic)
    assert psychic_mask[Action.PLAY_HAND] == 1

    cerulean = UnifiedGameState(
        phase=Phase.PLAY,
        active_boss_blind=BossBlindType.THE_CERULEAN,
        boss_blind_active=True,
        deck=[Card(Rank.TWO, Suit.CLUBS)] * 5,
        hand_indexes=list(range(5)),
        selected_cards=[0, 1],
        boss_forced_selected_card=2,
    )
    cerulean_mask = build_mvp_action_mask(cerulean)
    assert cerulean_mask[Action.PLAY_HAND] == 0
    assert cerulean_mask[Action.SELECT_CARD_BASE + 2] == 0


def test_serpent_discard_forces_next_draw_to_three_cards():
    state = UnifiedGameState(
        deck=[Card(Rank.TWO, Suit.CLUBS) for _ in range(8)],
        hand_indexes=[0, 1, 2, 3, 4],
        draw_pile_indexes=[5, 6, 7],
        selected_cards=[0],
        discards_left=3,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_SERPENT,
    )
    game = BalatroGame()
    game.deck = state.deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.round_discards = state.discards_left
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_SERPENT, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )

    reward, terminated, info = handler._handle_discard()

    assert terminated is False
    assert "error" not in info
    assert len(state.hand_indexes) == 3


def test_manacle_hand_size_restores_after_boss_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=3,
        hand_size=7,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_MANACLE,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0, hand_size=7, blind_index=2)
    boss_manager = BossBlindManager()
    boss_manager.activate_boss_blind(BossBlindType.THE_MANACLE, state.to_dict())
    manager = RoundManager(
        state,
        game,
        SimpleNamespace(end_of_round_effects=lambda _: []),
        boss_manager,
    )

    manager.advance_round()

    assert state.hand_size == 8
    assert game.hand_size == 8

from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.boss_blinds import BOSS_BLINDS, BossBlindManager, BossBlindType, select_boss_blind
from balatro_gym.core.cards import Card, Enhancement, Rank, Seal, Suit
from balatro_gym.core.constants import Action, Phase, encode_play_subset_action
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.mvp_contract import build_mvp_action_mask
from balatro_gym.core_utils.blind_scaling import get_blind_amount, get_blind_chips
from balatro_gym.core_utils.phase_handlers.blind_select import BlindSelectHandler
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.phase_handlers.shop_phase import ShopPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.core.jokers import JOKER_LIBRARY
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


def test_flint_does_not_modify_base_values_after_boss_effect_is_disabled():
    state = UnifiedGameState(active_boss_blind=BossBlindType.THE_FLINT, boss_blind_active=False)
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
    assert breakdown["blind_modified_base_chips"] == 5
    assert breakdown["blind_modified_base_mult"] == 1
    assert score == 16


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


def test_eye_hides_repeat_hand_type_actions_from_mask():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        active_boss_blind=BossBlindType.THE_EYE,
        boss_blind_active=True,
        boss_played_hand_types=["Pair"],
        deck=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.CLUBS),
        ],
        hand_indexes=[0, 1, 2],
        selected_cards=[0, 1],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.PLAY_HAND] == 0
    assert mask[encode_play_subset_action((0, 1))] == 0


def test_mouth_hides_new_hand_types_from_mask_after_first_play():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        active_boss_blind=BossBlindType.THE_MOUTH,
        boss_blind_active=True,
        last_hand_played="Pair",
        deck=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.CLUBS),
        ],
        hand_indexes=[0, 1, 2],
        selected_cards=[0],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.PLAY_HAND] == 0
    assert mask[encode_play_subset_action((0,))] == 0


def test_play_phase_action_mask_allows_selling_non_eternal_jokers_during_blind():
    joker = next(j for j in JOKER_LIBRARY if j.name == "Joker")
    state = UnifiedGameState(
        phase=Phase.PLAY,
        jokers=[joker],
        eternal_jokers=[],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.SELL_JOKER_BASE] == 1


def test_disable_boss_blind_restores_water_discards_and_clears_face_down_state():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        discards_left=3,
        face_down_cards=[0],
    )
    game = SimpleNamespace(round_discards=3)
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_WATER, state.to_dict())
    state.active_boss_blind = BossBlindType.THE_WATER
    state.boss_blind_active = True
    state.discards_left = 0
    state.face_down_cards = [0]
    state.get_card_state(0).is_face_down = True

    manager.disable_boss_blind(state, game)

    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.discards_left == 3
    assert game.round_discards == 3
    assert state.face_down_cards == []
    assert state.get_card_state(0).is_face_down is False


def test_selecting_needle_sets_one_hand_and_shared_disable_restores_original_hands():
    state = UnifiedGameState(
        ante=2,
        round=3,
        phase=Phase.BLIND_SELECT,
        hands_left=4,
    )
    game = SimpleNamespace(blinds=[0, 0, 0], blind_index=2, round_hands=4)
    manager = BossBlindManager()
    handler = BlindSelectHandler(state, game, manager, None, DeterministicRNG(1))
    state.pending_boss_blind = BossBlindType.THE_NEEDLE

    reward, terminated, info = handler.step(Action.SELECT_BLIND_BASE + 2)

    assert reward > 0.0
    assert terminated is False
    assert info["boss_blind"] == "The Needle"
    assert state.hands_left == 1
    assert game.round_hands == 1

    manager.disable_boss_blind(state, game)

    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.hands_left == 4
    assert game.round_hands == 4


def test_selecting_amber_acorn_reorders_and_hides_jokers_and_shared_cleanup_keeps_shuffled_order():
    class ReverseShuffleRng:
        def shuffle(self, _stream, items):
            items.reverse()

    jokers = [
        next(j for j in JOKER_LIBRARY if j.name == "Joker"),
        next(j for j in JOKER_LIBRARY if j.name == "Jolly Joker"),
        next(j for j in JOKER_LIBRARY if j.name == "Rocket"),
    ]
    state = UnifiedGameState(
        ante=2,
        round=3,
        phase=Phase.BLIND_SELECT,
        jokers=jokers.copy(),
    )
    state.eternal_jokers = [0]
    state.perishable_counters = {1: 4}
    state.rental_jokers = [2]
    state.rocket_payouts = {2: 7}
    game = SimpleNamespace(blinds=[0, 0, 0], blind_index=2)
    rng = ReverseShuffleRng()
    manager = BossBlindManager(rng)
    handler = BlindSelectHandler(state, game, manager, None, rng)
    state.pending_boss_blind = BossBlindType.THE_AMBER

    reward, terminated, info = handler.step(Action.SELECT_BLIND_BASE + 2)

    assert reward > 0.0
    assert terminated is False
    assert info["boss_blind"] == "Amber Acorn"
    assert [joker.name for joker in state.jokers] == ["Rocket", "Jolly Joker", "Joker"]
    assert state.hidden_joker_indexes == [0, 1, 2]
    assert state.eternal_jokers == [2]
    assert state.perishable_counters == {1: 4}
    assert state.rental_jokers == [0]
    assert state.rocket_payouts == {0: 7}
    assert state.active_boss_blind == BossBlindType.THE_AMBER
    assert state.boss_blind_active is True

    manager.disable_boss_blind(state, game)

    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.hidden_joker_indexes == []
    assert [joker.name for joker in state.jokers] == ["Rocket", "Jolly Joker", "Joker"]


def test_amber_acorn_consumes_exactly_three_boss_shuffle_calls():
    class CountingShuffleRng:
        def __init__(self):
            self.calls = []

        def shuffle(self, stream, items):
            self.calls.append((stream, tuple(items)))
            items.reverse()

    rng = CountingShuffleRng()
    manager = BossBlindManager(rng)

    order = manager._shuffle_amber_jokers(5)

    assert len(rng.calls) == 3
    assert all(stream == "boss_abilities" for stream, _items in rng.calls)
    assert order == [4, 3, 2, 1, 0]


def test_failed_boss_blind_cleans_up_boss_state_before_game_over():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_CERULEAN,
        boss_forced_selected_card=1,
        face_down_cards=[0],
        hidden_joker_indexes=[0],
        hands_left=0,
        discards_left=0,
    )
    state.get_card_state(0).is_face_down = True
    game = SimpleNamespace(round_hands=0, round_discards=0)
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_CERULEAN, state.to_dict())
    round_manager = RoundManager(
        state,
        game,
        CompleteJokerEffects(),
        boss_blind_manager=manager,
        rng=DeterministicRNG(123),
    )

    outcome = round_manager.enter_round_eval()

    assert outcome == "game_over"
    assert state.phase == Phase.GAME_OVER
    assert state.game_over is True
    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.boss_forced_selected_card is None
    assert state.face_down_cards == []
    assert state.hidden_joker_indexes == []
    assert state.get_card_state(0).is_face_down is False


def test_selling_luchador_uses_shared_boss_disable_cleanup():
    luchador = next(j for j in JOKER_LIBRARY if j.name == "Luchador")
    state = UnifiedGameState(
        phase=Phase.SHOP,
        jokers=[luchador],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        draw_pile_indexes=[],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_CERULEAN,
        boss_forced_selected_card=0,
        selected_cards=[0],
    )
    game = SimpleNamespace(round_discards=3, round_hands=4, hand_indexes=state.hand_indexes.copy(), draw_pile_indexes=[])
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_CERULEAN, state.to_dict())
    handler = ShopPhaseHandler(state, DeterministicRNG(123), boss_blind_manager=manager, game=game)

    reward, terminated, info = handler._handle_sell_joker(Action.SELL_JOKER_BASE)

    assert reward >= 0.0
    assert terminated is False
    assert info["joker_sold"] == "Luchador"
    assert info["luchador_effect"] == "Boss blind disabled this round"
    assert state.boss_blind_active is False
    assert state.active_boss_blind == BossBlindType.THE_CERULEAN
    assert state.boss_forced_selected_card is None
    assert manager.active_blind is None


def test_selling_luchador_during_play_disables_active_boss_blind():
    luchador = next(j for j in JOKER_LIBRARY if j.name == "Luchador")
    state = UnifiedGameState(
        phase=Phase.PLAY,
        jokers=[luchador],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_CERULEAN,
        boss_forced_selected_card=0,
    )
    game = BalatroGame()
    game.deck = state.deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_discards = 3
    game.round_hands = 4
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_CERULEAN, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.SELL_JOKER_BASE)

    assert reward >= 0.0
    assert terminated is False
    assert info["joker_sold"] == "Luchador"
    assert info["luchador_effect"] == "Boss blind disabled this round"
    assert state.boss_blind_active is False
    assert state.active_boss_blind == BossBlindType.THE_CERULEAN
    assert state.boss_forced_selected_card is None
    assert manager.active_blind is None


def test_selling_any_joker_under_verdant_uses_shared_boss_disable_cleanup():
    joker = next(j for j in JOKER_LIBRARY if j.name == "Jolly Joker")
    state = UnifiedGameState(
        phase=Phase.SHOP,
        jokers=[joker],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_VERDANT,
    )
    state.get_card_state(0).is_debuffed = True
    game = SimpleNamespace(round_discards=3, round_hands=4, hand_indexes=[], draw_pile_indexes=[])
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_VERDANT, state.to_dict())
    handler = ShopPhaseHandler(state, DeterministicRNG(123), boss_blind_manager=manager, game=game)

    reward, terminated, info = handler._handle_sell_joker(Action.SELL_JOKER_BASE)

    assert reward >= 0.0
    assert terminated is False
    assert info["joker_sold"] == "Jolly Joker"
    assert state.boss_blind_active is False
    assert state.active_boss_blind == BossBlindType.THE_VERDANT
    assert state.get_card_state(0).is_debuffed is False


def test_selling_any_joker_during_play_under_verdant_disables_active_boss_blind():
    joker = next(j for j in JOKER_LIBRARY if j.name == "Jolly Joker")
    state = UnifiedGameState(
        phase=Phase.PLAY,
        jokers=[joker],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_VERDANT,
    )
    state.get_card_state(0).is_debuffed = True
    game = BalatroGame()
    game.deck = state.deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_discards = 3
    game.round_hands = 4
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_VERDANT, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.SELL_JOKER_BASE)

    assert reward >= 0.0
    assert terminated is False
    assert info["joker_sold"] == "Jolly Joker"
    assert state.boss_blind_active is False
    assert state.active_boss_blind == BossBlindType.THE_VERDANT
    assert state.get_card_state(0).is_debuffed is False


def test_cerulean_discard_redraw_rerolls_forced_card_even_if_previous_card_stays_in_hand():
    class SequenceChoiceRng:
        def __init__(self, choices):
            self._choices = iter(choices)

        def choice(self, _stream, _sequence):
            return next(self._choices)

    deck = [
        Card(Rank.TWO, Suit.CLUBS),
        Card(Rank.THREE, Suit.DIAMONDS),
        Card(Rank.FOUR, Suit.HEARTS),
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.SIX, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.DIAMONDS),
    ]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0, 1, 2, 3, 4],
        draw_pile_indexes=[5],
        selected_cards=[0],
        discards_left=3,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_CERULEAN,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = []
    game.round_discards = state.discards_left
    manager = BossBlindManager(SequenceChoiceRng([2, 4]))
    manager.activate_boss_blind(BossBlindType.THE_CERULEAN, state.to_dict())
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

    handler.apply_boss_blind_to_hand()
    assert state.boss_forced_selected_card == 2
    assert state.selected_cards == [2]

    state.selected_cards = [0]
    reward, terminated, info = handler._handle_discard()

    assert reward >= 0.2
    assert terminated is False
    assert "error" not in info
    assert 2 in state.hand_indexes
    assert state.boss_forced_selected_card == 4
    assert state.selected_cards == [4]
    assert manager.blind_state["forced_card_ref"] == id(state.deck[state.hand_indexes[4]])


def test_serpent_discard_draws_three_more_cards_instead_of_refilling_to_hand_size():
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
    assert len(state.hand_indexes) == 7
    assert state.draw_pile_indexes == []


def test_serpent_play_draws_three_more_cards_instead_of_refilling_to_hand_size():
    deck = [Card(Rank.TWO, Suit.CLUBS) for _ in range(8)]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0, 1, 2, 3, 4],
        draw_pile_indexes=[5, 6, 7],
        selected_cards=[0],
        hands_left=3,
        discards_left=3,
        chips_needed=500,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_SERPENT,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
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
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})
    handler._score_hand = lambda _cards, _hand_type, _hand_type_name: (25, {})

    reward, terminated, info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert info["cards_played"] == 1
    assert len(state.hand_indexes) == 7
    assert state.draw_pile_indexes == []
    assert state.force_draw_count is None


def test_serpent_shared_draw_rule_applies_to_direct_draw_after_first_scored_hand():
    deck = [Card(Rank.TWO, Suit.CLUBS) for _ in range(8)]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0, 1, 2, 3],
        draw_pile_indexes=[4, 5, 6, 7],
        hands_left=3,
        discards_left=3,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_SERPENT,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_SERPENT, state.to_dict())
    manager.blind_state["hands_played"] = 1
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

    handler._draw_new_hand()

    assert len(state.hand_indexes) == 7
    assert state.draw_pile_indexes == [7]
    assert game.serpent_active is True
    assert game.serpent_post_first_action_draw is True


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


def test_disabling_manacle_mid_round_restores_hand_size_and_draws_one_card():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_size=7,
        hand_indexes=[0, 1, 2, 3, 4, 5, 6],
        draw_pile_indexes=[7],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_MANACLE,
    )
    game = SimpleNamespace(hand_size=7, hand_indexes=state.hand_indexes.copy(), draw_pile_indexes=state.draw_pile_indexes.copy())
    boss_manager = BossBlindManager()
    boss_manager.activate_boss_blind(BossBlindType.THE_MANACLE, state.to_dict())

    boss_manager.disable_boss_blind(state, game)

    assert state.hand_size == 8
    assert game.hand_size == 8
    assert state.hand_indexes == list(range(8))
    assert state.draw_pile_indexes == []


def test_arm_reduces_played_hand_level_before_scoring_but_not_below_one():
    deck = [Card(Rank.ACE, Suit.SPADES)]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        discards_left=3,
        chips_needed=500,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_ARM,
        hand_levels={HandType.HIGH_CARD: 3},
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    engine = ScoreEngine()
    engine.set_hand_level(HandType.HIGH_CARD, 3)
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_ARM, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    def _score_hand(_cards, _hand_type, _hand_type_name):
        assert engine.get_hand_level(HandType.HIGH_CARD) == 2
        assert state.hand_levels[HandType.HIGH_CARD] == 2
        return 25, {}

    handler._score_hand = _score_hand

    reward, terminated, _info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert engine.get_hand_level(HandType.HIGH_CARD) == 2
    assert state.hand_levels[HandType.HIGH_CARD] == 2

    state.phase = Phase.PLAY
    state.selected_cards = [0]
    state.hand_indexes = [0]
    state.hands_left = 2
    engine.set_hand_level(HandType.HIGH_CARD, 1)
    state.hand_levels[HandType.HIGH_CARD] = 1

    def _score_hand_level_one(_cards, _hand_type, _hand_type_name):
        assert engine.get_hand_level(HandType.HIGH_CARD) == 1
        return 10, {}

    handler._score_hand = _score_hand_level_one
    reward, terminated, _info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert engine.get_hand_level(HandType.HIGH_CARD) == 1
    assert state.hand_levels[HandType.HIGH_CARD] == 1


def test_disable_boss_blind_restores_wall_and_violet_chip_thresholds():
    for blind_type, expected in (
        (BossBlindType.THE_WALL, 400),
        (BossBlindType.THE_VIOLET, 700),
    ):
        state = UnifiedGameState(
            phase=Phase.PLAY,
            chips_needed=expected,
            boss_blind_active=True,
            active_boss_blind=blind_type,
        )
        game = SimpleNamespace(blinds=[0, 0, expected * 2], blind_index=2)
        manager = BossBlindManager()
        manager.activate_boss_blind(blind_type, state.to_dict())
        manager.blind_state["base_chips"] = expected
        state.chips_needed = expected * 2

        manager.disable_boss_blind(state, game)

        assert state.chips_needed == expected
        assert game.blinds[2] == expected


def test_hook_discards_from_remaining_hand_before_scoring_and_redraw():
    deck = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS),
        Card(Rank.EIGHT, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SIX, Suit.SPADES),
        Card(Rank.FIVE, Suit.HEARTS),
    ]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=list(range(8)),
        draw_pile_indexes=[8, 9],
        selected_cards=[0],
        hands_left=2,
        discards_left=3,
        chips_needed=500,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    rng = DeterministicRNG(123)
    boss_manager = BossBlindManager(rng)
    boss_manager.activate_boss_blind(BossBlindType.THE_HOOK, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        boss_manager,
        rng,
    )
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})
    handler._score_hand = lambda _cards, _hand_type, _hand_type_name: (50, {})

    reward, terminated, info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert info["final_score"] == 50
    assert info["cards_played"] == 1
    assert state.round_chips_scored == 50
    assert state.hands_left == 1
    assert state.selected_cards == []
    assert state.hand_indexes == [2, 3, 4, 6, 7, 8, 9]
    assert state.discard_pile_indexes == [1, 5, 0]
    assert state.draw_pile_indexes == []
    assert [entry for entry in rng.history if entry[0] == "boss_abilities"] == [
        ("boss_abilities", "sample", (4, 0))
    ]


def test_hook_does_not_prepare_or_discard_next_hand_when_play_clears_blind():
    deck = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS),
        Card(Rank.EIGHT, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SIX, Suit.SPADES),
    ]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=list(range(8)),
        draw_pile_indexes=[8],
        selected_cards=[0],
        hands_left=1,
        discards_left=3,
        chips_needed=50,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = state.draw_pile_indexes.copy()
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    rng = DeterministicRNG(123)
    boss_manager = BossBlindManager(rng)
    boss_manager.activate_boss_blind(BossBlindType.THE_HOOK, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        boss_manager,
        rng,
    )
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})
    handler._score_hand = lambda _cards, _hand_type, _hand_type_name: (50, {})

    reward, terminated, info = handler._handle_play_hand()

    assert reward == handler.BLIND_CLEAR_OUTCOME_BONUS
    assert terminated is False
    assert info["beat_blind"] is True
    assert info["transition_to"] == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.hand_indexes == []
    assert state.discard_pile_indexes == []
    assert state.draw_pile_indexes == list(range(len(deck)))
    assert [entry for entry in rng.history if entry[0] == "boss_abilities"] == [
        ("boss_abilities", "sample", (4, 0))
    ]


def test_fish_faces_only_the_next_draw_after_press_play():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
    ]
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_FISH, {})

    assert manager.on_hand_drawn(hand_cards, {})["face_down_cards"] == []

    manager.on_press_play(hand_cards, [0], {})
    assert manager.on_hand_drawn(hand_cards, {})["face_down_cards"] == [0, 1, 2, 3]
    assert manager.on_hand_drawn(hand_cards, {})["face_down_cards"] == []


def test_house_faces_only_while_no_hands_or_discards_have_been_used():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
    ]
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_HOUSE, {})

    first_draw = manager.on_hand_drawn(hand_cards, {"discards_used_this_round": 0})
    after_discard = manager.on_hand_drawn(hand_cards, {"discards_used_this_round": 1})

    assert first_draw["face_down_cards"] == [0, 1, 2]
    assert after_discard["face_down_cards"] == []


def test_mark_faces_only_face_cards_on_each_draw():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.TEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
    ]
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_MARK, {})

    assert manager.on_hand_drawn(hand_cards, {})["face_down_cards"] == [1, 3]


def test_wheel_uses_normal_probability_modifiers_from_active_jokers():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS),
    ]
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_WHEEL, {})

    class SequenceFloatRng:
        def __init__(self, values):
            self._values = iter(values)

        def get_float(self, _stream):
            return next(self._values)

    manager.rng = SequenceFloatRng([0.20, 0.30, 0.10, 0.24, 0.60, 0.80])
    base_effects = manager.on_hand_drawn(hand_cards, {"jokers": []})

    manager.rng = SequenceFloatRng([0.20, 0.30, 0.10, 0.24, 0.60, 0.80])
    boosted_effects = manager.on_hand_drawn(
        hand_cards,
        {"jokers": [{"name": "Oops! All 6s", "disabled": False}]},
    )

    manager.rng = SequenceFloatRng([0.20, 0.30, 0.10, 0.24, 0.60, 0.80])
    disabled_effects = manager.on_hand_drawn(
        hand_cards,
        {"jokers": [{"name": "Oops! All 6s", "disabled": True}]},
    )

    assert base_effects["face_down_cards"] == [2]
    assert boosted_effects["face_down_cards"] == [0, 2, 3]
    assert disabled_effects["face_down_cards"] == [2]


def test_crimson_disables_on_first_draw_and_again_on_the_next_draw_after_press_play():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
    ]
    rng = DeterministicRNG(123)
    manager = BossBlindManager(rng)
    manager.activate_boss_blind(BossBlindType.THE_CRIMSON, {"jokers": ["a", "b", "c"]})

    assert manager.on_hand_drawn(hand_cards, {"jokers": ["a", "b", "c"]})["disabled_joker_indexes"] in ([0], [1], [2])
    assert manager.on_hand_drawn(hand_cards, {"jokers": ["a", "b", "c"]}).get("disabled_joker_indexes", []) == []

    manager.on_press_play(hand_cards, [0], {"jokers": ["a", "b", "c"]})
    assert manager.on_hand_drawn(hand_cards, {"jokers": ["a", "b", "c"]})["disabled_joker_indexes"] in ([0], [1], [2])
    assert manager.on_hand_drawn(hand_cards, {"jokers": ["a", "b", "c"]}).get("disabled_joker_indexes", []) == []


def test_crimson_next_disabled_joker_excludes_currently_disabled_joker_when_multiple_exist():
    class FirstChoiceRng:
        def choice(self, _stream, sequence):
            return sequence[0]

    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
    ]
    manager = BossBlindManager(FirstChoiceRng())
    manager.activate_boss_blind(
        BossBlindType.THE_CRIMSON,
        {"jokers": [{"name": "a", "disabled": False}, {"name": "b", "disabled": True}, {"name": "c", "disabled": False}]},
    )

    manager.on_press_play(hand_cards, [0], {"jokers": ["a", "b", "c"]})
    effects = manager.on_hand_drawn(
        hand_cards,
        {"jokers": [{"name": "a", "disabled": False}, {"name": "b", "disabled": True}, {"name": "c", "disabled": False}]},
    )

    assert effects["disabled_joker_indexes"] == [0]


def test_disabled_joker_slots_remain_in_state_dict_without_renumbering():
    jokers = [
        next(j for j in JOKER_LIBRARY if j.name == "Joker"),
        next(j for j in JOKER_LIBRARY if j.name == "Jolly Joker"),
        next(j for j in JOKER_LIBRARY if j.name == "Rocket"),
    ]
    state = UnifiedGameState(jokers=jokers, boss_disabled_joker_indexes=[1])

    joker_state = state.to_dict()["jokers"]

    assert [joker["name"] for joker in joker_state] == ["Joker", "Jolly Joker", "Rocket"]
    assert [joker["disabled"] for joker in joker_state] == [False, True, False]


def test_cerulean_keeps_forcing_same_card_until_it_leaves_hand():
    cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
    ]
    rng = DeterministicRNG(123)
    manager = BossBlindManager(rng)
    manager.activate_boss_blind(BossBlindType.THE_CERULEAN, {})

    first = manager.on_hand_drawn(cards, {})
    forced_card = cards[first["forced_selected_card"]]

    rotated = [cards[2], cards[0], cards[1]]
    second = manager.on_hand_drawn(rotated, {})

    assert rotated[second["forced_selected_card"]] is forced_card


def test_tooth_reduces_money_before_scoring_context_is_built():
    deck = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
    ]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=list(range(3)),
        selected_cards=[0, 1, 2],
        hands_left=2,
        discards_left=3,
        chips_needed=500,
        money=10,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_TOOTH,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_TOOTH, state.to_dict())
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
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    def _score_hand(_cards, _hand_type, _hand_type_name):
        assert state.money == 7
        return 25, {}

    handler._score_hand = _score_hand

    reward, terminated, _info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert state.money == 7


def test_ox_zeroes_money_before_scoring_for_most_played_hand():
    deck = [Card(Rank.ACE, Suit.SPADES)]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        discards_left=3,
        chips_needed=500,
        money=12,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_OX,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    engine = ScoreEngine()
    engine.hand_play_counts[HandType.HIGH_CARD] = 3
    engine.hand_play_counts[HandType.ONE_PAIR] = 1
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_OX, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    def _score_hand(_cards, _hand_type, _hand_type_name):
        assert state.money == 0
        return 25, {}

    handler._score_hand = _score_hand

    reward, terminated, _info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert state.money == 0
    assert state.boss_round_ox_target_hand == HandType.HIGH_CARD


def test_ox_tie_targets_only_lowest_order_most_played_hand():
    state = UnifiedGameState(
        money=12,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_OX,
    )
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_OX, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        BalatroGame(),
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )

    handler._apply_boss_blind_before_scoring(
        HandType.ONE_PAIR,
        "Pair",
        {
            HandType.HIGH_CARD: 3,
            HandType.ONE_PAIR: 3,
        },
    )

    assert state.money == 12


def test_ox_defaults_to_high_card_before_any_hands_have_been_played():
    deck = [Card(Rank.ACE, Suit.SPADES)]
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=deck,
        hand_indexes=[0],
        selected_cards=[0],
        hands_left=2,
        discards_left=3,
        chips_needed=500,
        money=12,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_OX,
    )
    game = BalatroGame()
    game.deck = deck
    game.hand_indexes = state.hand_indexes.copy()
    game.draw_pile_indexes = []
    game.discard_pile_indexes = []
    game.round_hands = state.hands_left
    game.round_discards = state.discards_left
    engine = ScoreEngine()
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_OX, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_kwargs: {"total_reward": 0.0})

    def _score_hand(_cards, _hand_type, _hand_type_name):
        assert state.money == 0
        return 25, {}

    handler._score_hand = _score_hand
    handler._identify_poker_hand = lambda _cards: (HandType.HIGH_CARD, "High Card")

    reward, terminated, _info = handler._handle_play_hand()

    assert reward == 0.0
    assert terminated is False
    assert state.money == 0
    assert state.boss_round_ox_target_hand == HandType.HIGH_CARD


def test_ox_target_stays_fixed_for_boss_round_after_first_snapshot():
    state = UnifiedGameState(
        money=12,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_OX,
    )
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_OX, state.to_dict())
    handler = PlayPhaseHandler(
        state,
        BalatroGame(),
        ScoreEngine(),
        UnifiedScorer(ScoreEngine(), CompleteJokerEffects()),
        CompleteJokerEffects(),
        SimpleNamespace(),
        manager,
        DeterministicRNG(1),
    )

    handler._apply_boss_blind_before_scoring(
        HandType.HIGH_CARD,
        "High Card",
        {
            HandType.HIGH_CARD: 3,
            HandType.ONE_PAIR: 2,
        },
    )

    assert state.money == 0
    assert state.boss_round_ox_target_hand == HandType.HIGH_CARD

    state.money = 12
    handler._apply_boss_blind_before_scoring(
        HandType.ONE_PAIR,
        "Pair",
        {
            HandType.HIGH_CARD: 3,
            HandType.ONE_PAIR: 4,
        },
    )

    assert state.money == 12
    assert state.boss_round_ox_target_hand == HandType.HIGH_CARD


def test_disabling_boss_blind_clears_cached_ox_target_state():
    state = UnifiedGameState(
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_OX,
        boss_round_ox_target_hand=HandType.HIGH_CARD,
    )
    manager = BossBlindManager()
    manager.activate_boss_blind(BossBlindType.THE_OX, state.to_dict())

    manager.disable_boss_blind(state, BalatroGame())

    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.boss_round_ox_target_hand is None

from types import SimpleNamespace

from balatro_gym.core.cards import Card, Enhancement, Rank, Seal, Suit
from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import CardState, UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine
from balatro_gym.scoring.unified_scoring import ScoringContext, UnifiedScorer


def _make_play_handler(state):
    scorer = UnifiedScorer(ScoreEngine(), CompleteJokerEffects())
    return PlayPhaseHandler(
        state,
        game=SimpleNamespace(),
        engine=SimpleNamespace(),
        unified_scorer=scorer,
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=SimpleNamespace(),
        rng=DeterministicRNG(123),
    )


def _score_with_jokers(jokers):
    cards = [Card(Rank.ACE, Suit.SPADES)]
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": jokers},
    )

    return UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(context)


def test_unified_scorer_applies_joker_dicts_from_unified_game_state():
    state = UnifiedGameState(
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        jokers=[JokerInfo(1, "Joker", 2, "+4 Mult")],
    )
    cards = state.to_dict()["hand"]
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state=state.to_dict(),
    )

    score, breakdown = UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(context)

    assert score == 80
    assert breakdown["joker_mult"] == 4
    assert breakdown["effects_applied"] == ["Joker: +0c +4m x1.0"]


def test_play_phase_pair_scores_pair_cards_not_kickers():
    selected_cards = [
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.CLUBS),
    ]
    state = UnifiedGameState(deck=selected_cards, hand_indexes=list(range(5)))
    handler = _make_play_handler(state)

    score, breakdown = handler._score_hand(
        selected_cards=selected_cards,
        hand_type=HandType.ONE_PAIR,
        hand_type_name="Pair",
    )

    assert breakdown["card_chips"] == 14
    assert score == 48


def test_play_phase_high_card_scores_only_highest_card():
    selected_cards = [
        Card(Rank.TWO, Suit.CLUBS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.CLUBS),
        Card(Rank.NINE, Suit.HEARTS),
    ]
    state = UnifiedGameState(deck=selected_cards, hand_indexes=list(range(5)))
    handler = _make_play_handler(state)

    score, breakdown = handler._score_hand(
        selected_cards=selected_cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
    )

    assert breakdown["card_chips"] == 11
    assert score == 16


def test_play_phase_splash_scores_every_selected_card():
    selected_cards = [
        Card(Rank.TWO, Suit.CLUBS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.DIAMONDS),
    ]
    state = UnifiedGameState(
        deck=selected_cards,
        hand_indexes=list(range(3)),
        jokers=[JokerInfo(52, "Splash", 3, "Every card scores")],
    )
    handler = _make_play_handler(state)

    scoring_cards = handler._get_scoring_cards(selected_cards, HandType.HIGH_CARD)

    assert scoring_cards == selected_cards


def test_play_phase_stone_scores_but_does_not_make_pair():
    selected_game_cards = [
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.SPADES),
    ]
    state = UnifiedGameState(deck=selected_game_cards, hand_indexes=list(range(3)))
    state.get_card_state(0).enhancement = Enhancement.STONE
    selected_cards = [
        CardAdapter.to_scoring_format(card, i, state)
        for i, card in enumerate(selected_game_cards)
    ]
    handler = _make_play_handler(state)
    classification_cards = handler._get_poker_classification_cards(
        selected_cards,
        selected_game_cards,
    )

    hand_type, _ = BalatroGame()._classify_hand(classification_cards)
    score, breakdown = handler._score_hand(
        selected_cards=selected_cards,
        hand_type=hand_type,
        hand_type_name="High Card",
    )

    assert hand_type == HandType.HIGH_CARD
    assert handler._get_scoring_cards(selected_cards, hand_type) == [
        selected_cards[0],
        selected_cards[2],
    ]
    assert breakdown["card_chips"] == 61
    assert score == 66


def test_play_phase_card_effects_do_not_trigger_for_pair_kickers():
    selected_cards = [
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.CLUBS),
    ]
    state = UnifiedGameState(deck=selected_cards, hand_indexes=list(range(5)))
    state.card_states = {
        i: CardState(i, seal=Seal.GOLD if i == 2 else Seal.NONE)
        for i in range(5)
    }
    state.card_states[3].enhancement = Enhancement.GLASS
    handler = _make_play_handler(state)
    scoring_cards = [
        CardAdapter.to_scoring_format(card, i, state)
        for i, card in enumerate(selected_cards[:2])
    ]

    final_score, extra_money, cards_to_destroy, consumables_created = handler._apply_card_effects(
        scoring_cards,
        selected_cards[:2],
        48,
        "Pair",
    )

    assert final_score == 48
    assert extra_money == 0
    assert cards_to_destroy == []
    assert consumables_created == []
    assert [state.card_states[i].times_scored for i in range(5)] == [1, 1, 0, 0, 0]


def test_play_phase_card_effects_persist_missing_card_state_updates():
    selected_cards = [
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.HEARTS),
    ]
    state = UnifiedGameState(deck=selected_cards, hand_indexes=list(range(2)))
    handler = _make_play_handler(state)
    scoring_cards = [
        CardAdapter.to_scoring_format(card, i, state)
        for i, card in enumerate(selected_cards)
    ]

    handler._track_played_cards(scoring_cards)
    handler._apply_card_effects(scoring_cards, selected_cards, 48, "Pair")

    assert [state.card_states[i].times_played for i in range(2)] == [1, 1]
    assert [state.card_states[i].times_scored for i in range(2)] == [1, 1]


def test_unified_scorer_joker_representations_score_equivalently():
    string_score, _ = _score_with_jokers(["Joker"])
    dict_score, _ = _score_with_jokers([{"name": "Joker", "id": 1}])
    object_score, _ = _score_with_jokers([SimpleNamespace(name="Joker")])

    assert dict_score == string_score
    assert object_score == string_score


def test_play_phase_score_hand_applies_serialized_state_jokers():
    state = UnifiedGameState(
        deck=[Card(Rank.ACE, Suit.SPADES)],
        hand_indexes=[0],
        jokers=[JokerInfo(1, "Joker", 2, "+4 Mult")],
    )
    scorer = UnifiedScorer(ScoreEngine(), CompleteJokerEffects())
    handler = PlayPhaseHandler(
        state,
        game=SimpleNamespace(),
        engine=SimpleNamespace(),
        unified_scorer=scorer,
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=SimpleNamespace(),
        rng=DeterministicRNG(123),
    )

    score, breakdown = handler._score_hand(
        selected_cards=[Card(Rank.ACE, Suit.SPADES)],
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
    )

    assert score == 80
    assert breakdown["joker_mult"] == 4

from types import SimpleNamespace

from balatro_gym.core.cards import Card, Rank, Suit
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine
from balatro_gym.scoring.unified_scoring import ScoringContext, UnifiedScorer


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

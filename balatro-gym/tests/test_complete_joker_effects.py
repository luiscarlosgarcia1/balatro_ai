from types import SimpleNamespace

import pytest

from balatro_gym.core.cards import Card, Rank, Suit
from balatro_gym.core.jokers import JOKER_LIBRARY
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine
from balatro_gym.scoring.unified_scoring import ScoringContext, UnifiedScorer


def _joker(name):
    return SimpleNamespace(name=name)


def _card(rank, suit="Spades"):
    return SimpleNamespace(rank=rank, suit=suit)


def _supported_joker_names(engine):
    supported = set()

    for method_name in ("supported_jokers", "get_supported_jokers", "supported_joker_names"):
        method = getattr(engine, method_name, None)
        if callable(method):
            supported.update(method())

    for attr_name in (
        "joker_metadata",
        "metadata",
        "JOKER_METADATA",
        "SUPPORTED_JOKERS",
        "supported_jokers",
        "supported_joker_names",
    ):
        value = getattr(engine, attr_name, None)
        if isinstance(value, dict):
            supported.update(value.keys())
        elif isinstance(value, (set, list, tuple)):
            supported.update(value)

    return {name for name in supported if isinstance(name, str)}


def _score_joker(engine, name, game_state=None):
    return engine.apply_joker_effect(
        _joker(name),
        {"phase": "scoring", "scoring_cards": [_card(14)], "cards": [_card(14)]},
        game_state or {"jokers": [_joker(name)], "hands_left": 3, "discards_left": 3},
    )


def test_complete_joker_effects_metadata_reports_unimplemented_jokers():
    engine = CompleteJokerEffects()
    library_names = {joker.name for joker in JOKER_LIBRARY}

    assert len(library_names) == 150
    assert _supported_joker_names(engine) < library_names
    assert "Blueprint" in engine.unsupported_joker_names()
    assert "Joker" in _supported_joker_names(engine)


def test_popcorn_decays_at_end_of_round_and_eventually_destroys():
    engine = CompleteJokerEffects()
    game_state = {"jokers": [_joker("Popcorn")]}

    assert _score_joker(engine, "Popcorn", game_state)["mult"] == 20

    for expected_mult in (16, 12, 8, 4):
        effects = engine.end_of_round_effects(game_state)
        assert {"destroy_joker": "Popcorn"} not in effects
        assert _score_joker(engine, "Popcorn", game_state)["mult"] == expected_mult

    effects = engine.end_of_round_effects(game_state)

    assert any(effect.get("destroy_joker") == "Popcorn" for effect in effects)
    assert any(effect.get("destroy_joker_index") == 0 for effect in effects)


def test_ice_cream_decays_after_each_scored_hand():
    engine = CompleteJokerEffects()
    game_state = {"jokers": [_joker("Ice Cream")]}

    first = _score_joker(engine, "Ice Cream", game_state)
    second = _score_joker(engine, "Ice Cream", game_state)
    third = _score_joker(engine, "Ice Cream", game_state)

    assert first["chips"] == 100
    assert second["chips"] == 95
    assert third["chips"] == 90


def test_throwback_skip_blind_state_increases_scoring_x_mult():
    engine = CompleteJokerEffects()
    game_state = {"jokers": [_joker("Throwback")]}

    assert _score_joker(engine, "Throwback", game_state) in (None, {"x_mult": 1})

    engine.apply_joker_effect(_joker("Throwback"), {"phase": "skip_blind"}, game_state)
    assert _score_joker(engine, "Throwback", game_state)["x_mult"] == pytest.approx(1.25)

    engine.apply_joker_effect(_joker("Throwback"), {"phase": "skip_blind"}, game_state)
    assert _score_joker(engine, "Throwback", game_state)["x_mult"] == pytest.approx(1.5)


def test_mail_in_rebate_pays_for_discarded_matching_rank():
    engine = CompleteJokerEffects()
    context = {
        "phase": "discard",
        "discarded_cards": [_card(7), _card(7), _card(9)],
        "mail_in_rebate_rank": 7,
        "mail_in_rebate_target_rank": 7,
        "rebate_rank": 7,
    }
    game_state = {
        "mail_in_rebate_rank": 7,
        "mail_in_rebate_target_rank": 7,
        "rebate_rank": 7,
    }

    effect = engine.apply_joker_effect(_joker("Mail-In Rebate"), context, game_state)

    assert effect == {"money": 10}


def test_hanging_chad_uses_indexed_state_and_retriggers_first_scoring_card():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": [{"name": "Hanging Chad"}]},
    )

    score, breakdown = UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(context)

    assert score == 38
    assert breakdown["card_chips"] == 33
    assert breakdown["card_retriggers"] == 2


def test_once_per_hand_joker_state_resets_between_scored_hands():
    cards = [Card(Rank.KING, Suit.SPADES)]
    scorer = UnifiedScorer(ScoreEngine(), CompleteJokerEffects())
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": [{"name": "Photograph"}]},
    )

    first_score, _ = scorer.score_hand(context)
    second_score, _ = scorer.score_hand(context)

    assert first_score == 30
    assert second_score == 30

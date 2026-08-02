from types import SimpleNamespace

from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.consumables import (
    Edition as ConsumableEdition,
    Enhancement as ConsumableEnhancement,
    Seal as ConsumableSeal,
)
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import CardState, UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects
from balatro_gym.scoring.scoring_engine import HandType, ScoreEngine
from balatro_gym.scoring.unified_scoring import LUA_SCORING_STAGES, ScoringContext, UnifiedScorer


class RecordingJokerEffects:
    def __init__(self, effects_by_phase=None):
        self.effects_by_phase = effects_by_phase or {}
        self.calls = []

    def reset_scoring_hand_state(self, game_state):
        self.calls.append(("reset", None))

    def apply_joker_effect(self, joker, context, game_state):
        phase = context["phase"]
        self.calls.append((phase, getattr(joker, "name", None)))
        return self.effects_by_phase.get(phase)


class ScriptedJokerEffects:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def reset_scoring_hand_state(self, game_state):
        self.calls.append(("reset", None, None, None))

    def apply_joker_effect(self, joker, context, game_state):
        phase = context["phase"]
        card = context.get("card") or context.get("other_card")
        card_index = getattr(getattr(card, "card_state", None), "card_index", None)
        times_scored = getattr(getattr(card, "card_state", None), "times_scored", None)
        self.calls.append((phase, getattr(joker, "name", None), card_index, times_scored))
        effect = self.script(phase, joker, context, game_state)
        if effect and isinstance(effect, dict) and effect.get("message"):
            game_state.setdefault("_test_trace", []).append(effect["message"])
        return effect


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


def _score_hand(cards, scoring_cards, hand_type, hand_type_name, game_state):
    context = ScoringContext(
        cards=cards,
        scoring_cards=scoring_cards,
        hand_type=hand_type,
        hand_type_name=hand_type_name,
        game_state=game_state,
    )

    return UnifiedScorer(ScoreEngine(), CompleteJokerEffects()).score_hand(context)


def _score_hand_with_effects(cards, scoring_cards, hand_type, hand_type_name, game_state, effects):
    context = ScoringContext(
        cards=cards,
        scoring_cards=scoring_cards,
        hand_type=hand_type,
        hand_type_name=hand_type_name,
        game_state=game_state,
    )

    return UnifiedScorer(ScoreEngine(), effects).score_hand(context)


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
    assert breakdown["effects_applied"] == ["Joker (scoring): +0c +4m x1.0"]


def test_unified_scorer_invokes_lua_scoring_phases_in_order():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    effects = RecordingJokerEffects()
    context = ScoringContext(
        cards=cards,
        scoring_cards=cards,
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": ["Recorder"]},
    )

    _, breakdown = UnifiedScorer(ScoreEngine(), effects).score_hand(context)

    assert breakdown["stage_order"] == list(LUA_SCORING_STAGES)
    assert effects.calls == [
        ("reset", None),
        ("before_scoring", "Recorder"),
        ("individual_scoring", "Recorder"),
        ("held_card", "Recorder"),
        ("joker_edition_chip_mult", "Recorder"),
        ("scoring", "Recorder"),
        ("joker_on_joker", "Recorder"),
        ("joker_edition_x_mult", "Recorder"),
        ("final_scoring_step", "Recorder"),
        ("destroying_card", "Recorder"),
        ("after_hand", "Recorder"),
    ]


def test_unified_scorer_applies_before_effects_before_blind_modification():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    effects = RecordingJokerEffects({"before_scoring": {"mult": 3}})
    blind_calls = []

    def halve_base(chips, mult, cards, hand_type_name):
        blind_calls.append((chips, mult, hand_type_name))
        return int(chips * 0.5 + 0.5), max(1, int(mult * 0.5 + 0.5))

    context = ScoringContext(
        cards=cards,
        scoring_cards=[],
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": ["Recorder"]},
        blind_modifier=halve_base,
    )

    score, breakdown = UnifiedScorer(ScoreEngine(), effects).score_hand(context)

    assert blind_calls == [(5, 1, "High Card")]
    assert breakdown["blind_modified_base_chips"] == 3
    assert breakdown["blind_modified_base_mult"] == 1
    assert breakdown["final_chips"] == 3
    assert breakdown["final_mult"] == 4
    assert score == 12


def test_unified_scorer_does_not_apply_after_hand_effects_to_current_score():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    effects = RecordingJokerEffects({"after_hand": {"mult": 99, "money": 2}})
    context = ScoringContext(
        cards=cards,
        scoring_cards=[],
        hand_type=HandType.HIGH_CARD,
        hand_type_name="High Card",
        game_state={"jokers": ["Recorder"], "money": 0},
    )

    score, breakdown = UnifiedScorer(ScoreEngine(), effects).score_hand(context)

    assert score == 5
    assert breakdown["final_mult"] == 1
    assert breakdown["joker_mult"] == 99
    assert breakdown["money_gained"] == 2


def test_unified_scorer_applies_held_steel_in_held_card_stage():
    cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)]
    state = UnifiedGameState(deck=cards, hand_indexes=[0, 1], selected_cards=[0])
    state.get_card_state(1).enhancement = Enhancement.STEEL
    scoring_card = CardAdapter.to_scoring_format(cards[0], 0, state)
    held_card = CardAdapter.to_scoring_format(cards[1], 1, state)

    score, breakdown = _score_hand(
        [scoring_card],
        [scoring_card],
        HandType.HIGH_CARD,
        "High Card",
        {"jokers": [], "held_cards": [held_card]},
    )

    assert score == 24
    assert "Held card (Steel): x1.5" in breakdown["effects_applied"]


def test_unified_scorer_snapshots_played_card_repetitions_and_resolves_repeats_before_next_card():
    cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)]
    state = UnifiedGameState(deck=cards, hand_indexes=[0, 1], selected_cards=[0, 1])
    scoring_cards = [
        CardAdapter.to_scoring_format(cards[0], 0, state),
        CardAdapter.to_scoring_format(cards[1], 1, state),
    ]

    def script(phase, joker, context, game_state):
        if phase != "individual_scoring":
            return None
        card = context["card"]
        card_index = card.card_state.card_index
        if card_index == 0:
            return {
                "mult": 10 * card.card_state.times_scored,
                "retriggers": 2 if card.card_state.times_scored == 1 else 7,
                "message": f"played-{card_index}-pass-{card.card_state.times_scored}",
            }
        return {
            "mult": 40,
            "message": f"played-{card_index}-pass-{card.card_state.times_scored}",
        }

    effects = ScriptedJokerEffects(script)
    game_state = {"jokers": ["Recorder"]}

    _, breakdown = _score_hand_with_effects(
        scoring_cards,
        scoring_cards,
        HandType.HIGH_CARD,
        "High Card",
        game_state,
        effects,
    )

    assert effects.calls == [
        ("reset", None, None, None),
        ("before_scoring", "Recorder", None, None),
        ("individual_scoring", "Recorder", 0, 1),
        ("individual_scoring", "Recorder", 0, 2),
        ("individual_scoring", "Recorder", 0, 3),
        ("individual_scoring", "Recorder", 1, 1),
        ("held_card", "Recorder", None, None),
        ("joker_edition_chip_mult", "Recorder", None, None),
        ("scoring", "Recorder", None, None),
        ("joker_on_joker", "Recorder", None, None),
        ("joker_edition_x_mult", "Recorder", None, None),
        ("final_scoring_step", "Recorder", None, None),
        ("destroying_card", "Recorder", None, None),
        ("destroying_card", "Recorder", None, None),
        ("after_hand", "Recorder", None, None),
    ]
    assert game_state["_test_trace"] == [
        "played-0-pass-1",
        "played-0-pass-2",
        "played-0-pass-3",
        "played-1-pass-1",
    ]
    assert breakdown["card_retriggers"] == 2
    assert scoring_cards[0].card_state.times_scored == 3
    assert scoring_cards[1].card_state.times_scored == 1
    assert [
        (entry["stage"], entry["event"], entry.get("card_index"), entry.get("repetition_index"))
        for entry in breakdown["scoring_trace"]
        if entry["stage"] in {"repetitions", "scoring_card_effects"}
        and entry["event"] in {"repetition_discovery", "playing_card_base_enhancement"}
    ][:5] == [
        ("scoring_card_effects", "playing_card_base_enhancement", 0, 0),
        ("repetitions", "repetition_discovery", 0, 0),
        ("repetitions", "playing_card_base_enhancement", 0, 1),
        ("repetitions", "playing_card_base_enhancement", 0, 2),
        ("scoring_card_effects", "playing_card_base_enhancement", 1, 0),
    ]


def test_unified_scorer_scores_held_cards_after_played_cards_and_retriggers_only_effectful_first_passes():
    cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.TWO, Suit.CLUBS),
    ]
    state = UnifiedGameState(deck=cards, hand_indexes=[0, 1, 2], selected_cards=[0])
    state.get_card_state(1).enhancement = Enhancement.STEEL
    scoring_card = CardAdapter.to_scoring_format(cards[0], 0, state)
    held_steel = CardAdapter.to_scoring_format(cards[1], 1, state)
    held_blank = CardAdapter.to_scoring_format(cards[2], 2, state)

    score, breakdown = _score_hand(
        [scoring_card],
        [scoring_card],
        HandType.HIGH_CARD,
        "High Card",
        {
            "jokers": [{"name": "Mime"}],
            "held_cards": [held_steel, held_blank],
            "hand": [held_steel, held_blank],
        },
    )

    assert score == 36
    assert breakdown["final_chips"] == 16
    assert breakdown["final_mult"] == 1
    assert breakdown["final_x_mult"] == 2.25
    assert breakdown["effects_applied"].count("Held card (Steel): x1.5") == 2


def test_unified_scorer_does_not_retrigger_held_cards_without_a_first_pass_effect():
    cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.TWO, Suit.CLUBS)]
    state = UnifiedGameState(deck=cards, hand_indexes=[0, 1], selected_cards=[0])
    scoring_card = CardAdapter.to_scoring_format(cards[0], 0, state)
    held_blank = CardAdapter.to_scoring_format(cards[1], 1, state)

    score, breakdown = _score_hand(
        [scoring_card],
        [scoring_card],
        HandType.HIGH_CARD,
        "High Card",
        {
            "jokers": [{"name": "Mime"}],
            "held_cards": [held_blank],
            "hand": [held_blank],
        },
    )

    assert score == 16
    assert breakdown["final_x_mult"] == 1.0
    assert "Held card (Steel): x1.5" not in breakdown["effects_applied"]


def test_unified_scorer_orders_joker_edition_and_main_phases_like_lua():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    scoring_cards = cards

    def script(phase, joker, context, game_state):
        return {
            "joker_edition_chip_mult": {
                "chips": 10,
                "mult": 1,
                "message": "edition-chip-mult",
            },
            "scoring": {
                "chips": 20,
                "mult": 2,
                "x_mult": 2.0,
                "message": "joker-main",
            },
            "joker_on_joker": {
                "chips": 30,
                "mult": 3,
                "x_mult": 3.0,
                "message": "joker-on-joker",
            },
            "joker_edition_x_mult": {
                "x_mult": 4.0,
                "message": "edition-x-mult",
            },
        }.get(phase)

    effects = ScriptedJokerEffects(script)
    game_state = {"jokers": ["Recorder"]}

    score, breakdown = _score_hand_with_effects(
        cards,
        scoring_cards,
        HandType.HIGH_CARD,
        "High Card",
        game_state,
        effects,
    )

    assert game_state["_test_trace"] == [
        "edition-chip-mult",
        "joker-main",
        "joker-on-joker",
        "edition-x-mult",
    ]
    assert breakdown["effects_applied"][-4:] == [
        "Recorder (joker edition chip mult): +10c +1m x1.0",
        "Recorder (scoring): +20c +2m x2.0",
        "Recorder (joker on joker): +30c +3m x3.0",
        "Recorder (joker edition x mult): +0c +0m x4.0",
    ]
    assert breakdown["final_chips"] == 76
    assert breakdown["final_mult"] == 7
    assert breakdown["final_x_mult"] == 24.0
    assert score == 12768


def test_unified_scorer_runs_destruction_after_final_scoring_and_before_after_hand():
    cards = [Card(Rank.ACE, Suit.SPADES)]

    def script(phase, joker, context, game_state):
        return {
            "final_scoring_step": {"mult": 4, "message": "final-step"},
            "destroying_card": {"mult": 8, "message": "destroying-card"},
            "after_hand": {"mult": 16, "money": 2, "message": "after-hand"},
        }.get(phase)

    effects = ScriptedJokerEffects(script)
    game_state = {"jokers": ["Recorder"], "money": 0}

    score, breakdown = _score_hand_with_effects(
        cards,
        cards,
        HandType.HIGH_CARD,
        "High Card",
        game_state,
        effects,
    )

    assert game_state["_test_trace"] == [
        "final-step",
        "destroying-card",
        "after-hand",
    ]
    assert breakdown["effects_applied"][-3:] == [
        "Recorder (final scoring step): +0c +4m x1.0",
        "Recorder (destroying card): +0c +8m x1.0",
        "Recorder (after hand): +0c +16m x1.0",
    ]
    assert breakdown["final_mult"] == 5
    assert breakdown["joker_mult"] == 28
    assert breakdown["money_gained"] == 2
    assert score == 80
    assert [entry["applies_to_score"] for entry in breakdown["scoring_trace"] if entry["stage"] == "destruction_hooks"] == [False]
    assert [entry["applies_to_score"] for entry in breakdown["scoring_trace"] if entry["stage"] == "after_hand_effects"] == [False]


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


def test_unified_scorer_applies_enum_enhancements_and_editions():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    cases = [
        ({"enhancement": Enhancement.BONUS}, 46),
        ({"enhancement": Enhancement.MULT}, 80),
        ({"enhancement": Enhancement.GLASS}, 32),
        ({"edition": Edition.FOIL}, 66),
        ({"edition": Edition.HOLOGRAPHIC}, 176),
        ({"edition": Edition.POLYCHROME}, 24),
    ]

    for modifiers, expected_score in cases:
        state = UnifiedGameState(deck=cards, hand_indexes=[0])
        card_state = state.get_card_state(0)
        for attr, value in modifiers.items():
            setattr(card_state, attr, value)
        scoring_cards = [CardAdapter.to_scoring_format(cards[0], 0, state)]

        score, _ = _score_hand(
            scoring_cards,
            scoring_cards,
            HandType.HIGH_CARD,
            "High Card",
            state.to_dict(),
        )

        assert score == expected_score


def test_unified_scorer_red_seal_retriggers_card_scoring_not_final_score():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    state = UnifiedGameState(deck=cards, hand_indexes=[0])
    state.get_card_state(0).seal = Seal.RED
    scoring_cards = [CardAdapter.to_scoring_format(cards[0], 0, state)]

    score, breakdown = _score_hand(
        scoring_cards,
        scoring_cards,
        HandType.HIGH_CARD,
        "High Card",
        state.to_dict(),
    )

    assert score == 27
    assert breakdown["card_chips"] == 22
    assert breakdown["card_retriggers"] == 1


def test_modifier_logic_accepts_consumable_enum_family_by_name():
    cards = [Card(Rank.ACE, Suit.SPADES)]
    state = UnifiedGameState(deck=cards, hand_indexes=[0])
    card_state = state.get_card_state(0)
    card_state.enhancement = ConsumableEnhancement.MULT
    card_state.edition = ConsumableEdition.FOIL
    card_state.seal = ConsumableSeal.RED
    scoring_cards = [CardAdapter.to_scoring_format(cards[0], 0, state)]

    score, breakdown = _score_hand(
        scoring_cards,
        scoring_cards,
        HandType.HIGH_CARD,
        "High Card",
        state.to_dict(),
    )

    assert score == 1143
    assert breakdown["card_retriggers"] == 1
    assert state.get_card_state(0).times_scored == 2


def test_blue_seal_creates_planet_from_held_card_at_round_end_only():
    cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.CLUBS),
    ]
    state = UnifiedGameState(
        deck=cards,
        hand_indexes=[0, 1],
        selected_cards=[0],
        consumable_slots=2,
        last_hand_played="High Card",
    )
    state.get_card_state(0).seal = Seal.BLUE
    state.get_card_state(1).seal = Seal.BLUE
    state.get_card_state(2).seal = Seal.BLUE
    handler = _make_play_handler(state)
    scoring_cards = [CardAdapter.to_scoring_format(cards[0], 0, state)]

    _, _, _, consumables_created = handler._apply_card_effects(
        scoring_cards,
        [cards[0]],
        16,
        "High Card",
    )

    assert consumables_created == []

    state.hand_indexes = [1, 2]
    state.last_held_card_indexes = [1]
    state.selected_cards = []
    RoundManager(
        state,
        SimpleNamespace(round_hands=0, round_discards=0),
        SimpleNamespace(end_of_round_effects=lambda _: []),
        boss_blind_manager=None,
    ).advance_round()

    assert state.consumables == ["Pluto"]


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

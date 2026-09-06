from __future__ import annotations

from balatro_gym.environments.live import (
    ActionKind,
    LegalAction,
    RoundTacticsObservation,
)
from balatro_gym.policies import DeterministicLegalHeuristic


def observation(
    cards: tuple[dict[str, object], ...], *, discards_left: int = 3
) -> RoundTacticsObservation:
    return RoundTacticsObservation(
        version="round-tactics/v1",
        hand=cards,
        remaining_deck_cards=44,
        round_chips=0,
        blind_target=300,
        hands_left=4,
        discards_left=discards_left,
        hands_played=0,
        discards_used=0,
        money=4,
        poker_hands={
            "High Card": {"chips": 5, "mult": 1},
            "Pair": {"chips": 10, "mult": 2},
        },
        jokers=(),
    )


def card(rank: str, suit: str, *, chips: int | None = None) -> dict[str, object]:
    value: dict[str, object] = {"rank": rank, "suit": suit}
    if chips is not None:
        value["chips"] = chips
    return {"value": value}


def test_policy_selects_the_highest_immediate_score_from_the_mask() -> None:
    policy = DeterministicLegalHeuristic()
    state = observation((card("2", "Spades"), card("2", "Hearts"), card("K", "Clubs")))
    mask = (
        LegalAction(ActionKind.PLAY, (0,)),
        LegalAction(ActionKind.PLAY, (2,)),
        LegalAction(ActionKind.PLAY, (0, 1)),
        LegalAction(ActionKind.DISCARD, (0, 2)),
    )

    assert policy.select_action(state, mask) == LegalAction(ActionKind.PLAY, (0, 1))


def test_policy_breaks_equal_play_scores_by_fewer_cards_then_indices() -> None:
    policy = DeterministicLegalHeuristic()
    state = observation(
        (card("K", "Spades", chips=23), card("2", "Hearts"), card("2", "Clubs"))
    )
    mask = (
        LegalAction(ActionKind.PLAY, (0,)),
        LegalAction(ActionKind.PLAY, (1, 2)),
    )

    assert policy.select_action(state, mask) == LegalAction(ActionKind.PLAY, (0,))


def test_policy_discards_unretained_cards_when_best_play_is_below_threshold() -> None:
    policy = DeterministicLegalHeuristic()
    state = observation(
        (card("K", "Spades"), card("3", "Hearts"), card("7", "Clubs"))
    )
    mask = (
        LegalAction(ActionKind.PLAY, (0,)),
        LegalAction(ActionKind.DISCARD, (1, 2)),
        LegalAction(ActionKind.DISCARD, (0, 1)),
    )

    assert policy.select_action(state, mask) == LegalAction(ActionKind.DISCARD, (1, 2))


def test_policy_never_returns_an_action_absent_from_the_mask() -> None:
    policy = DeterministicLegalHeuristic()
    state = observation((card("2", "Spades"), card("2", "Hearts")))
    mask = (LegalAction(ActionKind.DISCARD, (0,)),)

    assert policy.select_action(state, mask) == LegalAction(ActionKind.DISCARD, (0,))

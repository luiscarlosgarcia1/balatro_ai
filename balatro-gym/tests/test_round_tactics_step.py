from __future__ import annotations

import pytest

from balatro_gym.environments.live import (
    ActionKind,
    LegalAction,
    RoundTacticsEnvironment,
    StepResult,
)
from round_tactics_support import ScriptedBridge, selecting_hand_state


ReplayCounters = list[tuple[str, int, int, int, int, int]]


def reset_environment(bridge: ScriptedBridge) -> tuple[RoundTacticsEnvironment, tuple[LegalAction, ...]]:
    environment = RoundTacticsEnvironment(bridge)
    result = environment.reset("BAL9SEED")
    return environment, result.legal_action_mask


def test_step_executes_a_legal_play_and_returns_the_next_settled_mask() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(card_ids=(10, 11)),
            selecting_hand_state(card_ids=(20, 21, 22), discards_left=2),
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)
    action = next(
        action
        for action in legal_action_mask
        if action.kind == ActionKind.PLAY and action.indices == (1,)
    )

    result = environment.step(action)

    assert bridge.calls[-1] == ("play", {"cards": [1]})
    assert [card["id"] for card in result.observation.hand] == [20, 21, 22]
    assert all(action.indices[-1] < 3 for action in result.legal_action_mask)
    assert any(
        action.kind == ActionKind.DISCARD for action in result.legal_action_mask
    )
    assert result.reward == 0
    assert not result.terminated
    assert not result.truncated


def test_step_executes_an_eligible_discard() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            selecting_hand_state(discards_left=2),
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)
    action = next(
        action
        for action in legal_action_mask
        if action.kind == ActionKind.DISCARD and action.indices == (0, 1)
    )

    environment.step(action)

    assert bridge.calls[-1] == ("discard", {"cards": [0, 1]})


@pytest.mark.parametrize(
    "action",
    [
        LegalAction(ActionKind.PLAY, ()),
        LegalAction(ActionKind.PLAY, (0, 0)),
        LegalAction(ActionKind.PLAY, (1, 0)),
        LegalAction(ActionKind.PLAY, (2,)),
        LegalAction(ActionKind.DISCARD, (0,)),
    ],
)
def test_step_rejects_invalid_actions_before_invoking_the_bridge(
    action: LegalAction,
) -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(discards_left=0),
        ]
    )
    environment, _ = reset_environment(bridge)
    calls_before_step = list(bridge.calls)

    with pytest.raises(ValueError):
        environment.step(action)

    assert bridge.calls == calls_before_step


def test_step_rejects_a_stale_action_before_invoking_the_bridge() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            selecting_hand_state(),
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)
    action = legal_action_mask[0]

    environment.step(action)
    calls_after_first_step = list(bridge.calls)

    with pytest.raises(ValueError, match="stale"):
        environment.step(action)

    assert bridge.calls == calls_after_first_step


def test_step_marks_round_eval_as_a_rewarded_terminal_victory() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            selecting_hand_state(
                chips=348,
                hands_left=2,
                hands_played=2,
                discards_left=1,
                discards_used=2,
                money=4,
            )
            | {"state": "ROUND_EVAL"},
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)
    action = legal_action_mask[0]

    result = environment.step(action)
    calls_after_completion = list(bridge.calls)

    assert result.state == "ROUND_EVAL"
    assert result.legal_action_mask == ()
    assert result.reward == 1.125
    assert result.terminated
    assert not result.truncated
    assert result.observation.round_chips == 348
    assert result.observation.hands_left == 2
    assert result.observation.hands_played == 2
    assert result.observation.discards_used == 2
    assert result.observation.money == 4
    with pytest.raises(ValueError, match="no active hand"):
        environment.step(action)

    assert bridge.calls == calls_after_completion


def test_step_marks_game_over_as_a_terminal_failure() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            {"state": "GAME_OVER"},
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)

    result = environment.step(legal_action_mask[0])

    assert result.state == "GAME_OVER"
    assert result.reward == -1
    assert result.terminated
    assert not result.truncated


def test_step_classifies_external_limits_and_bridge_faults_as_truncation() -> None:
    limit_bridge = ScriptedBridge(
        [{"state": "MENU"}, {"state": "BLIND_SELECT"}, selecting_hand_state()]
    )
    limited = RoundTacticsEnvironment(limit_bridge, max_steps=0)
    actions = limited.reset("BAL9SEED").legal_action_mask

    limit_result = limited.step(actions[0])

    assert limit_result.state == "EXTERNAL_LIMIT"
    assert limit_result.reward == 0
    assert not limit_result.terminated
    assert limit_result.truncated
    assert len(limit_bridge.calls) == 3

    fault_bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            ConnectionError("bridge unavailable"),
        ]
    )
    fault_environment, fault_actions = reset_environment(fault_bridge)

    fault_result = fault_environment.step(fault_actions[0])

    assert fault_result.state == "BRIDGE_FAULT"
    assert fault_result.reward == 0
    assert not fault_result.terminated
    assert fault_result.truncated


def test_bal9seed_trace_replays_twice_to_the_specified_terminal_state() -> None:
    def replay() -> tuple[StepResult, list[tuple[str, object]], ReplayCounters]:
        bridge = ScriptedBridge(
            [
                {"state": "MENU"},
                {"state": "BLIND_SELECT"},
                selecting_hand_state(hand_size=8),
                selecting_hand_state(hand_size=8, discards_left=2, discards_used=1),
                selecting_hand_state(
                    hand_size=8,
                    chips=174,
                    hands_left=3,
                    discards_left=2,
                    hands_played=1,
                    discards_used=1,
                ),
                selecting_hand_state(
                    hand_size=8,
                    chips=174,
                    hands_left=3,
                    discards_left=1,
                    hands_played=1,
                    discards_used=2,
                ),
                selecting_hand_state(
                    hand_size=8,
                    chips=348,
                    hands_left=2,
                    discards_left=1,
                    hands_played=2,
                    discards_used=2,
                    money=4,
                )
                | {"state": "ROUND_EVAL"},
            ]
        )
        environment = RoundTacticsEnvironment(bridge)
        reset_result = environment.reset("BAL9SEED")
        actions = reset_result.legal_action_mask
        counters = [
            (
                "SELECTING_HAND",
                reset_result.observation.round_chips,
                reset_result.observation.hands_left,
                reset_result.observation.discards_used,
                reset_result.observation.hands_played,
                reset_result.observation.money,
            )
        ]
        for kind, indices in (
            (ActionKind.DISCARD, (2, 3, 4, 7)),
            (ActionKind.PLAY, (5, 6)),
            (ActionKind.DISCARD, (6, 7)),
            (ActionKind.PLAY, (2, 3, 4, 5, 7)),
        ):
            action = next(
                action
                for action in actions
                if action.kind == kind and action.indices == indices
            )
            result = environment.step(action)
            actions = result.legal_action_mask
            counters.append(
                (
                    result.state,
                    result.observation.round_chips,
                    result.observation.hands_left,
                    result.observation.discards_used,
                    result.observation.hands_played,
                    result.observation.money,
                )
            )
        return result, bridge.calls, counters

    first_result, first_calls, first_counters = replay()
    second_result, second_calls, second_counters = replay()

    assert first_calls == second_calls
    assert first_result == second_result
    assert first_counters == second_counters == [
        ("SELECTING_HAND", 12, 4, 0, 0, 4),
        ("SELECTING_HAND", 12, 4, 1, 0, 4),
        ("SELECTING_HAND", 174, 3, 1, 1, 4),
        ("SELECTING_HAND", 174, 3, 2, 1, 4),
        ("ROUND_EVAL", 348, 2, 2, 2, 4),
    ]
    assert first_result.state == "ROUND_EVAL"
    assert first_result.observation.round_chips == 348
    assert first_result.observation.blind_target == 300
    assert first_result.observation.hands_left == 2
    assert first_result.observation.discards_used == 2
    assert first_result.observation.hands_played == 2
    assert first_result.observation.money == 4

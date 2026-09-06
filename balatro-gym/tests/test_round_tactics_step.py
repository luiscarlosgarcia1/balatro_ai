from __future__ import annotations

import pytest

from balatro_gym.environments.live import ActionKind, LegalAction, RoundTacticsEnvironment
from round_tactics_support import ScriptedBridge, selecting_hand_state


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


def test_step_returns_a_completion_state_and_rejects_follow_on_actions() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(),
            {"state": "ROUND_EVAL"},
        ]
    )
    environment, legal_action_mask = reset_environment(bridge)
    action = legal_action_mask[0]

    result = environment.step(action)
    calls_after_completion = list(bridge.calls)

    assert result.state == "ROUND_EVAL"
    assert result.legal_action_mask == ()
    with pytest.raises(ValueError, match="no active hand"):
        environment.step(action)

    assert bridge.calls == calls_after_completion

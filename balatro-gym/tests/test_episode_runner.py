from __future__ import annotations

from dataclasses import dataclass

import pytest

from balatro_gym.environments.live import (
    ActionKind,
    LegalAction,
    RoundTacticsEnvironment,
)
from balatro_gym.episode_runner import EpisodeExecutionError, RoundTacticsEpisodeRunner

from round_tactics_support import ScriptedBridge, selecting_hand_state


@dataclass(frozen=True)
class FirstLegalActionPolicy:
    revision: str = "first-legal-action/v1"

    def select_action(
        self, observation: object, legal_action_mask: tuple[LegalAction, ...]
    ) -> LegalAction:
        del observation
        return legal_action_mask[0]


@dataclass(frozen=True)
class StaleActionPolicy:
    revision: str = "stale-action/v1"

    def select_action(
        self, observation: object, legal_action_mask: tuple[LegalAction, ...]
    ) -> LegalAction:
        del observation, legal_action_mask
        return LegalAction(ActionKind.PLAY, (0,))


def test_episode_runner_drives_a_multistep_round_eval_episode_and_observes_actions() -> None:
    initial = selecting_hand_state(hand_size=1)
    next_hand = selecting_hand_state(hand_size=1, hands_left=3, hands_played=1)
    terminal = selecting_hand_state(hand_size=1, hands_left=2, hands_played=2)
    terminal["state"] = "ROUND_EVAL"
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            initial,
            next_hand,
            terminal,
        ]
    )
    observed_actions: list[LegalAction] = []

    outcome = RoundTacticsEpisodeRunner(
        RoundTacticsEnvironment(bridge), action_observer=observed_actions.append
    )(FirstLegalActionPolicy(), "BAL9SEED")

    assert outcome.seed == "BAL9SEED"
    assert outcome.won
    assert outcome.hands_left == 2
    assert outcome.terminal_reward == 1.125
    assert observed_actions == [LegalAction(ActionKind.PLAY, (0,))] * 2
    assert [method for method, _ in bridge.calls] == [
        "menu",
        "start",
        "select",
        "play",
        "play",
    ]


@pytest.mark.parametrize(
    ("terminal_state", "won"), [("ROUND_EVAL", True), ("GAME_OVER", False)]
)
def test_episode_runner_maps_supported_terminal_states_to_outcomes(
    terminal_state: str, won: bool
) -> None:
    terminal = selecting_hand_state(hand_size=1, hands_left=3)
    terminal["state"] = terminal_state
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(hand_size=1),
            terminal,
        ]
    )

    outcome = RoundTacticsEpisodeRunner(RoundTacticsEnvironment(bridge))(
        FirstLegalActionPolicy(), "BAL9SEED"
    )

    assert outcome.won is won
    assert outcome.hands_left == 3


def test_episode_runner_rejects_a_policy_action_outside_the_current_mask() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(hand_size=1),
        ]
    )

    with pytest.raises(EpisodeExecutionError, match="outside the legal mask"):
        RoundTacticsEpisodeRunner(RoundTacticsEnvironment(bridge))(
            StaleActionPolicy(), "BAL9SEED"
        )

    assert [method for method, _ in bridge.calls] == ["menu", "start", "select"]


def test_episode_runner_rejects_a_truncated_episode() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(hand_size=1),
        ]
    )

    with pytest.raises(EpisodeExecutionError, match="truncated"):
        RoundTacticsEpisodeRunner(RoundTacticsEnvironment(bridge, max_steps=0))(
            FirstLegalActionPolicy(), "BAL9SEED"
        )

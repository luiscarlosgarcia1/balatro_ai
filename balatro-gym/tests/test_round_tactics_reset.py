from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from balatro_gym.environments.live import (
    OBSERVATION_VERSION,
    ActionKind,
    RoundTacticsEnvironment,
)


class ScriptedBridge:
    def __init__(self, states: list[dict[str, Any]]) -> None:
        self.states = iter(states)
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def call(
        self, method: str, params: Mapping[str, object] | None = None
    ) -> Mapping[str, Any]:
        self.calls.append((method, params))
        return next(self.states)


def selecting_hand_state(
    *, discards_left: int = 3, hand_size: int = 2
) -> dict[str, Any]:
    return {
        "state": "SELECTING_HAND",
        "hand": {
            "cards": [
                {"id": index, "value": {"rank": str(index)}}
                for index in range(hand_size)
            ]
        },
        "cards": {"count": 44},
        "round": {"chips": 12, "hands_left": 4, "discards_left": discards_left},
        "blinds": {"small": {"score": 300}},
        "hands": {"Pair": {"chips": 10, "mult": 2, "level": 1}},
        "jokers": {"cards": [{"key": "j_joker", "modifier": {}}]},
        "shop": {"cards": [{"key": "should_not_escape"}]},
    }


def test_reset_starts_seeded_red_white_run_selects_small_blind_and_projects_it() -> None:
    bridge = ScriptedBridge(
        [{"state": "MENU"}, {"state": "BLIND_SELECT"}, selecting_hand_state()]
    )

    result = RoundTacticsEnvironment(bridge).reset("BAL9SEED")

    assert bridge.calls == [
        ("menu", None),
        ("start", {"deck": "RED", "stake": "WHITE", "seed": "BAL9SEED"}),
        ("select", None),
    ]
    assert result.observation.version == OBSERVATION_VERSION
    assert [card["id"] for card in result.observation.hand] == [0, 1]
    assert result.observation.remaining_deck_cards == 44
    assert result.observation.round_chips == 12
    assert result.observation.blind_target == 300
    assert result.observation.hands_left == 4
    assert result.observation.discards_left == 3
    assert result.observation.poker_hands["Pair"]["mult"] == 2
    assert result.observation.jokers[0]["key"] == "j_joker"
    assert not hasattr(result.observation, "shop")


def test_reset_admits_each_canonical_play_and_discard_subset_when_discards_remain() -> None:
    bridge = ScriptedBridge(
        [{"state": "MENU"}, {"state": "BLIND_SELECT"}, selecting_hand_state()]
    )

    actions = RoundTacticsEnvironment(bridge).reset("BAL9SEED").legal_action_mask

    assert {(action.kind, action.indices) for action in actions} == {
        (kind, indices)
        for kind in (ActionKind.PLAY, ActionKind.DISCARD)
        for indices in ((0,), (1,), (0, 1))
    }


def test_reset_omits_discard_subsets_when_none_remain() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(discards_left=0),
        ]
    )

    actions = RoundTacticsEnvironment(bridge).reset("BAL9SEED").legal_action_mask

    assert all(action.kind == ActionKind.PLAY for action in actions)


def test_reset_caps_legal_subsets_at_five_cards() -> None:
    bridge = ScriptedBridge(
        [
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
            selecting_hand_state(hand_size=6),
        ]
    )

    actions = RoundTacticsEnvironment(bridge).reset("BAL9SEED").legal_action_mask

    assert len(actions) == 124
    assert all(1 <= len(action.indices) <= 5 for action in actions)
    assert all(action.indices == tuple(sorted(set(action.indices))) for action in actions)

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ScriptedBridge:
    def __init__(self, states: list[dict[str, Any] | Exception]) -> None:
        self.states = iter(states)
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def call(
        self, method: str, params: Mapping[str, object] | None = None
    ) -> Mapping[str, Any]:
        self.calls.append((method, params))
        result = next(self.states)
        if isinstance(result, Exception):
            raise result
        return result


def selecting_hand_state(
    *,
    card_ids: tuple[int, ...] | None = None,
    discards_left: int = 3,
    hand_size: int = 2,
    chips: int = 12,
    hands_left: int = 4,
    hands_played: int = 0,
    discards_used: int = 0,
    money: int = 4,
) -> dict[str, Any]:
    card_ids = card_ids if card_ids is not None else tuple(range(hand_size))
    return {
        "state": "SELECTING_HAND",
        "hand": {
            "cards": [
                {"id": card_id, "value": {"rank": str(card_id)}}
                for card_id in card_ids
            ]
        },
        "cards": {"count": 44},
        "round": {
            "chips": chips,
            "hands_left": hands_left,
            "discards_left": discards_left,
            "hands_played": hands_played,
            "discards_used": discards_used,
        },
        "money": money,
        "blinds": {"small": {"score": 300}},
        "hands": {"Pair": {"chips": 10, "mult": 2, "level": 1}},
        "jokers": {"cards": [{"key": "j_joker", "modifier": {}}]},
        "shop": {"cards": [{"key": "should_not_escape"}]},
    }

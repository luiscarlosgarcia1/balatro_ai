from __future__ import annotations

from ..models import (
    ObservedInterest,
    ObservedPackContents,
    ObservedRunHand,
    ObservedRunInfo,
    RUN_INFO_HAND_ORDER,
)
from .coercion import int_or_none
from .zones import parse_cards


def parse_interest(payload: object) -> ObservedInterest | None:
    if isinstance(payload, dict):
        return ObservedInterest(
            amount=int_or_none(payload.get("amount", payload.get("interest_amount"))),
            cap=int_or_none(payload.get("cap", payload.get("interest_cap"))),
            no_interest=bool(payload.get("no_interest", False)),
        )

    scalar = int_or_none(payload)
    if scalar is None:
        return None
    return ObservedInterest(amount=scalar, cap=None, no_interest=False)


def parse_run_info(payload: object) -> ObservedRunInfo | None:
    if not isinstance(payload, dict):
        return None

    hands_payload = payload.get("hands")
    if not isinstance(hands_payload, dict):
        return None

    hands: list[ObservedRunHand] = []
    for hand_name in RUN_INFO_HAND_ORDER:
        hand_payload = hands_payload.get(hand_name)
        if not isinstance(hand_payload, dict):
            continue
        hands.append(
            ObservedRunHand(
                hand_name=hand_name,
                level=int_or_none(hand_payload.get("level")),
                mult=int_or_none(hand_payload.get("mult")),
                chips=int_or_none(hand_payload.get("chips")),
                played=int_or_none(hand_payload.get("played")),
                played_this_round=int_or_none(hand_payload.get("played_this_round")),
            )
        )

    return ObservedRunInfo(hands=tuple(hands)) if hands else None


def parse_pack_contents(payload: object) -> ObservedPackContents | None:
    if not isinstance(payload, dict):
        return None

    return ObservedPackContents(
        choices_remaining=int_or_none(payload.get("choices_remaining")),
        skip_available=bool(payload.get("skip_available", False)),
        cards=tuple(parse_cards(payload.get("cards"))),
    )

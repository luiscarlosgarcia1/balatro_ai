from __future__ import annotations

from ...models import (
    ObservedInterest,
    ObservedPackContents,
    ObservedPackItem,
    ObservedRunHand,
    ObservedRunInfo,
    RUN_INFO_HAND_ORDER,
)
from .coercion import int_or_none, int_or_zero
from .zones import parse_card, parse_consumable, parse_joker, parse_pack


def parse_interest(payload: object) -> ObservedInterest | None:
    if isinstance(payload, dict):
        return ObservedInterest(
            amount=int_or_zero(payload.get("amount", payload.get("interest_amount"))),
            cap=int_or_zero(payload.get("cap", payload.get("interest_cap"))),
            no_interest=bool(payload.get("no_interest", False)),
        )

    scalar = int_or_none(payload)
    if scalar is None:
        return None
    return ObservedInterest(amount=scalar, cap=0, no_interest=False)


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
                level=int_or_zero(hand_payload.get("level")),
                mult=int_or_zero(hand_payload.get("mult")),
                chips=int_or_zero(hand_payload.get("chips")),
                played=int_or_zero(hand_payload.get("played")),
                played_this_round=int_or_zero(hand_payload.get("played_this_round")),
            )
        )

    return ObservedRunInfo(hands=tuple(hands)) if hands else None


def parse_pack_contents(payload: object) -> ObservedPackContents | None:
    if not isinstance(payload, dict):
        return None

    items_payload = payload.get("items", payload.get("cards"))
    items: list[ObservedPackItem] = []
    if isinstance(items_payload, list):
        for index, item in enumerate(items_payload):
            parsed_item = _parse_pack_item(item, index)
            if parsed_item is not None:
                items.append(parsed_item)

    return ObservedPackContents(
        pack=parse_pack(payload.get("pack"), 0),
        choices_remaining=int_or_none(payload.get("choices_remaining")),
        skip_available=bool(payload.get("skip_available", False)),
        items=tuple(items),
    )


def _parse_pack_item(payload: object, fallback_index: int) -> ObservedPackItem | None:
    if not isinstance(payload, dict):
        return None

    key = payload.get("key", payload.get("card_key"))
    if isinstance(key, str) and key.startswith("j_"):
        return parse_joker(payload, fallback_index)
    if isinstance(key, str) and key.startswith("c_") and payload.get("card_key") is None:
        return parse_consumable(payload, fallback_index)
    return parse_card(payload, fallback_index)

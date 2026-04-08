from __future__ import annotations

from ...models import (
    ObservedBlind,
    ObservedCard,
    ObservedConsumable,
    ObservedJoker,
    ObservedPack,
    ObservedReference,
    ObservedTag,
    ObservedVoucher,
)
from .coercion import first_non_none, int_or_none, int_or_zero, string_or_none


def parse_instance_id(payload: dict[str, object], fallback_index: int = 0) -> int:
    instance_id = int_or_none(first_non_none(payload.get("instance_id"), payload.get("id"), payload.get("ID")))
    if instance_id is not None:
        return instance_id
    return -(fallback_index + 1)


def parse_card(payload: object, fallback_index: int = 0) -> ObservedCard | None:
    if not isinstance(payload, dict):
        return None

    card_key = string_or_none(first_non_none(payload.get("card_key"), payload.get("code"), payload.get("key")))
    if not card_key:
        return None

    return ObservedCard(
        card_key=card_key,
        instance_id=parse_instance_id(payload, fallback_index),
        enhancement=string_or_none(payload.get("enhancement")),
        edition=string_or_none(payload.get("edition")),
        seal=string_or_none(payload.get("seal")),
        facing=string_or_none(payload.get("facing")),
        debuffed=bool(payload.get("debuffed", False)),
    )


def parse_voucher(payload: object, fallback_index: int = 0) -> ObservedVoucher | None:
    if not isinstance(payload, dict):
        return None

    key = string_or_none(payload.get("key"))
    if not key:
        return None

    return ObservedVoucher(
        key=key,
        instance_id=parse_instance_id(payload, fallback_index),
        cost=int_or_zero(payload.get("cost")),
    )


def parse_joker(payload: object, fallback_index: int = 0) -> ObservedJoker | None:
    if not isinstance(payload, dict):
        return None

    key = string_or_none(payload.get("key"))
    if not key:
        return None

    stickers = payload.get("stickers")
    sticker_set = {str(value).lower() for value in stickers} if isinstance(stickers, list) else set()
    eternal = payload.get("eternal")
    perishable = payload.get("perishable")
    rental = payload.get("rental")

    return ObservedJoker(
        key=key,
        instance_id=parse_instance_id(payload, fallback_index),
        eternal=bool(eternal) if eternal is not None else "eternal" in sticker_set,
        perishable=bool(perishable) if perishable is not None else "perishable" in sticker_set,
        rental=bool(rental) if rental is not None else "rental" in sticker_set,
        perish_tally=int_or_none(payload.get("perish_tally")),
        edition=string_or_none(payload.get("edition")),
        debuffed=bool(payload.get("debuffed", False)),
        cost=int_or_none(payload.get("cost")),
        sell_cost=int_or_none(first_non_none(payload.get("sell_cost"), payload.get("sell_price"))),
    )


def parse_consumable(payload: object, fallback_index: int = 0) -> ObservedConsumable | None:
    if not isinstance(payload, dict):
        return None

    key = string_or_none(payload.get("key"))
    if not key:
        return None

    return ObservedConsumable(
        key=key,
        instance_id=parse_instance_id(payload, fallback_index),
        edition=string_or_none(payload.get("edition")),
        cost=int_or_none(payload.get("cost")),
        sell_cost=int_or_none(first_non_none(payload.get("sell_cost"), payload.get("sell_price"))),
    )


def parse_pack(payload: object, fallback_index: int = 0) -> ObservedPack | None:
    if not isinstance(payload, dict):
        return None

    key = string_or_none(payload.get("key"))
    if not key:
        return None

    return ObservedPack(
        key=key,
        instance_id=parse_instance_id(payload, fallback_index),
        cost=int_or_none(payload.get("cost")),
    )


def parse_cards(payload: object) -> list[ObservedCard]:
    cards: list[ObservedCard] = []
    if not isinstance(payload, list):
        return cards

    for index, item in enumerate(payload):
        card = parse_card(item, index)
        if card is not None:
            cards.append(card)
    return cards


def parse_references(payload: object) -> list[ObservedReference]:
    references: list[ObservedReference] = []
    if not isinstance(payload, list):
        return references

    for index, item in enumerate(payload):
        reference = parse_reference(item, index)
        if reference is not None:
            references.append(reference)
    return references


def parse_reference(payload: object, fallback_index: int = 0) -> ObservedReference | None:
    if not isinstance(payload, dict):
        return None

    zone = string_or_none(payload.get("zone"))
    if not zone:
        return None

    key = string_or_none(
        first_non_none(
            payload.get("key"),
            payload.get("card_key"),
            payload.get("joker_key"),
            payload.get("consumable_key"),
            payload.get("pack_key"),
            payload.get("voucher_key"),
        )
    )
    if not key:
        return None

    return ObservedReference(
        zone=zone,
        instance_id=parse_instance_id(payload, fallback_index),
        key=key,
    )


def parse_vouchers(payload: object) -> list[ObservedVoucher]:
    vouchers: list[ObservedVoucher] = []
    if not isinstance(payload, list):
        return vouchers

    for index, item in enumerate(payload):
        voucher = parse_voucher(item, index)
        if voucher is not None:
            vouchers.append(voucher)
    return vouchers


def parse_jokers(payload: object) -> list[ObservedJoker]:
    jokers: list[ObservedJoker] = []
    if not isinstance(payload, list):
        return jokers

    for index, item in enumerate(payload):
        joker = parse_joker(item, index)
        if joker is not None:
            jokers.append(joker)
    return jokers


def parse_consumables(payload: object) -> list[ObservedConsumable]:
    consumables: list[ObservedConsumable] = []
    if not isinstance(payload, list):
        return consumables

    for index, item in enumerate(payload):
        consumable = parse_consumable(item, index)
        if consumable is not None:
            consumables.append(consumable)
    return consumables


def parse_tags(payload: object) -> list[ObservedTag]:
    tags: list[ObservedTag] = []
    if not isinstance(payload, list):
        return tags

    for item in payload:
        if not isinstance(item, dict):
            continue
        key = string_or_none(item.get("key"))
        if not key:
            continue
        tags.append(ObservedTag(key=key))
    return tags


def parse_blinds(payload: object) -> list[ObservedBlind]:
    blinds: list[ObservedBlind] = []
    if not isinstance(payload, list):
        return blinds

    for item in payload:
        if not isinstance(item, dict):
            continue
        key = string_or_none(item.get("key"))
        state = string_or_none(item.get("state"))
        if not key or not state:
            continue
        blinds.append(
            ObservedBlind(
                key=key,
                state=state,
                tag_key=string_or_none(item.get("tag_key", item.get("tag"))),
            )
        )
    return blinds

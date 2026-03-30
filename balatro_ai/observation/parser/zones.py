from __future__ import annotations

from ..models import (
    ObservedBlind,
    ObservedCard,
    ObservedConsumable,
    ObservedJoker,
    ObservedReference,
    ObservedTag,
    ObservedVoucher,
)
from .coercion import int_or_none, string_or_none


def parse_cards(payload: object) -> list[ObservedCard]:
    cards: list[ObservedCard] = []
    if not isinstance(payload, list):
        return cards

    for item in payload:
        if not isinstance(item, dict):
            continue
        stickers = item.get("stickers")
        cards.append(
            ObservedCard(
                card_key=string_or_none(item.get("card_key", item.get("code"))),
                card_kind=string_or_none(item.get("card_kind", item.get("kind"))),
                suit=string_or_none(item.get("suit")),
                rank=string_or_none(item.get("rank")),
                rarity=string_or_none(item.get("rarity")),
                enhancement=string_or_none(item.get("enhancement")),
                edition=string_or_none(item.get("edition")),
                seal=string_or_none(item.get("seal")),
                stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                facing=string_or_none(item.get("facing")),
                cost=int_or_none(item.get("cost")),
                sell_price=int_or_none(item.get("sell_price")),
                debuffed=bool(item.get("debuffed", False)),
            )
        )
    return cards


def parse_references(payload: object) -> list[ObservedReference]:
    references: list[ObservedReference] = []
    if not isinstance(payload, list):
        return references

    for item in payload:
        reference = parse_reference(item)
        if reference is not None:
            references.append(reference)
    return references


def parse_reference(payload: object) -> ObservedReference | None:
    if not isinstance(payload, dict):
        return None

    zone = string_or_none(payload.get("zone"))
    if not zone:
        return None

    reference = ObservedReference(
        zone=zone,
        card_key=string_or_none(payload.get("card_key")),
        joker_key=string_or_none(payload.get("joker_key")),
        consumable_key=string_or_none(payload.get("consumable_key")),
        pack_key=string_or_none(payload.get("pack_key")),
        voucher_key=string_or_none(payload.get("voucher_key")),
    )
    if any(
        value is not None
        for value in (
            reference.card_key,
            reference.joker_key,
            reference.consumable_key,
            reference.pack_key,
            reference.voucher_key,
        )
    ):
        return reference
    return None


def parse_vouchers(payload: object) -> list[ObservedVoucher]:
    vouchers: list[ObservedVoucher] = []
    if not isinstance(payload, list):
        return vouchers

    for item in payload:
        if not isinstance(item, dict):
            continue
        key = string_or_none(item.get("key"))
        if not key:
            continue
        vouchers.append(
            ObservedVoucher(
                key=key,
                cost=int_or_none(item.get("cost")),
            )
        )
    return vouchers


def parse_jokers(payload: object) -> list[ObservedJoker]:
    jokers: list[ObservedJoker] = []
    if not isinstance(payload, list):
        return jokers

    for item in payload:
        if not isinstance(item, dict):
            continue
        key = string_or_none(item.get("key"))
        if not key:
            continue
        stickers = item.get("stickers")
        jokers.append(
            ObservedJoker(
                key=key,
                rarity=string_or_none(item.get("rarity")),
                edition=string_or_none(item.get("edition")),
                sell_price=int_or_none(item.get("sell_price")),
                debuffed=bool(item.get("debuffed", False)),
                stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
            )
        )
    return jokers


def parse_consumables(payload: object) -> list[ObservedConsumable]:
    consumables: list[ObservedConsumable] = []
    if not isinstance(payload, list):
        return consumables

    for item in payload:
        if not isinstance(item, dict):
            continue
        key = string_or_none(item.get("key"))
        if not key:
            continue
        consumables.append(
            ObservedConsumable(
                key=key,
                edition=string_or_none(item.get("edition")),
                sell_price=int_or_none(item.get("sell_price")),
            )
        )
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
                tag_claimed=bool(item.get("tag_claimed", False)),
            )
        )
    return blinds

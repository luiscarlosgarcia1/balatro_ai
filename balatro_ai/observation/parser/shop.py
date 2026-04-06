from __future__ import annotations

from ...models import ObservedCard, ObservedConsumable, ObservedJoker, ObservedPack, ObservedShopItem, ObservedVoucher
from .zones import parse_card, parse_consumable, parse_joker, parse_pack, parse_voucher


def parse_shop_items(payload: object) -> list[ObservedShopItem]:
    shop_items: list[ObservedShopItem] = []
    if not isinstance(payload, list):
        return shop_items

    for index, item in enumerate(payload):
        parsed_item = parse_shop_item(item, index)
        if parsed_item is not None:
            shop_items.append(parsed_item)
    return shop_items


def parse_shop_item(payload: object, fallback_index: int = 0) -> ObservedShopItem | None:
    if not isinstance(payload, dict):
        return None

    card_payload = payload.get("card")
    if card_payload is not None:
        return parse_card(card_payload, fallback_index)

    joker_payload = payload.get("joker")
    if joker_payload is not None:
        return parse_joker(joker_payload, fallback_index)

    consumable_payload = payload.get("consumable")
    if consumable_payload is not None:
        return parse_consumable(consumable_payload, fallback_index)

    voucher_payload = payload.get("voucher")
    if voucher_payload is not None:
        return parse_voucher(voucher_payload)

    pack_payload = payload.get("pack")
    if pack_payload is not None:
        return parse_pack(pack_payload, fallback_index)

    return None


def shop_item_key(item: ObservedShopItem) -> str | None:
    if isinstance(item, ObservedCard):
        return item.card_key
    if isinstance(item, ObservedJoker):
        return item.key
    if isinstance(item, ObservedConsumable):
        return item.key
    if isinstance(item, ObservedVoucher):
        return item.key
    if isinstance(item, ObservedPack):
        return item.key
    return None


def merge_shop_vouchers_into_shop_items(*, shop_items: list[ObservedShopItem], shop_vouchers: list[ObservedShopItem]) -> list[ObservedShopItem]:
    if not shop_vouchers:
        return shop_items

    merged = list(shop_items)
    seen = {shop_item_key(item) for item in merged}

    for voucher in shop_vouchers:
        dedupe_key = shop_item_key(voucher)
        if dedupe_key in seen:
            continue
        merged.append(voucher)
        seen.add(dedupe_key)
    return merged

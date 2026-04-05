from __future__ import annotations

from ...models import ObservedShopItem
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
        card = parse_card(card_payload, fallback_index)
        if card is not None:
            return ObservedShopItem(card=card)
        return None

    joker_payload = payload.get("joker")
    if joker_payload is not None:
        joker = parse_joker(joker_payload, fallback_index)
        if joker is not None:
            return ObservedShopItem(joker=joker)
        return None

    consumable_payload = payload.get("consumable")
    if consumable_payload is not None:
        consumable = parse_consumable(consumable_payload, fallback_index)
        if consumable is not None:
            return ObservedShopItem(consumable=consumable)
        return None

    voucher_payload = payload.get("voucher")
    if voucher_payload is not None:
        voucher = parse_voucher(voucher_payload)
        if voucher is not None:
            return ObservedShopItem(voucher=voucher)
        return None

    pack_payload = payload.get("pack")
    if pack_payload is not None:
        pack = parse_pack(pack_payload, fallback_index)
        if pack is not None:
            return ObservedShopItem(pack=pack)
        return None

    return None


def merge_shop_vouchers_into_shop_items(*, shop_items: list[ObservedShopItem], shop_vouchers: list[ObservedShopItem]) -> list[ObservedShopItem]:
    if not shop_vouchers:
        return shop_items

    merged = list(shop_items)
    seen = {
        item.card.card_key if item.card is not None else None
        for item in merged
    }
    seen.update(item.joker.key if item.joker is not None else None for item in merged)
    seen.update(item.consumable.key if item.consumable is not None else None for item in merged)
    seen.update(item.voucher.key if item.voucher is not None else None for item in merged)
    seen.update(item.pack.key if item.pack is not None else None for item in merged)

    for voucher in shop_vouchers:
        dedupe_key = voucher.voucher.key if voucher.voucher is not None else None
        if dedupe_key in seen:
            continue
        merged.append(voucher)
        seen.add(dedupe_key)
    return merged

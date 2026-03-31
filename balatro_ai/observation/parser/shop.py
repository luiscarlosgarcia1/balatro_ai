from __future__ import annotations

import re

from ...models import ObservedShopItem
from .coercion import string_or_none
from .zones import parse_card, parse_consumable, parse_joker, parse_pack, parse_voucher

PLAYING_CARD_KEY_PATTERN = re.compile(r"^[cdhs]_[a2-9tjqk]$", re.IGNORECASE)


def _normalize_kind(value: object) -> str | None:
    kind = string_or_none(value)
    if not kind:
        return None
    return kind.strip().lower()


def _looks_like_playing_card(key: str | None) -> bool:
    if not key:
        return False
    return PLAYING_CARD_KEY_PATTERN.match(key) is not None


def _infer_shop_item_kind(item: dict[str, object]) -> str | None:
    kind = _normalize_kind(item.get("kind"))
    key = string_or_none(item.get("key", item.get("card_key")))

    if kind == "voucher" or (key and key.startswith("v_")):
        return "voucher"
    if kind == "pack" or (key and key.startswith("p_")):
        return "pack"
    if kind == "joker" or (key and key.startswith("j_")):
        return "joker"
    if kind in {"tarot", "planet", "spectral", "consumable"}:
        return "consumable"
    if _looks_like_playing_card(string_or_none(item.get("card_key"))) or _looks_like_playing_card(key):
        return "card"
    if key and key.startswith("c_"):
        return "consumable"
    return None


def parse_shop_items(payload: object) -> list[ObservedShopItem]:
    shop_items: list[ObservedShopItem] = []
    if not isinstance(payload, list):
        return shop_items

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        item_kind = _infer_shop_item_kind(item)
        if item_kind == "voucher":
            voucher = parse_voucher(item)
            if voucher is not None:
                shop_items.append(ObservedShopItem(voucher=voucher))
            continue
        if item_kind == "pack":
            pack = parse_pack(item, index)
            if pack is not None:
                shop_items.append(ObservedShopItem(pack=pack))
            continue
        if item_kind == "joker":
            joker = parse_joker(item, index)
            if joker is not None:
                shop_items.append(ObservedShopItem(joker=joker))
            continue
        if item_kind == "consumable":
            consumable = parse_consumable(item, index)
            if consumable is not None:
                shop_items.append(ObservedShopItem(consumable=consumable))
            continue
        if item_kind == "card":
            card = parse_card(item, index)
            if card is not None:
                shop_items.append(ObservedShopItem(card=card))
    return shop_items


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

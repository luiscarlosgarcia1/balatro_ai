from __future__ import annotations

from ...models import ObservedShopItem, ObservedVoucher
from .coercion import int_or_none, string_or_none


def parse_shop_items(payload: object) -> list[ObservedShopItem]:
    shop_items: list[ObservedShopItem] = []
    if not isinstance(payload, list):
        return shop_items

    for item in payload:
        if not isinstance(item, dict):
            continue
        kind = string_or_none(item.get("kind"))
        name = string_or_none(item.get("name"))
        key = string_or_none(item.get("key"))
        if not key and not name:
            continue
        stickers = item.get("stickers")
        shop_items.append(
            ObservedShopItem(
                kind=kind or "shop",
                name=name or key or "shop_item",
                key=key,
                cost=int_or_none(item.get("cost")),
                rarity=string_or_none(item.get("rarity")),
                edition=string_or_none(item.get("edition")),
                enhancement=string_or_none(item.get("enhancement")),
                seal=string_or_none(item.get("seal")),
                stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                debuffed=bool(item.get("debuffed", False)),
            )
        )
    return shop_items


def merge_shop_vouchers_into_shop_items(
    *,
    shop_items: list[ObservedShopItem],
    shop_vouchers: list[ObservedVoucher],
    interaction_phase: str,
) -> list[ObservedShopItem]:
    if interaction_phase != "shop" or not shop_vouchers:
        return shop_items

    merged = list(shop_items)
    seen = {item.key or item.name for item in merged}
    for voucher in shop_vouchers:
        dedupe_key = voucher.key
        if dedupe_key in seen:
            continue
        merged.append(
            ObservedShopItem(
                kind="voucher",
                name=voucher.key,
                key=voucher.key,
                cost=voucher.cost,
            )
        )
        seen.add(dedupe_key)
    return merged

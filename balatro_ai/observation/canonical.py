from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ..models import (
    GameObservation,
    ObservedBlind,
    ObservedCard,
    ObservedConsumable,
    ObservedJoker,
    ObservedShopDiscount,
    ObservedShopItem,
    ObservedSkipTag,
    ObservedTag,
    ObservedVoucher,
)


CANONICAL_TOP_LEVEL_KEYS = (
    "source",
    "state_id",
    "interaction_phase",
    "blind_key",
    "deck_key",
    "stake_id",
    "score",
    "money",
    "hands_left",
    "discards_left",
    "ante",
    "round_count",
    "joker_slots",
    "joker_count",
    "jokers",
    "consumable_slots",
    "consumables",
    "shop_vouchers",
    "vouchers",
    "skip_tags",
    "tags",
    "shop_items",
    "shop_discounts",
    "reroll_cost",
    "interest",
    "inflation",
    "pack_contents",
    "hand_size",
    "cards_in_hand",
    "selected_cards",
    "highlighted_card",
    "cards_in_deck",
    "blinds",
    "notes",
)

def serialize_observation(observation: GameObservation) -> dict[str, Any]:
    serialized_jokers = [_serialize_joker(joker) for joker in observation.jokers]
    serialized_consumables = [_serialize_consumable(consumable) for consumable in observation.consumables]
    serialized_shop_vouchers = [_serialize_voucher(voucher) for voucher in observation.shop_vouchers]
    serialized_vouchers = [_serialize_voucher(voucher) for voucher in observation.vouchers]
    serialized_tags = [_serialize_tag(tag) for tag in observation.tags]
    serialized_skip_tags = [_serialize_skip_tag(skip_tag) for skip_tag in observation.skip_tags]
    serialized_cards_in_hand = [_serialize_card(card) for card in observation.hand_cards]
    serialized_blinds = [_serialize_blind(blind) for blind in observation.blinds]
    serialized_shop_discounts = [_serialize_shop_discount(discount) for discount in observation.shop_discounts]

    payload: dict[str, Any] = {
        "source": observation.source,
        "state_id": observation.state_id,
        "interaction_phase": _normalize_machine_value(observation.interaction_phase),
        "blind_key": _normalize_machine_value(observation.blind_key),
        "deck_key": _normalize_machine_value(observation.deck_key),
        "stake_id": _normalize_machine_value(observation.stake_id),
        "score": {
            "current": observation.score_current,
            "target": observation.score_target,
        },
        "money": observation.money,
        "hands_left": observation.hands_left,
        "discards_left": observation.discards_left,
        "ante": observation.ante,
        "round_count": observation.round_count,
        "joker_slots": observation.joker_slots,
        "joker_count": observation.joker_count if observation.joker_count is not None else len(serialized_jokers),
        "jokers": serialized_jokers,
        "consumable_slots": observation.consumable_slots,
        "consumables": serialized_consumables,
        "shop_vouchers": serialized_shop_vouchers,
        "vouchers": serialized_vouchers,
        "skip_tags": serialized_skip_tags,
        "tags": serialized_tags,
        "shop_items": _serialize_shop_items(observation),
        "shop_discounts": serialized_shop_discounts,
        "reroll_cost": observation.reroll_cost,
        "interest": observation.interest,
        "inflation": observation.inflation,
        "pack_contents": None,
        "hand_size": observation.hand_size,
        "cards_in_hand": serialized_cards_in_hand,
        "selected_cards": [],
        "highlighted_card": None,
        "cards_in_deck": [],
        "blinds": serialized_blinds,
        "notes": _serialize_notes(observation.notes, observation.seen_at),
    }

    return {key: payload[key] for key in CANONICAL_TOP_LEVEL_KEYS}


def _serialize_joker(joker: ObservedJoker) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": _normalize_machine_value(joker.key),
    }
    if joker.rarity is not None:
        payload["rarity"] = _normalize_machine_value(joker.rarity)
    if joker.edition is not None:
        payload["edition"] = _normalize_machine_value(joker.edition)
    if joker.sell_price is not None:
        payload["sell_price"] = joker.sell_price
    if joker.debuffed:
        payload["debuffed"] = True
    if joker.stickers:
        payload["stickers"] = [_normalize_machine_value(sticker) for sticker in joker.stickers]
    return payload


def _serialize_consumable(consumable: ObservedConsumable) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(consumable.kind),
        "key": _normalize_machine_value(consumable.key),
    }
    if consumable.edition is not None:
        payload["edition"] = _normalize_machine_value(consumable.edition)
    if consumable.sell_price is not None:
        payload["sell_price"] = consumable.sell_price
    if consumable.debuffed:
        payload["debuffed"] = True
    if consumable.stickers:
        payload["stickers"] = [_normalize_machine_value(sticker) for sticker in consumable.stickers]
    if consumable.cost is not None:
        payload["cost"] = consumable.cost
    return payload


def _serialize_voucher(voucher: ObservedVoucher) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": _normalize_machine_value(voucher.key),
    }
    if voucher.cost is not None:
        payload["cost"] = voucher.cost
    return payload


def _serialize_tag(tag: ObservedTag) -> dict[str, Any]:
    return {
        "key": _normalize_machine_value(tag.key),
    }


def _serialize_skip_tag(tag: ObservedSkipTag) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slot": _normalize_machine_value(tag.slot),
        "key": _normalize_machine_value(tag.key),
    }
    if tag.claimed:
        payload["claimed"] = True
    return payload


def _serialize_card(card: ObservedCard) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "card_key": _normalize_machine_value(card.code),
        "name": card.name,
    }
    if card.enhancement is not None:
        payload["enhancement"] = _normalize_machine_value(card.enhancement)
    if card.edition is not None:
        payload["edition"] = _normalize_machine_value(card.edition)
    if card.seal is not None:
        payload["seal"] = _normalize_machine_value(card.seal)
    if card.facing is not None:
        payload["facing"] = _normalize_machine_value(card.facing)
    if card.debuffed:
        payload["debuffed"] = True
    if card.modifiers:
        payload["modifiers"] = list(card.modifiers)
    return payload


def _serialize_blind(blind: ObservedBlind) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slot": _normalize_machine_value(blind.slot),
        "key": _normalize_machine_value(blind.key),
        "state": _normalize_machine_value(blind.state),
    }
    if blind.tag_key is not None:
        payload["tag_key"] = _normalize_machine_value(blind.tag_key)
    if blind.tag_claimed:
        payload["tag_claimed"] = True
    return payload


def _serialize_shop_items(observation: GameObservation) -> list[dict[str, Any]]:
    return [_serialize_shop_item(item) for item in observation.shop_items]


def _serialize_shop_item(item: ObservedShopItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(item.kind),
        "name": item.name,
        "key": _normalize_machine_value(item.key),
    }
    if item.cost is not None:
        payload["cost"] = item.cost
    if item.rarity is not None:
        payload["rarity"] = _normalize_machine_value(item.rarity)
    if item.edition is not None:
        payload["edition"] = _normalize_machine_value(item.edition)
    if item.sell_price is not None:
        payload["sell_price"] = item.sell_price
    if item.enhancement is not None:
        payload["enhancement"] = _normalize_machine_value(item.enhancement)
    if item.seal is not None:
        payload["seal"] = _normalize_machine_value(item.seal)
    if item.consumable_kind is not None:
        payload["consumable_kind"] = _normalize_machine_value(item.consumable_kind)
    if item.stickers:
        payload["stickers"] = [_normalize_machine_value(sticker) for sticker in item.stickers]
    if item.debuffed:
        payload["debuffed"] = True
    if item.card_key is not None:
        payload["card_key"] = _normalize_machine_value(item.card_key)
    if item.card_kind is not None:
        payload["card_kind"] = _normalize_machine_value(item.card_kind)
    if item.suit is not None:
        payload["suit"] = _normalize_machine_value(item.suit)
    if item.rank is not None:
        payload["rank"] = _normalize_machine_value(item.rank)
    if item.pack_key is not None:
        payload["pack_key"] = _normalize_machine_value(item.pack_key)
    if item.pack_kind is not None:
        payload["pack_kind"] = _normalize_machine_value(item.pack_kind)
    return payload


def _serialize_shop_discount(discount: ObservedShopDiscount) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(discount.kind),
    }
    if discount.value is not None:
        payload["value"] = discount.value
    return payload


def _serialize_notes(notes: tuple[str, ...], seen_at: datetime | None) -> list[str]:
    values = [str(note) for note in notes]
    if seen_at is not None:
        values.append(f"seen_at={seen_at.isoformat()}")
    return values


def _normalize_machine_value(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    text = str(value).strip()
    if not text:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return normalized or None

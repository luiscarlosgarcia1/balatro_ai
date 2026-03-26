from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ..models import (
    GameObservation,
    ObservedBlindChoice,
    ObservedBoosterPack,
    ObservedCard,
    ObservedConsumable,
    ObservedJoker,
    ObservedShopItem,
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

_CANONICAL_PHASES = {"shop", "blind_select", "play_hand", "pack_reward"}


def serialize_observation(observation: GameObservation) -> dict[str, Any]:
    # Transitional legacy bridge: the internal GameObservation shape is still legacy-oriented in places.
    # This serializer is the only public rewrite point until later phases remove those legacy fields.
    serialized_jokers = _serialize_jokers(observation)
    serialized_consumables = [
        _serialize_consumable(consumable) for consumable in observation.consumables_inventory
    ]
    serialized_vouchers = [_serialize_voucher(voucher) for voucher in observation.vouchers]
    serialized_tags = [_serialize_tag(tag) for tag in observation.tags]
    serialized_skip_tags = (
        [_serialize_tag(observation.skip_tag)] if observation.skip_tag is not None else []
    )
    serialized_cards_in_hand = [_serialize_card(card) for card in observation.hand_cards]
    serialized_blinds = [_serialize_blind_choice(choice) for choice in observation.blind_choices]

    payload: dict[str, Any] = {
        "source": observation.source,
        "state_id": observation.state_id,
        "interaction_phase": _canonical_interaction_phase(observation),
        "blind_key": _normalize_machine_value(observation.blind_key),
        "deck_key": _normalize_machine_value(observation.deck_key),
        "stake_id": _normalize_machine_value(observation.stake),
        "score": {
            "current": observation.current_score,
            "target": observation.score_to_beat,
        },
        "money": observation.money,
        "hands_left": observation.hands_left,
        "discards_left": observation.discards_left,
        "ante": observation.ante,
        "round_count": observation.round_count,
        "joker_slots": None,
        "joker_count": observation.jokers_count if observation.jokers_count is not None else len(serialized_jokers),
        "jokers": serialized_jokers,
        "consumable_slots": observation.consumable_capacity,
        "consumables": serialized_consumables,
        "shop_vouchers": [],
        "vouchers": serialized_vouchers,
        "skip_tags": serialized_skip_tags,
        "tags": serialized_tags,
        "shop_items": _serialize_shop_items(observation),
        "shop_discounts": [],
        "reroll_cost": observation.reroll_cost,
        "interest": None,
        "inflation": None,
        "pack_contents": None,
        "hand_size": None,
        "cards_in_hand": serialized_cards_in_hand,
        "selected_cards": [],
        "highlighted_card": None,
        "cards_in_deck": [],
        "blinds": serialized_blinds,
        "notes": _serialize_notes(observation.notes, observation.seen_at),
    }

    return {key: payload[key] for key in CANONICAL_TOP_LEVEL_KEYS}


def _serialize_jokers(observation: GameObservation) -> list[dict[str, Any]]:
    if observation.joker_details:
        return [_serialize_joker(joker) for joker in observation.joker_details]
    return [{"name": name} for name in observation.jokers]


def _serialize_joker(joker: ObservedJoker) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": joker.name,
        "key": _normalize_machine_value(joker.key),
    }
    if joker.edition is not None:
        payload["edition"] = _normalize_machine_value(joker.edition)
    if joker.debuffed:
        payload["debuffed"] = True
    if joker.modifiers:
        payload["modifiers"] = list(joker.modifiers)
    return payload


def _serialize_consumable(consumable: ObservedConsumable) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(consumable.kind),
        "name": consumable.name,
        "key": _normalize_machine_value(consumable.key),
    }
    if consumable.cost is not None:
        payload["cost"] = consumable.cost
    return payload


def _serialize_voucher(voucher: ObservedVoucher) -> dict[str, Any]:
    return {
        "name": voucher.name,
        "key": _normalize_machine_value(voucher.key),
    }


def _serialize_tag(tag: ObservedTag) -> dict[str, Any]:
    return {
        "name": tag.name,
        "key": _normalize_machine_value(tag.key or tag.name),
    }


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


def _serialize_blind_choice(choice: ObservedBlindChoice) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slot": _normalize_machine_value(choice.slot),
        "key": _normalize_machine_value(choice.key),
    }
    if choice.state is not None:
        payload["state"] = _normalize_machine_value(choice.state)
    if choice.tag is not None:
        payload["tag"] = _normalize_machine_value(choice.tag)
    return payload


def _serialize_shop_items(observation: GameObservation) -> list[dict[str, Any]]:
    # Transitional legacy bridge: current live input still splits packs out as `shop_packs`.
    # Phase 1 folds that legacy input into canonical `shop_items`; later slices can delete this bridge.
    shop_items = [_serialize_shop_item(item) for item in observation.shop_items]
    shop_items.extend(_serialize_shop_pack(pack) for pack in observation.shop_packs)
    return shop_items


def _serialize_shop_item(item: ObservedShopItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(item.kind),
        "name": item.name,
        "key": _normalize_machine_value(item.key),
    }
    if item.cost is not None:
        payload["cost"] = item.cost
    return payload


def _serialize_shop_pack(pack: ObservedBoosterPack) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": _normalize_machine_value(pack.kind),
        "name": pack.name,
        "key": _normalize_machine_value(pack.key),
    }
    if pack.cost is not None:
        payload["cost"] = pack.cost
    return payload


def _serialize_notes(notes: tuple[str, ...], seen_at: datetime | None) -> list[str]:
    values = [str(note) for note in notes]
    if seen_at is not None:
        values.append(f"seen_at={seen_at.isoformat()}")
    return values


def _canonical_interaction_phase(observation: GameObservation) -> str | None:
    primary = _normalize_machine_value(observation.interaction_phase)
    phase = _normalize_machine_value(observation.phase)
    # Transitional legacy bridge: legacy inputs still carry the main gameplay state in `phase`.
    # Keep rewriting it here until parsers/exporter stop producing that field.
    if primary in _CANONICAL_PHASES:
        return primary
    if phase in _CANONICAL_PHASES:
        return phase
    if phase is not None:
        return phase
    return primary


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

from __future__ import annotations

import zlib
from typing import Any, Iterable, Mapping, TYPE_CHECKING

import numpy as np
from gymnasium import spaces

from balatro_gym.core.constants import Action, ActionCounts, Phase
from balatro_gym.core.consumables import is_planet_consumable_name, is_spectral_consumable_name, is_tarot_consumable_name
from balatro_gym.scoring.scoring_engine import HandType

if TYPE_CHECKING:
    from balatro_gym.core_utils.state import UnifiedGameState


MVP_HAND_LEVEL_ORDER: tuple[HandType, ...] = (
    HandType.HIGH_CARD,
    HandType.ONE_PAIR,
    HandType.TWO_PAIR,
    HandType.THREE_KIND,
    HandType.STRAIGHT,
    HandType.FLUSH,
    HandType.FULL_HOUSE,
    HandType.FOUR_KIND,
    HandType.STRAIGHT_FLUSH,
    HandType.FIVE_KIND,
    HandType.FLUSH_HOUSE,
    HandType.FLUSH_FIVE,
)

MVP_HAND_LEVEL_LABELS: dict[HandType, str] = {
    HandType.HIGH_CARD: "High Card",
    HandType.ONE_PAIR: "Pair",
    HandType.TWO_PAIR: "Two Pair",
    HandType.THREE_KIND: "Three of a Kind",
    HandType.STRAIGHT: "Straight",
    HandType.FLUSH: "Flush",
    HandType.FULL_HOUSE: "Full House",
    HandType.FOUR_KIND: "Four of a Kind",
    HandType.STRAIGHT_FLUSH: "Straight Flush",
    HandType.FIVE_KIND: "Five of a Kind",
    HandType.FLUSH_HOUSE: "Flush House",
    HandType.FLUSH_FIVE: "Flush Five",
}

MVP_CONSUMABLE_ID_MAP: dict[str, int] = {
    "The Fool": 1,
    "The Magician": 2,
    "The High Priestess": 3,
    "The Empress": 4,
    "The Emperor": 5,
    "The Hierophant": 6,
    "The Lovers": 7,
    "The Chariot": 8,
    "Strength": 9,
    "The Hermit": 10,
    "Wheel of Fortune": 11,
    "Justice": 12,
    "The Hanged Man": 13,
    "Death": 14,
    "Temperance": 15,
    "The Devil": 16,
    "The Tower": 17,
    "The Star": 18,
    "The Moon": 19,
    "The Sun": 20,
    "Judgement": 21,
    "The World": 22,
    "Mercury": 30,
    "Venus": 31,
    "Earth": 32,
    "Mars": 33,
    "Jupiter": 34,
    "Saturn": 35,
    "Uranus": 36,
    "Neptune": 37,
    "Pluto": 38,
    "Planet X": 39,
    "Ceres": 40,
    "Eris": 41,
    "Familiar": 50,
    "Grim": 51,
    "Incantation": 52,
    "Talisman": 53,
    "Aura": 54,
    "Wraith": 55,
    "Sigil": 56,
    "Ouija": 57,
    "Ectoplasm": 58,
    "Immolate": 59,
    "Ankh": 60,
    "Deja Vu": 61,
    "Hex": 62,
    "Trance": 63,
    "Medium": 64,
    "Cryptid": 65,
    "The Soul": 66,
    "Black Hole": 67,
}

SHOP_ITEM_TYPE_IDS: dict[str, int] = {
    "JOKER": 1,
    "TAROT": 2,
    "PLANET": 3,
    "SPECTRAL": 4,
    "VOUCHER": 5,
    "BOOSTER": 6,
    "PLAYING": 7,
}

PACK_IMMEDIATE_PLANETS: frozenset[str] = frozenset(
    {
        "Mercury",
        "Venus",
        "Earth",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
        "Planet X",
        "Ceres",
        "Eris",
    }
)

PACK_IMMEDIATE_TAROTS: frozenset[str] = frozenset(
    {
        "The Fool",
        "The High Priestess",
        "The Emperor",
        "The Hermit",
        "Temperance",
        "Judgement",
    }
)

PACK_IMMEDIATE_SPECTRALS: frozenset[str] = frozenset(
    {
        "Wraith",
        "Ectoplasm",
        "Immolate",
        "The Soul",
        "Black Hole",
    }
)

PACK_TARGETED_MIN_HAND_SIZE: dict[str, int] = {
    "The Magician": 1,
    "The Empress": 1,
    "The Hierophant": 1,
    "The Lovers": 1,
    "The Chariot": 1,
    "Strength": 1,
    "Justice": 1,
    "Death": 2,
    "The Devil": 1,
    "The Tower": 1,
    "The Star": 1,
    "The Moon": 1,
    "The Sun": 1,
    "The World": 1,
    "Aura": 1,
    "Talisman": 1,
    "Deja Vu": 1,
    "Trance": 1,
    "Medium": 1,
}

PACK_TARGETED_DEFAULT_TARGET_COUNT: dict[str, int] = {
    "The Magician": 2,
    "The Empress": 2,
    "The Hierophant": 2,
    "The Lovers": 1,
    "The Chariot": 1,
    "Strength": 2,
    "Justice": 1,
    "Death": 2,
    "The Devil": 1,
    "The Tower": 1,
    "The Star": 3,
    "The Moon": 3,
    "The Sun": 3,
    "The World": 3,
    "Aura": 1,
    "Talisman": 1,
    "Deja Vu": 1,
    "Trance": 1,
    "Medium": 1,
}


def create_mvp_observation_space() -> spaces.Dict:
    return spaces.Dict(
        {
            "hand": spaces.Box(-1, 51, (8,), dtype=np.int8),
            "hand_size": spaces.Box(0, 12, (), dtype=np.int8),
            "deck_size": spaces.Box(0, 52, (), dtype=np.int8),
            "selected_cards": spaces.MultiBinary(8),
            "chips_scored": spaces.Box(0, 10_000_000_000, (), dtype=np.int64),
            "round_chips_scored": spaces.Box(0, 10_000_000, (), dtype=np.int32),
            "progress_ratio": spaces.Box(0.0, 2.0, (), dtype=np.float32),
            "mult": spaces.Box(0, 10_000, (), dtype=np.int32),
            "chips_needed": spaces.Box(0, 10_000_000, (), dtype=np.int32),
            "money": spaces.Box(-20, 999, (), dtype=np.int32),
            "ante": spaces.Box(1, 1000, (), dtype=np.int16),
            "round": spaces.Box(1, 3, (), dtype=np.int8),
            "hands_left": spaces.Box(0, 12, (), dtype=np.int8),
            "discards_left": spaces.Box(0, 10, (), dtype=np.int8),
            "joker_count": spaces.Box(0, 10, (), dtype=np.int8),
            "joker_ids": spaces.Box(0, 200, (10,), dtype=np.int16),
            "joker_slots": spaces.Box(0, 10, (), dtype=np.int8),
            "consumable_count": spaces.Box(0, 5, (), dtype=np.int8),
            "consumables": spaces.Box(0, 100, (5,), dtype=np.int16),
            "consumable_slots": spaces.Box(0, 5, (), dtype=np.int8),
            "shop_items": spaces.Box(0, 300, (10,), dtype=np.int16),
            "shop_costs": spaces.Box(0, 5000, (10,), dtype=np.int16),
            "shop_rerolls": spaces.Box(0, 999, (), dtype=np.int16),
            "pack_item_types": spaces.Box(0, 7, (ActionCounts.SELECT_FROM_PACK_COUNT,), dtype=np.int8),
            "pack_item_ids": spaces.Box(0, 500, (ActionCounts.SELECT_FROM_PACK_COUNT,), dtype=np.int16),
            "pack_item_selectable": spaces.MultiBinary(ActionCounts.SELECT_FROM_PACK_COUNT),
            "pack_cards_to_select": spaces.Box(0, ActionCounts.SELECT_FROM_PACK_COUNT, (), dtype=np.int8),
            "pack_choices_remaining": spaces.Box(0, ActionCounts.SELECT_FROM_PACK_COUNT, (), dtype=np.int8),
            "fool_replayable_consumable": spaces.Box(0, 100, (), dtype=np.int16),
            "hand_levels": spaces.Box(0, 15, (12,), dtype=np.int8),
            "phase": spaces.Box(0, 3, (), dtype=np.int8),
            "action_mask": spaces.MultiBinary(ActionCounts.ACTION_SPACE_SIZE),
            "hands_played": spaces.Box(0, 10000, (), dtype=np.int32),
            "best_hand_this_ante": spaces.Box(0, 10_000_000, (), dtype=np.int32),
            "boss_blind_active": spaces.Box(0, 1, (), dtype=np.int8),
            "boss_blind_type": spaces.Box(0, 30, (), dtype=np.int8),
            "face_down_cards": spaces.MultiBinary(8),
            "rank_counts": spaces.Box(0, 4, (13,), dtype=np.int8),
            "suit_counts": spaces.Box(0, 8, (4,), dtype=np.int8),
            "straight_potential": spaces.Box(0, 1, (), dtype=np.float32),
            "flush_potential": spaces.Box(0, 1, (), dtype=np.float32),
        }
    )


def build_mvp_action_mask(state: UnifiedGameState, shop: Any = None) -> np.ndarray:
    mask = np.zeros(ActionCounts.ACTION_SPACE_SIZE, dtype=np.int8)
    phase = Phase(int(state.phase))

    if phase == Phase.PLAY:
        selected_count = len(state.selected_cards)
        for i in range(min(ActionCounts.SELECT_CARD_COUNT, len(state.hand_indexes))):
            mask[Action.SELECT_CARD_BASE + i] = 1
        if 0 < selected_count <= 5:
            mask[Action.PLAY_HAND] = 1
        if selected_count > 0 and state.discards_left > 0:
            mask[Action.DISCARD] = 1
        for i in range(min(ActionCounts.USE_CONSUMABLE_COUNT, len(state.consumables))):
            if can_use_consumable_in_play(state, str(state.consumables[i])):
                mask[Action.USE_CONSUMABLE_BASE + i] = 1
        return mask

    if phase == Phase.SHOP:
        for i, item in enumerate(get_shop_inventory(state, shop)[: ActionCounts.SHOP_BUY_COUNT]):
            cost = get_shop_item_cost(item)
            if cost is not None and state.money >= cost and is_shop_item_buyable(state, item):
                mask[Action.SHOP_BUY_BASE + i] = 1

        if state.money >= state.shop_reroll_cost:
            mask[Action.SHOP_REROLL] = 1

        mask[Action.SHOP_END] = 1

        eternal_jokers = set(getattr(state, "eternal_jokers", []))
        for i in range(min(ActionCounts.SELL_JOKER_COUNT, len(state.jokers))):
            if i not in eternal_jokers:
                mask[Action.SELL_JOKER_BASE + i] = 1

        for i in range(min(ActionCounts.SELL_CONSUMABLE_COUNT, len(state.consumables))):
            mask[Action.SELL_CONSUMABLE_BASE + i] = 1
        return mask

    if phase == Phase.BLIND_SELECT:
        visible_slot = max(0, min(ActionCounts.SELECT_BLIND_COUNT - 1, int(state.round) - 1))
        mask[Action.SELECT_BLIND_BASE + visible_slot] = 1
        if visible_slot < ActionCounts.SELECT_BLIND_COUNT - 1:
            mask[Action.SKIP_BLIND] = 1
        if visible_slot == ActionCounts.SELECT_BLIND_COUNT - 1 and can_reroll_pending_boss_blind(state):
            mask[Action.REROLL_BOSS_BLIND] = 1
        return mask

    if phase == Phase.PACK_OPEN:
        pack_contents = get_pack_contents(state, shop)
        selected_indexes = set(get_pack_selected_indexes(state, shop))
        cards_to_select = get_pack_cards_to_select(state, shop)
        pending_pack_index = get_pending_pack_index(state, shop)
        pending_target_count = get_pending_pack_target_count(state, shop)
        pending_target_valid = has_valid_pending_pack_targets(state, shop)

        if pending_pack_index is not None:
            for i in range(min(ActionCounts.SELECT_CARD_COUNT, len(state.hand_indexes))):
                mask[Action.SELECT_CARD_BASE + i] = 1
            if (
                0 <= pending_pack_index < min(ActionCounts.SELECT_FROM_PACK_COUNT, len(pack_contents))
                and pending_target_count > 0
                and pending_target_valid
            ):
                mask[Action.SELECT_FROM_PACK_BASE + pending_pack_index] = 1
        elif len(selected_indexes) < cards_to_select:
            for i in range(min(ActionCounts.SELECT_FROM_PACK_COUNT, len(pack_contents))):
                if i not in selected_indexes and is_pack_item_selectable(state, pack_contents[i], item_index=i):
                    mask[Action.SELECT_FROM_PACK_BASE + i] = 1

        if pack_contents:
            mask[Action.SKIP_PACK] = 1
        return mask

    return mask


def get_visible_boss_blind(state: UnifiedGameState):
    """Return the boss blind currently visible to the policy."""
    if state.phase == Phase.PLAY and state.active_boss_blind is not None:
        return state.active_boss_blind
    if state.phase in {Phase.BLIND_SELECT, Phase.SHOP}:
        return state.pending_boss_blind
    return None


def can_reroll_pending_boss_blind(state: UnifiedGameState) -> bool:
    """Return whether a boss reroll action should be available."""
    if state.phase != Phase.BLIND_SELECT or int(state.round) != 3:
        return False
    if state.pending_boss_blind is None or state.money < 10:
        return False

    has_directors_cut = "Director's Cut" in state.vouchers
    has_retcon = "Retcon" in state.vouchers
    if not has_directors_cut and not has_retcon:
        return False
    if has_retcon:
        return True
    return int(getattr(state, "boss_blind_rerolls_used_ante", 0) or 0) == 0


def encode_joker_ids(jokers: Iterable[Any], slots: int = 10) -> np.ndarray:
    ids = [encode_joker_id(joker) for joker in jokers]
    return np.array((ids + [0] * max(0, slots - len(ids)))[:slots], dtype=np.int16)


def encode_joker_id(joker: Any) -> int:
    if joker is None:
        return 0

    if isinstance(joker, str) and joker:
        return _stable_text_id(joker, modulus=200)

    for key in ("key", "name", "label"):
        value = _get_string_value(joker, key)
        if value:
            return _stable_text_id(value, modulus=200)

    joker_id = getattr(joker, "id", None)
    if joker_id is None and isinstance(joker, dict):
        joker_id = joker.get("id")
    if joker_id is not None:
        try:
            return max(0, min(200, int(joker_id)))
        except (TypeError, ValueError):
            pass

    return 0


def encode_consumable_ids(consumables: Iterable[Any], slots: int = 5) -> np.ndarray:
    ids = [encode_consumable_id(consumable) for consumable in consumables]
    return np.array((ids + [0] * max(0, slots - len(ids)))[:slots], dtype=np.int16)


def encode_consumable_id(consumable: Any) -> int:
    if consumable is None:
        return 0

    if isinstance(consumable, str):
        return MVP_CONSUMABLE_ID_MAP.get(consumable, 0)

    for key in ("label", "name", "consumable"):
        value = _get_string_value(consumable, key)
        if value:
            return MVP_CONSUMABLE_ID_MAP.get(value, 0)

    return 0


def encode_hand_levels(levels: Mapping[Any, Any] | None, default_level: int = 1) -> np.ndarray:
    hand_levels = levels or {}
    ordered_levels: list[int] = []

    for hand_type in MVP_HAND_LEVEL_ORDER:
        raw_value = default_level
        for key in (
            hand_type,
            hand_type.name,
            MVP_HAND_LEVEL_LABELS[hand_type],
            MVP_HAND_LEVEL_LABELS[hand_type].replace(" ", "_").upper(),
        ):
            if key in hand_levels:
                raw_value = hand_levels[key]
                break

        try:
            normalized_level = int(raw_value)
        except (TypeError, ValueError):
            normalized_level = default_level

        ordered_levels.append(max(0, min(15, normalized_level)))

    return np.array(ordered_levels, dtype=np.int8)


def encode_pack_item_types(
    pack_contents: Iterable[Any],
    slots: int = ActionCounts.SELECT_FROM_PACK_COUNT,
) -> np.ndarray:
    ids = [get_pack_item_type_id(item) for item in pack_contents]
    return np.array((ids + [0] * max(0, slots - len(ids)))[:slots], dtype=np.int8)


def encode_pack_item_ids(
    pack_contents: Iterable[Any],
    slots: int = ActionCounts.SELECT_FROM_PACK_COUNT,
) -> np.ndarray:
    ids = [encode_pack_item_id(item) for item in pack_contents]
    return np.array((ids + [0] * max(0, slots - len(ids)))[:slots], dtype=np.int16)


def encode_fool_replayable_consumable(state: UnifiedGameState) -> np.int16:
    remembered = getattr(state, "last_tarot_planet_consumable", None)
    if not remembered or remembered == "The Fool":
        return np.int16(0)
    return np.int16(encode_consumable_id(remembered))


def build_action_mask(
    state: UnifiedGameState | None = None,
    shop: Any = None,
    **kwargs: Any,
) -> np.ndarray:
    if state is not None:
        return build_mvp_action_mask(state, shop)

    phase = Phase(int(kwargs["phase"]))
    mask = np.zeros(ActionCounts.ACTION_SPACE_SIZE, dtype=np.int8)

    if phase == Phase.PLAY:
        hand_size = int(kwargs["hand_size"])
        selected_cards = list(kwargs["selected_cards"])
        discards_left = int(kwargs["discards_left"])
        consumable_count = int(kwargs["consumable_count"])
        for i in range(min(ActionCounts.SELECT_CARD_COUNT, hand_size)):
            mask[Action.SELECT_CARD_BASE + i] = 1
        if 0 < len(selected_cards) <= 5:
            mask[Action.PLAY_HAND] = 1
        if selected_cards and discards_left > 0:
            mask[Action.DISCARD] = 1
        for i in range(min(ActionCounts.USE_CONSUMABLE_COUNT, consumable_count)):
            mask[Action.USE_CONSUMABLE_BASE + i] = 1
        return mask

    if phase == Phase.SHOP:
        for i, (cost, can_buy) in enumerate(list(kwargs["shop_items"])[: ActionCounts.SHOP_BUY_COUNT]):
            normalized_cost = 0 if cost is None else int(cost)
            if can_buy and int(kwargs["money"]) >= normalized_cost:
                mask[Action.SHOP_BUY_BASE + i] = 1
        if int(kwargs["money"]) >= int(kwargs["shop_reroll_cost"]):
            mask[Action.SHOP_REROLL] = 1
        mask[Action.SHOP_END] = 1
        for i in range(min(ActionCounts.SELL_JOKER_COUNT, int(kwargs["joker_count"]))):
            mask[Action.SELL_JOKER_BASE + i] = 1
        for i in range(min(ActionCounts.SELL_CONSUMABLE_COUNT, int(kwargs["sellable_consumable_count"]))):
            mask[Action.SELL_CONSUMABLE_BASE + i] = 1
        return mask

    if phase == Phase.BLIND_SELECT:
        for slot in kwargs["blind_selectable_slots"]:
            slot_index = int(slot)
            if 0 <= slot_index < ActionCounts.SELECT_BLIND_COUNT:
                mask[Action.SELECT_BLIND_BASE + slot_index] = 1
        if kwargs["can_skip_blind"]:
            mask[Action.SKIP_BLIND] = 1
        if kwargs.get("can_reroll_boss_blind"):
            mask[Action.REROLL_BOSS_BLIND] = 1
        return mask

    if phase == Phase.PACK_OPEN:
        pack_size = int(kwargs["pack_size"])
        selected_indexes = {int(idx) for idx in kwargs["pack_selected_indexes"]}
        cards_to_select = int(kwargs["pack_cards_to_select"])
        item_selectable = list(kwargs.get("pack_item_selectable", [True] * pack_size))
        pending_pack_index = kwargs.get("pending_pack_index")
        pending_target_count = int(kwargs.get("pending_target_count", 0) or 0)
        pending_target_valid = bool(kwargs.get("pending_target_valid", False))
        if pending_pack_index is not None:
            hand_size = int(kwargs.get("hand_size", 0))
            for i in range(min(ActionCounts.SELECT_CARD_COUNT, hand_size)):
                mask[Action.SELECT_CARD_BASE + i] = 1
            pending_pack_index = int(pending_pack_index)
            if (
                0 <= pending_pack_index < min(ActionCounts.SELECT_FROM_PACK_COUNT, pack_size)
                and pending_target_count > 0
                and pending_target_valid
            ):
                mask[Action.SELECT_FROM_PACK_BASE + pending_pack_index] = 1
        elif len(selected_indexes) < cards_to_select:
            for i in range(min(ActionCounts.SELECT_FROM_PACK_COUNT, pack_size)):
                if i not in selected_indexes and (i >= len(item_selectable) or bool(item_selectable[i])):
                    mask[Action.SELECT_FROM_PACK_BASE + i] = 1
        if pack_size > 0:
            mask[Action.SKIP_PACK] = 1
        return mask

    return mask


def encode_joker_tokens(jokers: Iterable[Any], slots: int = 10) -> np.ndarray:
    return encode_joker_ids(jokers, slots=slots)


def encode_consumables(consumables: Iterable[Any], slots: int = 5) -> np.ndarray:
    return encode_consumable_ids(consumables, slots=slots)


def ordered_hand_levels(levels: Mapping[Any, Any] | None, default_level: int = 1) -> np.ndarray:
    return encode_hand_levels(levels, default_level=default_level)


def get_shop_inventory(state: UnifiedGameState, shop: Any = None) -> list[Any]:
    inventory = getattr(state, "shop_inventory", None)
    if inventory:
        return list(inventory)

    inventory = getattr(shop, "inventory", None)
    if inventory:
        return list(inventory)

    return []


def get_shop_item_cost(item: Any) -> int | None:
    cost = getattr(item, "cost", None)
    if cost is None and isinstance(item, dict):
        cost = item.get("cost")
    if cost is None:
        return None

    try:
        return int(cost)
    except (TypeError, ValueError):
        return None


def is_shop_item_buyable(state: UnifiedGameState, item: Any) -> bool:
    item_type_name = getattr(getattr(item, "item_type", None), "name", None)
    payload = getattr(item, "payload", {}) or {}

    if isinstance(item, dict):
        item_type_name = item.get("item_type", item_type_name)
        payload = item.get("payload", payload) or {}

    if item_type_name == "JOKER" and len(state.jokers) >= state.joker_slots:
        return False
    if item_type_name == "CARD" and isinstance(payload, dict) and payload.get("consumable"):
        if len(state.consumables) >= state.consumable_slots:
            return False
    return True


def get_pack_contents(state: UnifiedGameState, shop: Any = None) -> list[Any]:
    return _get_first_list_like(
        (state, shop),
        (
            "pack_contents",
            "current_pack_contents",
            "pack_items",
            "pack_cards",
            "pack_choices",
        ),
    )


def get_pack_selected_indexes(state: UnifiedGameState, shop: Any = None) -> list[int]:
    return _get_first_list_like(
        (state, shop),
        (
            "selected_indexes",
            "pack_selected_indexes",
            "selected_pack_indexes",
        ),
    )


def get_pack_cards_to_select(state: UnifiedGameState, shop: Any = None) -> int:
    for owner in (state, shop):
        if owner is None:
            continue
        for attr in ("cards_to_select", "pack_cards_to_select", "pack_selection_limit"):
            value = getattr(owner, attr, None)
            if value is not None:
                try:
                    return max(0, int(value))
                except (TypeError, ValueError):
                    return 1
    return 1


def get_shop_item_type_id(item: Any) -> int:
    item_type = getattr(item, "item_type", None)
    payload = getattr(item, "payload", {}) or {}
    if isinstance(item, dict):
        item_type = item.get("item_type", item_type)
        payload = item.get("payload", payload) or {}

    item_type_name = getattr(item_type, "name", item_type)
    if item_type_name == "PACK":
        return SHOP_ITEM_TYPE_IDS["BOOSTER"]
    if item_type_name == "JOKER":
        return SHOP_ITEM_TYPE_IDS["JOKER"]
    if item_type_name == "VOUCHER":
        return SHOP_ITEM_TYPE_IDS["VOUCHER"]
    if item_type_name == "CARD":
        offer_set = payload.get("offer_set") or payload.get("consumable_type")
        if offer_set == "Tarot":
            return SHOP_ITEM_TYPE_IDS["TAROT"]
        if offer_set == "Planet":
            return SHOP_ITEM_TYPE_IDS["PLANET"]
        if offer_set == "Spectral":
            return SHOP_ITEM_TYPE_IDS["SPECTRAL"]
        return SHOP_ITEM_TYPE_IDS["PLAYING"]
    if isinstance(item_type_name, str):
        return SHOP_ITEM_TYPE_IDS.get(item_type_name.upper(), 0)
    return 0


def get_pack_item_type_id(item: Any) -> int:
    normalized_type, _, _ = _normalize_pack_item(item)
    if normalized_type == "consumable":
        consumable_name = _get_pack_consumable_name(item)
        if consumable_name:
            if is_tarot_consumable_name(consumable_name):
                return SHOP_ITEM_TYPE_IDS["TAROT"]
            if is_planet_consumable_name(consumable_name):
                return SHOP_ITEM_TYPE_IDS["PLANET"]
            if is_spectral_consumable_name(consumable_name):
                return SHOP_ITEM_TYPE_IDS["SPECTRAL"]
        return SHOP_ITEM_TYPE_IDS["PLAYING"]
    if normalized_type == "joker":
        return SHOP_ITEM_TYPE_IDS["JOKER"]
    if normalized_type == "card":
        return SHOP_ITEM_TYPE_IDS["PLAYING"]
    return 0


def encode_pack_item_id(item: Any) -> int:
    normalized_type, primary_value, fallback_label = _normalize_pack_item(item)
    if normalized_type == "consumable":
        encoded = encode_consumable_id(primary_value)
        if encoded:
            return encoded
    elif normalized_type == "joker":
        encoded = encode_joker_id(primary_value)
        if encoded:
            return min(500, 200 + encoded)
    elif normalized_type == "card":
        encoded = _encode_standard_card_id(primary_value)
        if encoded:
            return min(500, 300 + encoded)

    if fallback_label:
        return min(500, _stable_text_id(fallback_label, modulus=499))
    return 0


def is_pack_item_selectable(state: UnifiedGameState, item: Any, item_index: int | None = None) -> bool:
    pending_pack_index = get_pending_pack_index(state)
    if pending_pack_index is not None:
        return item_index is not None and item_index == pending_pack_index

    normalized_type, primary_value, _ = _normalize_pack_item(item)
    if normalized_type == "consumable" and primary_value:
        return can_use_consumable_from_pack(state, str(primary_value))
    if normalized_type == "joker":
        return len(state.jokers) < state.joker_slots
    return True


def can_use_consumable_from_pack(state: UnifiedGameState, consumable_name: str) -> bool:
    if is_planet_consumable_name(consumable_name):
        return True

    if consumable_name == "The Fool":
        remembered = getattr(state, "last_tarot_planet_consumable", None)
        return (
            bool(remembered)
            and remembered != "The Fool"
            and len(state.consumables) < state.consumable_slots
        )

    if consumable_name in {"The High Priestess", "The Emperor", "Judgement"}:
        return len(state.consumables) < state.consumable_slots

    if consumable_name in {"The Hermit", "Temperance", "Immolate", "Black Hole"}:
        return True

    if consumable_name in {"Wraith", "The Soul"}:
        return len(state.jokers) < state.joker_slots and state.hand_size > 1

    if consumable_name == "Ectoplasm":
        return bool(state.jokers) and state.hand_size > 1

    required_targets = PACK_TARGETED_MIN_HAND_SIZE.get(consumable_name)
    if required_targets is not None:
        return _count_current_hand_cards(state) >= required_targets

    if is_tarot_consumable_name(consumable_name) or is_spectral_consumable_name(consumable_name):
        return False

    return False


def can_use_consumable_in_play(state: UnifiedGameState, consumable_name: str) -> bool:
    required_targets = PACK_TARGETED_MIN_HAND_SIZE.get(consumable_name)
    if required_targets is not None:
        return len(state.selected_cards) >= required_targets

    return can_use_consumable_from_pack(state, consumable_name)


def get_pack_consumable_target_count(consumable_name: str) -> int:
    return PACK_TARGETED_DEFAULT_TARGET_COUNT.get(consumable_name, 0)


def get_pending_pack_consumable(state: Any, shop: Any = None) -> str | None:
    for owner in (state, shop):
        if owner is None:
            continue
        value = getattr(owner, "pending_pack_consumable", None)
        if isinstance(value, str) and value:
            return value
    return None


def get_pending_pack_index(state: Any, shop: Any = None) -> int | None:
    for owner in (state, shop):
        if owner is None:
            continue
        value = getattr(owner, "pending_pack_index", None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def get_pending_pack_target_count(state: Any, shop: Any = None) -> int:
    pending_pack_consumable = get_pending_pack_consumable(state, shop)
    if not pending_pack_consumable:
        return 0
    return get_pack_consumable_target_count(pending_pack_consumable)


def has_valid_pending_pack_targets(state: Any, shop: Any = None) -> bool:
    target_count = get_pending_pack_target_count(state, shop)
    if target_count <= 0:
        return False
    selected_cards = getattr(state, "selected_cards", None)
    if selected_cards is None and shop is not None:
        selected_cards = getattr(shop, "selected_cards", None)
    return len(selected_cards or []) == target_count


def _count_current_hand_cards(state: UnifiedGameState) -> int:
    count = 0
    for idx in state.hand_indexes:
        if 0 <= idx < len(state.deck):
            count += 1
    return count


def _get_first_list_like(owners: tuple[Any, ...], attrs: tuple[str, ...]) -> list[Any]:
    for owner in owners:
        if owner is None:
            continue
        for attr in attrs:
            value = getattr(owner, attr, None)
            if value is not None:
                return list(value)
    return []


def _get_string_value(item: Any, key: str) -> str | None:
    value = getattr(item, key, None)
    if value is None and isinstance(item, dict):
        value = item.get(key)
    return value if isinstance(value, str) and value else None


def _normalize_pack_item(item: Any) -> tuple[str | None, Any, str | None]:
    if item is None:
        return None, None, None

    if isinstance(item, str):
        return "consumable", item, item

    if isinstance(item, dict):
        if "consumable" in item:
            consumable_name = item.get("consumable")
            return "consumable", consumable_name, str(consumable_name) if consumable_name else None
        if "joker" in item:
            joker_value = item.get("joker")
            return "joker", joker_value, _get_string_value(joker_value, "label") or _get_string_value(joker_value, "name")
        if "card" in item:
            card_value = item.get("card")
            return "card", card_value, _get_string_value(item, "label")

        item_set = item.get("set")
        label = _get_string_value(item, "label")
        if item_set == "JOKER":
            return "joker", item, label
        if item_set in {"Tarot", "Planet", "Spectral"}:
            return "consumable", label, label
        if item_set:
            return "card", item, label

    if _get_string_value(item, "label") or _get_string_value(item, "name"):
        label = _get_string_value(item, "label") or _get_string_value(item, "name")
        consumable_name = _get_pack_consumable_name(item)
        if consumable_name:
            return "consumable", consumable_name, label

    if hasattr(item, "rank") and hasattr(item, "suit"):
        return "card", item, None

    return None, item, _get_string_value(item, "label") or _get_string_value(item, "name")


def _get_pack_consumable_name(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        consumable_name = item.get("consumable")
        if isinstance(consumable_name, str) and consumable_name:
            return consumable_name
        item_set = item.get("set")
        label = item.get("label")
        if item_set in {"Tarot", "Planet", "Spectral"} and isinstance(label, str) and label:
            return label
    for key in ("consumable", "label", "name"):
        value = _get_string_value(item, key)
        if value and (
            value in MVP_CONSUMABLE_ID_MAP
            or is_tarot_consumable_name(value)
            or is_planet_consumable_name(value)
            or is_spectral_consumable_name(value)
        ):
            return value
    return None


def _encode_standard_card_id(card: Any) -> int:
    rank_value = None
    suit_value = None

    if isinstance(card, dict):
        value = card.get("value") or {}
        rank_value = value.get("rank")
        suit_value = value.get("suit")
    else:
        rank = getattr(card, "rank", None)
        suit = getattr(card, "suit", None)
        rank_value = getattr(rank, "value", None)
        suit_value = getattr(suit, "value", None)

    suit_index = _normalize_suit_index(suit_value)
    rank_index = _normalize_rank_index(rank_value)
    if suit_index is None or rank_index is None:
        return 0
    return rank_index * 4 + suit_index + 1


def _stable_text_id(value: str, modulus: int) -> int:
    return (zlib.adler32(value.encode("utf-8")) % modulus) + 1


def _normalize_suit_index(value: Any) -> int | None:
    if isinstance(value, int):
        return value if 0 <= value <= 3 else None
    if value in {"H", "D", "C", "S"}:
        return {"H": 0, "D": 1, "C": 2, "S": 3}[value]
    return None


def _normalize_rank_index(value: Any) -> int | None:
    if isinstance(value, int):
        return value - 2 if 2 <= value <= 14 else None
    if value in {"2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"}:
        return {"2": 0, "3": 1, "4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "T": 8, "J": 9, "Q": 10, "K": 11, "A": 12}[value]
    return None

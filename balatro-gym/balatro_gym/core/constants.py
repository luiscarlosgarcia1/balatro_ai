"""Centralised enumerations and helper utilities for Balatro Gym
================================================================

This module replaces scattered *magic integers* with explicit `IntEnum`
classes. Import these enums everywhere instead of raw numbers to gain:

1. **Safety** – your IDE & `mypy` will scream when you pass the wrong kind of
   integer.
2. **Readability** – `Action.PLAY_HAND` is self‑explanatory; `0` is not.
3. **Refactor‑friendliness** – change a value here, *all* call‑sites update.

Usage (env excerpt)
-------------------
```python
from balatro_gym.core.constants import Action, Phase

if Phase(self.state.phase) is Phase.PLAY:
    if Action(action) is Action.PLAY_HAND:
        ...
    elif Action.SELECT_CARD_BASE <= action < Action.SELECT_CARD_BASE + Action.SELECT_CARD_COUNT:
        card_idx = action - Action.SELECT_CARD_BASE
        ...
```

Tip: wrap the integer `action` into `Action(action)` once at the top of
`step()` and pattern‑match from there.
"""

from __future__ import annotations
from itertools import combinations
from typing import Iterable
from enum import IntEnum, unique


@unique
class Phase(IntEnum):
    """High‑level game phases."""
    PLAY = 0
    SHOP = 1
    BLIND_SELECT = 2
    PACK_OPEN = 3


@unique
class Action(IntEnum):
    """Flat action space (0-277) with *base* offsets for parameterised actions.
    
    For ranges (e.g. *select card 0‑7*) we expose both **BASE** and **COUNT**
    constants so you can compute the concrete integer or reverse‑map from it.
    """
    # === Play‑phase basics ===
    PLAY_HAND: int = 0
    DISCARD: int = 1
    
    # --- Card selection (8 options) ---
    SELECT_CARD_BASE: int = 2
    # SELECT_CARD_COUNT = 8  # → 2‑9
    
    # --- Consumables (5 slots) ---
    USE_CONSUMABLE_BASE: int = 10
    # USE_CONSUMABLE_COUNT = 5  # → 10‑14
    
    # === Shop‑phase ===
    SHOP_BUY_BASE: int = 20  # 10 item slots → 20‑29
    # SHOP_BUY_COUNT = 10
    SHOP_REROLL: int = 30
    SHOP_END: int = 31
    
    # Selling
    SELL_JOKER_BASE: int = 32  # 5 joker slots → 32‑36
    # SELL_JOKER_COUNT = 5
    SELL_CONSUMABLE_BASE: int = 37  # 5 consumable slots → 37‑41
    # SELL_CONSUMABLE_COUNT = 5
    
    # === Blind selection ===
    SELECT_BLIND_BASE: int = 45  # small/big/boss → 45‑47
    # SELECT_BLIND_COUNT = 3
    SKIP_BLIND: int = 48
    REROLL_BOSS_BLIND: int = 49

    # === Pack opening ===
    SELECT_FROM_PACK_BASE: int = 50  # 5 choices → 50‑54
    # SELECT_FROM_PACK_COUNT = 5
    SKIP_PACK: int = 55

    # === Direct play-subset actions ===
    PLAY_SUBSET_BASE: int = 60
    # PLAY_SUBSET_COUNT = 218  # any visible non-empty subset of up to 5 of 8 slots
    
    # === Meta ===
    # ACTION_SPACE_SIZE = 60

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def offset(self, index: int) -> int:  # noqa: D401 – simple helper
        """Return the concrete *integer* ID for an indexed variant.
        
        Example::
            Action.SELECT_CARD_BASE.offset(3)  # → 5
        """
        return int(self) + index
    
    @classmethod
    def from_offset(cls, base: "Action", id_: int) -> int:
        """Reverse‑map: given a *concrete* action ID, return its **index**.
        
        Example::
            idx = Action.from_offset(Action.SELECT_CARD_BASE, action_id)
        """
        return id_ - int(base)


# Action count constants - not part of the enum!
class ActionCounts:
    """Constants defining how many actions of each type exist."""
    SELECT_CARD_COUNT: int = 8
    PLAY_SUBSET_COUNT: int = 218
    USE_CONSUMABLE_COUNT: int = 5
    SHOP_BUY_COUNT: int = 10
    SELL_JOKER_COUNT: int = 5
    SELL_CONSUMABLE_COUNT: int = 5
    SELECT_BLIND_COUNT: int = 3
    SELECT_FROM_PACK_COUNT: int = 5
    ACTION_SPACE_SIZE: int = 278


MAX_VISIBLE_HAND_CARDS = ActionCounts.SELECT_CARD_COUNT
MAX_PLAYABLE_SELECTED_CARDS = 5


def _build_play_subset_slot_sets() -> tuple[tuple[int, ...], ...]:
    subsets: list[tuple[int, ...]] = []
    for subset_size in range(1, MAX_PLAYABLE_SELECTED_CARDS + 1):
        subsets.extend(combinations(range(MAX_VISIBLE_HAND_CARDS), subset_size))
    return tuple(subsets)


PLAY_SUBSET_SLOT_SETS: tuple[tuple[int, ...], ...] = _build_play_subset_slot_sets()
if len(PLAY_SUBSET_SLOT_SETS) != ActionCounts.PLAY_SUBSET_COUNT:
    raise ValueError("PLAY_SUBSET_COUNT does not match the generated play-subset mapping")
PLAY_SUBSET_INDEX_BY_SLOTS: dict[tuple[int, ...], int] = {
    slots: index for index, slots in enumerate(PLAY_SUBSET_SLOT_SETS)
}


def _normalize_play_subset_slots(selected_slots: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted({int(slot) for slot in selected_slots}))
    if not normalized:
        raise ValueError("Play subset must contain at least one visible slot")
    if len(normalized) > MAX_PLAYABLE_SELECTED_CARDS:
        raise ValueError("Play subset cannot exceed five cards")
    if normalized[0] < 0 or normalized[-1] >= MAX_VISIBLE_HAND_CARDS:
        raise ValueError("Play subset must use visible hand slots only")
    return normalized


def encode_play_subset_action(selected_slots: Iterable[int]) -> int:
    normalized = _normalize_play_subset_slots(selected_slots)
    subset_index = PLAY_SUBSET_INDEX_BY_SLOTS.get(normalized)
    if subset_index is None:
        raise ValueError(f"Unsupported play subset: {normalized}")
    return int(Action.PLAY_SUBSET_BASE) + subset_index


def decode_play_subset_action(action_id: int) -> tuple[int, ...]:
    subset_index = int(action_id) - int(Action.PLAY_SUBSET_BASE)
    if not 0 <= subset_index < len(PLAY_SUBSET_SLOT_SETS):
        raise ValueError(f"Action {action_id} is not a direct play-subset action")
    return PLAY_SUBSET_SLOT_SETS[subset_index]


def is_play_subset_action(action_id: int) -> bool:
    subset_index = int(action_id) - int(Action.PLAY_SUBSET_BASE)
    return 0 <= subset_index < len(PLAY_SUBSET_SLOT_SETS)


# For backward compatibility, also expose as module-level constants
SELECT_CARD_COUNT = ActionCounts.SELECT_CARD_COUNT
PLAY_SUBSET_COUNT = ActionCounts.PLAY_SUBSET_COUNT
USE_CONSUMABLE_COUNT = ActionCounts.USE_CONSUMABLE_COUNT
SHOP_BUY_COUNT = ActionCounts.SHOP_BUY_COUNT
SELL_JOKER_COUNT = ActionCounts.SELL_JOKER_COUNT
SELL_CONSUMABLE_COUNT = ActionCounts.SELL_CONSUMABLE_COUNT
SELECT_BLIND_COUNT = ActionCounts.SELECT_BLIND_COUNT
SELECT_FROM_PACK_COUNT = ActionCounts.SELECT_FROM_PACK_COUNT
ACTION_SPACE_SIZE = ActionCounts.ACTION_SPACE_SIZE

# Alternatively, if you want to keep them on the Action class but not as enum members:
Action.SELECT_CARD_COUNT = SELECT_CARD_COUNT
Action.PLAY_SUBSET_COUNT = PLAY_SUBSET_COUNT
Action.USE_CONSUMABLE_COUNT = USE_CONSUMABLE_COUNT
Action.SHOP_BUY_COUNT = SHOP_BUY_COUNT
Action.SELL_JOKER_COUNT = SELL_JOKER_COUNT
Action.SELL_CONSUMABLE_COUNT = SELL_CONSUMABLE_COUNT
Action.SELECT_BLIND_COUNT = SELECT_BLIND_COUNT
Action.SELECT_FROM_PACK_COUNT = SELECT_FROM_PACK_COUNT
Action.ACTION_SPACE_SIZE = ACTION_SPACE_SIZE


__all__ = [
    "Phase",
    "Action",
    "ActionCounts",
    # Export the constants too for convenience
    "SELECT_CARD_COUNT",
    "PLAY_SUBSET_COUNT",
    "USE_CONSUMABLE_COUNT", 
    "SHOP_BUY_COUNT",
    "SELL_JOKER_COUNT",
    "SELL_CONSUMABLE_COUNT",
    "SELECT_BLIND_COUNT",
    "SELECT_FROM_PACK_COUNT",
    "ACTION_SPACE_SIZE",
    "MAX_VISIBLE_HAND_CARDS",
    "MAX_PLAYABLE_SELECTED_CARDS",
    "PLAY_SUBSET_SLOT_SETS",
    "encode_play_subset_action",
    "decode_play_subset_action",
    "is_play_subset_action",
]

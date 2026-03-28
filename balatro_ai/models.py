from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeAlias


ObservationPayload: TypeAlias = dict[str, Any]


@dataclass(frozen=True)
class ObservedCard:
    """Compact card summary extracted from the save payload."""

    area: str
    code: str | None = None
    name: str | None = None
    facing: str | None = None
    enhancement: str | None = None
    edition: str | None = None
    seal: str | None = None
    debuffed: bool = False
    modifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedVoucher:
    """Compact voucher summary exposed to policy code."""

    key: str
    cost: int | None = None


@dataclass(frozen=True)
class ObservedConsumable:
    """Consumable item that can be in inventory or visible in the shop."""

    kind: str
    key: str
    edition: str | None = None
    sell_price: int | None = None
    debuffed: bool = False
    stickers: tuple[str, ...] = ()
    cost: int | None = None


@dataclass(frozen=True)
class ObservedJoker:
    """Gameplay-relevant joker summary for policy decisions."""

    key: str
    rarity: str | None = None
    edition: str | None = None
    sell_price: int | None = None
    debuffed: bool = False
    stickers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedTag:
    """Run-relevant tag summary."""

    key: str


@dataclass(frozen=True)
class ObservedSkipTag:
    """Claimable or claimed skip tag summary."""

    slot: str
    key: str
    claimed: bool = False


@dataclass(frozen=True)
class ObservedBoosterPack:
    """Visible booster pack summary for shop decisions."""

    name: str
    key: str | None = None
    kind: str | None = None
    cost: int | None = None


@dataclass(frozen=True)
class ObservedShopItem:
    """Any visible shop item the policy may need to consider."""

    kind: str
    name: str
    key: str | None = None
    cost: int | None = None


@dataclass(frozen=True)
class ObservedBlind:
    """Blind choice available during blind selection."""

    slot: str
    key: str
    state: str
    tag_key: str | None = None
    tag_claimed: bool = False


@dataclass(frozen=True)
class GameObservation:
    """Structured snapshot of the current game state.

    Transitional legacy bridge: later phases will keep shrinking the object-model
    side of cards, shop, and blind details, but the scalar backbone already follows
    the canonical observer contract.
    """

    interaction_phase: str
    money: int
    hands_left: int
    discards_left: int
    score_current: int | None = None
    score_target: int | None = None
    jokers: tuple[ObservedJoker, ...] = ()
    hand_cards: tuple[ObservedCard, ...] = ()
    source: str = "unknown"
    state_id: int | None = None
    blind_key: str | None = None
    deck_key: str | None = None
    stake_id: str | int | None = None
    ante: int | None = None
    round_count: int | None = None
    blinds: tuple[ObservedBlind, ...] = ()
    joker_slots: int | None = None
    joker_count: int | None = None
    shop_vouchers: tuple[ObservedVoucher, ...] = ()
    vouchers: tuple[ObservedVoucher, ...] = ()
    consumables: tuple[ObservedConsumable, ...] = ()
    consumable_slots: int | None = None
    reroll_cost: int | None = None
    interest: int | None = None
    inflation: int | None = None
    hand_size: int | None = None
    shop_items: tuple[ObservedShopItem, ...] = ()
    tags: tuple[ObservedTag, ...] = ()
    skip_tags: tuple[ObservedSkipTag, ...] = ()
    booster_packs: tuple[ObservedBoosterPack, ...] = ()
    notes: tuple[str, ...] = ()
    seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class GameAction:
    """A high-level in-game action before it is translated into UI input."""

    kind: str
    target: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Whether the proposed action should be allowed to execute."""

    accepted: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepRecord:
    """Single loop iteration for logging and later evaluation."""

    observation: ObservationPayload
    action: GameAction
    validation: ValidationResult

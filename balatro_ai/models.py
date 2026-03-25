from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


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

    name: str
    key: str | None = None


@dataclass(frozen=True)
class ObservedConsumable:
    """Consumable item that can be in inventory or visible in the shop."""

    kind: str
    name: str
    key: str | None = None
    cost: int | None = None


@dataclass(frozen=True)
class ObservedJoker:
    """Gameplay-relevant joker summary for policy decisions."""

    name: str
    key: str | None = None
    edition: str | None = None
    debuffed: bool = False
    modifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedTag:
    """Run-relevant tag summary."""

    name: str
    key: str | None = None


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
class ObservedBlindChoice:
    """Blind choice available during blind selection."""

    slot: str
    key: str
    state: str | None = None
    tag: str | None = None


@dataclass(frozen=True)
class GameObservation:
    """Structured snapshot of the current game state."""

    phase: str
    money: int
    hands_left: int
    discards_left: int
    score_to_beat: int
    current_score: int = 0
    jokers: tuple[str, ...] = ()
    joker_details: tuple[ObservedJoker, ...] = ()
    hand_cards: tuple[ObservedCard, ...] = ()
    source: str = "unknown"
    state_id: int | None = None
    ante: int | None = None
    round_count: int | None = None
    stake: str | None = None
    blind_name: str | None = None
    blind_key: str | None = None
    blind_choices: tuple[ObservedBlindChoice, ...] = ()
    deck_name: str | None = None
    deck_key: str | None = None
    vouchers: tuple[ObservedVoucher, ...] = ()
    consumables_inventory: tuple[ObservedConsumable, ...] = ()
    consumables_shop: tuple[ObservedConsumable, ...] = ()
    consumable_capacity: int | None = None
    reroll_cost: int | None = None
    shop_items: tuple[ObservedShopItem, ...] = ()
    shop_packs: tuple[ObservedBoosterPack, ...] = ()
    tags: tuple[ObservedTag, ...] = ()
    booster_packs: tuple[ObservedBoosterPack, ...] = ()
    skip_tag_claimed: bool = False
    skip_tag: ObservedTag | None = None
    interaction_phase: str | None = None
    cards_in_hand: int | None = None
    jokers_count: int | None = None
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

    observation: GameObservation
    action: GameAction
    validation: ValidationResult

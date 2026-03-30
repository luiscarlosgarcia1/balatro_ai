from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeAlias


ObservationPayload: TypeAlias = dict[str, Any]


RUN_INFO_HAND_ORDER = (
    "Flush Five",
    "Flush House",
    "Five of a Kind",
    "Straight Flush",
    "Four of a Kind",
    "Full House",
    "Flush",
    "Straight",
    "Three of a Kind",
    "Two Pair",
    "Pair",
    "High Card",
)


@dataclass(frozen=True)
class ObservedCard:
    """Canonical card object for hand, deck, and pack zones."""

    card_key: str | None = None
    card_kind: str | None = None
    suit: str | None = None
    rank: str | None = None
    rarity: str | None = None
    enhancement: str | None = None
    edition: str | None = None
    seal: str | None = None
    stickers: tuple[str, ...] = ()
    facing: str | None = None
    cost: int | None = None
    sell_price: int | None = None
    debuffed: bool = False


@dataclass(frozen=True)
class ObservedReference:
    """Compact typed reference used for selected objects."""

    zone: str
    card_key: str | None = None
    joker_key: str | None = None
    consumable_key: str | None = None
    pack_key: str | None = None
    voucher_key: str | None = None


@dataclass(frozen=True)
class ObservedVoucher:
    """Compact voucher summary exposed to policy code."""

    key: str
    cost: int | None = None


@dataclass(frozen=True)
class ObservedConsumable:
    """Consumable item that can be in inventory or visible in the shop."""

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
class ObservedShopItem:
    """Any visible shop item the policy may need to consider."""

    kind: str
    name: str
    key: str | None = None
    cost: int | None = None
    rarity: str | None = None
    edition: str | None = None
    sell_price: int | None = None
    enhancement: str | None = None
    seal: str | None = None
    consumable_kind: str | None = None
    stickers: tuple[str, ...] = ()
    debuffed: bool = False
    card_key: str | None = None
    card_kind: str | None = None
    suit: str | None = None
    rank: str | None = None
    pack_key: str | None = None
    pack_kind: str | None = None


@dataclass(frozen=True)
class ObservedInterest:
    """Raw interest-state determinants exported from the game."""

    amount: int | None = None
    cap: int | None = None
    no_interest: bool = False


@dataclass(frozen=True)
class ObservedPackContents:
    """Canonical opened-pack state for finishing an active pack interaction."""

    choices_remaining: int | None = None
    skip_available: bool = False
    cards: tuple[ObservedCard, ...] = ()


@dataclass(frozen=True)
class ObservedRunHand:
    """Raw stored per-hand state exported from G.GAME.hands."""

    hand_name: str
    level: int | None = None
    mult: int | None = None
    chips: int | None = None
    played: int | None = None
    played_this_round: int | None = None


@dataclass(frozen=True)
class ObservedRunInfo:
    """Grouped run-scoped state that is not tied to a card zone."""

    hands: tuple[ObservedRunHand, ...] = ()


@dataclass(frozen=True)
class ObservedBlind:
    """Blind choice available during blind selection."""

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
    cards_in_hand: tuple[ObservedCard, ...] = ()
    selected_cards: tuple[ObservedReference, ...] = ()
    cards_in_deck: tuple[ObservedCard, ...] = ()
    source: str = "unknown"
    state_id: int | None = None
    blind_key: str | None = None
    deck_key: str | None = None
    stake_id: str | int | None = None
    ante: int | None = None
    round_count: int | None = None
    run_info: ObservedRunInfo | None = None
    blinds: tuple[ObservedBlind, ...] = ()
    joker_slots: int | None = None
    vouchers: tuple[ObservedVoucher, ...] = ()
    consumables: tuple[ObservedConsumable, ...] = ()
    consumable_slots: int | None = None
    reroll_cost: int | None = None
    interest: ObservedInterest | None = None
    hand_size: int | None = None
    shop_items: tuple[ObservedShopItem, ...] = ()
    pack_contents: ObservedPackContents | None = None
    tags: tuple[ObservedTag, ...] = ()
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

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


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
    """Observed playing card instance used across hand, deck, shop, and pack views."""
    # Design note: suit and rank should be derived from card_key in the knowledge layer.
    card_key: str                        # card.lua: card.config.card_key
    instance_id: int                     # card.lua: card.ID
    enhancement: str | None = None       # card.lua: card.config.center_key
    edition: str | None = None           # card.lua: card.edition.type
    seal: str | None = None              # card.lua: card.seal
    facing: str | None = None            # card.lua: card.facing
    debuffed: bool = False               # card.lua: card.debuff


@dataclass(frozen=True)
class ObservedCardPermanent:
    """Compact permanent per-card modifiers that persist across hands."""
    bonus_chips: int = 0                 # card.lua: card.ability.perma_bonus
    bonus_mult: int = 0                  # card.lua: card.ability.perma_mult
    bonus_x_mult: float = 0.0            # card.lua: card.ability.perma_x_mult
    held_chips: int = 0                  # card.lua: card.ability.perma_h_chips
    held_x_chips: float = 0.0            # card.lua: card.ability.perma_h_x_chips
    held_mult: int = 0                   # card.lua: card.ability.perma_h_mult
    held_x_mult: float = 0.0             # card.lua: card.ability.perma_h_x_mult
    play_dollars: int = 0                # card.lua: card.ability.perma_p_dollars
    held_dollars: int = 0                # card.lua: card.ability.perma_h_dollars


@dataclass(frozen=True)
class ObservedJoker:
    """Observed joker instance carrying only the gameplay-relevant live state."""
    # Design note: joker rarity should be derived from key in the knowledge layer.
    # Intentionally excluded until policy code needs them:
    # invisible_rounds, to_do_poker_hand, loyalty_remaining,
    # driver_tally, steel_tally, stone_tally, nine_tally

    key: str                             # card.lua: joker card.config.center_key
    instance_id: int                     # card.lua: card.ID
    eternal: bool                        # card.lua: card.ability.eternal
    perishable: bool                     # card.lua: card.ability.perishable
    rental: bool                         # card.lua: card.ability.rental
    perish_tally: int | None             # card.lua: card.ability.perish_tally
    edition: str | None = None           # card.lua: card.edition.type
    debuffed: bool = False               # card.lua: card.debuff
    cost: int | None = None              # card.lua: card.cost
    sell_cost: int | None = None         # card.lua: card.sell_cost


@dataclass(frozen=True)
class ObservedConsumable:
    """Observed consumable instance for inventory, shop, or pack contexts."""
    # Design note: consumable family/kind should be derived from key in the knowledge layer.

    key: str                             # card.lua: consumable card.config.center_key
    instance_id: int                     # card.lua: card.ID
    edition: str | None = None           # card.lua: card.edition.type
    cost: int | None = None              # card.lua: card.cost
    sell_cost: int | None = None         # card.lua: card.sell_cost


@dataclass(frozen=True)
class ObservedVoucher:
    """Minimal voucher identity and price for owned or shop-visible vouchers."""

    key: str                             # card.lua: voucher card.config.center_key / G.GAME.used_vouchers[key]
    instance_id: int                     # card.lua: card.ID
    cost: int                            # card.lua: voucher card.cost


@dataclass(frozen=True)
class ObservedTag:
    """Minimal tag identity for run-owned tags or blind skip rewards."""

    key: str                             # tag.lua: Tag.key / game.lua: G.GAME.round_resets.blind_tags[type]


@dataclass(frozen=True)
class ObservedPack:
    """Minimal booster pack identity for shop and opened-pack contexts."""

    key: str                             # card.lua: booster card.config.center_key
    instance_id: int                     # card.lua: card.ID
    cost: int | None = None              # card.lua: card.cost


ObservedPackItem = ObservedCard | ObservedConsumable | ObservedJoker
@dataclass(frozen=True)
class ObservedPackContents:
    """Active opened-pack interaction state, including visible reward choices."""

    choices_remaining: int | None = None             # card.lua: G.GAME.pack_choices
    skip_available: bool = False                     # button_callbacks.lua: can_skip_booster(...)
    items: tuple[ObservedPackItem, ...] = ()         # card.lua: G.pack_cards.cards


ObservedShopItem = ObservedCard | ObservedConsumable | ObservedJoker | ObservedVoucher | ObservedPack


@dataclass(frozen=True)
class ObservedReference:
    """Lightweight pointer to an interacted-with object without duplicating full payloads."""

    zone: str                            # main.lua: collect_selected_cards(...).zone
    instance_id: int                     # card.lua: selected card.ID
    key: str                             # card.lua: selected config.card_key / config.center_key


@dataclass(frozen=True)
class ObservedInterest:
    """Interest rule inputs needed to reason about end-of-round income."""

    amount: int                          # game.lua: G.GAME.interest_amount
    cap: int                             # game.lua: G.GAME.interest_cap
    no_interest: bool                    # game.lua: G.GAME.modifiers.no_interest


@dataclass(frozen=True)
class ObservedRunHand:
    """Per-hand run progression and usage counters from G.GAME.hands."""

    hand_name: str                        # game.lua: key in G.GAME.hands
    level: int                            # game.lua: G.GAME.hands[hand].level
    mult: int                             # game.lua: G.GAME.hands[hand].mult
    chips: int                            # game.lua: G.GAME.hands[hand].chips
    played: int                           # game.lua: G.GAME.hands[hand].played
    played_this_round: int                # game.lua: G.GAME.hands[hand].played_this_round


@dataclass(frozen=True)
class ObservedRunInfo:
    """Grouped run-scoped tables that are not tied to a single visible zone."""

    hands: tuple[ObservedRunHand, ...]       # game.lua: G.GAME.hands normalized into ordered tuples


@dataclass(frozen=True)
class ObservedBlind:
    """Blind-selection row summary for Small, Big, or Boss choices."""

    key: str                             # game.lua: G.GAME.round_resets.blind_choices[type]
    state: str                           # game.lua: G.GAME.round_resets.blind_states[type]
    tag_key: str | None = None           # game.lua: G.GAME.round_resets.blind_tags[type]

    
@dataclass(frozen=True)
class ObservedScore:
    """Current run score progress toward clearing the active blind."""
    current: int                         # main.lua: score.current <- G.GAME.chips / game.current_round_score / game.score
    target: int                          # main.lua: score.target <- G.GAME.blind.chips / game.score_to_beat / game.target_score


@dataclass(frozen=True)
class GameObservation:
    """Top-level typed snapshot of the current exported Balatro game state."""

    state_id: int                         # main.lua: root.STATE / game.state / game.current_round_state

    dollars: int                          # game.lua: G.GAME.dollars
    hands_left: int                       # game.lua: G.GAME.current_round.hands_left
    discards_left: int                    # game.lua: G.GAME.current_round.discards_left

    score: ObservedScore                  # main.lua: observer score wrapper around current + target score

    deck_key: str | None = None           # main.lua: summarize_deck(game).key <- game.selected_back_key / game.selected_back.key
    stake_id: str | int | None = None  # main.lua: summarize_stake(...).key / .index
    ante: int | None = None               # game.lua: G.GAME.round_resets.ante
    round: int | None = None              # game.lua: G.GAME.round
    blinds: tuple[ObservedBlind, ...] = ()  # main.lua: collect_blinds(game)

    joker_slots: int | None = None         # main.lua: root.jokers.config.card_limit / temp_limit / game.starting_params.joker_slots
    jokers: tuple[ObservedJoker, ...] = ()  # main.lua: collect_jokers(root.jokers)
    
    consumable_slots: int | None = None  # main.lua: consumeables.config.card_limit / temp_limit / game.starting_params.consumable_slots
    consumables: tuple[ObservedConsumable, ...] = ()  # main.lua: collect_consumables_from_sources(...)

    tags: tuple[ObservedTag, ...] = ()  # main.lua: collect_tags(game, root)
    vouchers: tuple[ObservedVoucher, ...] = ()  # main.lua: collect_used_vouchers(game, root)

    run_info: ObservedRunInfo | None = None  # main.lua: collect_run_info(game)
    interest: ObservedInterest | None = None  # main.lua: interest.amount/cap/no_interest

    shop_items: tuple[ObservedShopItem, ...] = ()  # main.lua: collect_shop_items(root, interaction_phase)
    reroll_cost: int | None = None           # game.lua: G.GAME.current_round.reroll_cost
    pack_contents: ObservedPackContents | None = None  # main.lua: collect_pack_contents(root, game, interaction_phase)

    hand_size: int | None = None            # main.lua: root.hand.config.card_limit / temp_limit / game.starting_params.hand_size
    cards_in_hand: tuple[ObservedCard, ...] = ()  # main.lua: collect_cards(root.hand.cards)
    selected_cards: tuple[ObservedReference, ...] = ()  # main.lua: collect_selected_cards(root)
    cards_in_deck: tuple[ObservedCard, ...] = ()  # main.lua: summarize_deck(game).cards

    seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # parser/file metadata; not native game state


@dataclass(frozen=True)
class GameAction:
    """Policy-produced high-level intent before UI automation translates it."""

    kind: str                                  # runtime/policy only; not native game state
    target: str | None = None                  # runtime/policy only; not native game state
    reason: str = ""                           # runtime/policy only; not native game state
    target_ids: tuple[int, ...] = ()           # file-channel: instance IDs of target cards
    order: tuple[int, ...] = ()                # file-channel: desired order by instance ID

    def to_action_dict(self) -> dict[str, object]:
        """Serialize to the action object shape used inside action.json's 'actions' array."""
        return {
            "kind": self.kind,
            "target_ids": list(self.target_ids),
            "target_key": self.target,
            "order": list(self.order),
        }


@dataclass(frozen=True)
class ValidationResult:
    """Validator output describing whether an action should be executed."""

    accepted: bool                        # runtime/validator only; not native game state
    notes: tuple[str, ...] = ()           # runtime/validator only; not native game state


@dataclass(frozen=True)
class StepRecord:
    """Single runtime loop record pairing observation, action, and validation."""

    observation: GameObservation          # runtime log wrapper; not native game state
    action: GameAction                    # runtime log wrapper; not native game state
    validation: ValidationResult          # runtime log wrapper; not native game state

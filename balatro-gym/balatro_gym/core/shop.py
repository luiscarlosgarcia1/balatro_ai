# balatro_gym/shop.py
# ---------------------------------------------------------------------------
# Deck-building subsystem: packs, jokers, vouchers, rerolls, skip-shop
# ---------------------------------------------------------------------------
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Dict, List, Optional, Sequence, Tuple

from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.jokers import JOKER_LIBRARY, JokerInfo


class ItemType(IntEnum):
    PACK = auto()
    CARD = auto()
    JOKER = auto()
    VOUCHER = auto()


class ShopAction(IntEnum):
    SKIP = 10
    REROLL = 11
    BUY_PACK_BASE = 12
    BUY_JOKER_BASE = 20
    BUY_CARD_BASE = 40
    BUY_VOUCHER_BASE = 60

    @classmethod
    def is_shop_action(cls, a: int) -> bool:
        return a >= cls.SKIP

    @classmethod
    def decode(cls, a: int) -> Tuple[str, int]:
        if a == cls.SKIP:
            return ("skip", -1)
        if a == cls.REROLL:
            return ("reroll", -1)
        if cls.BUY_PACK_BASE <= a < cls.BUY_JOKER_BASE:
            return ("buy_pack", a - cls.BUY_PACK_BASE)
        if cls.BUY_JOKER_BASE <= a < cls.BUY_CARD_BASE:
            return ("buy_joker", a - cls.BUY_JOKER_BASE)
        if cls.BUY_CARD_BASE <= a < cls.BUY_VOUCHER_BASE:
            return ("buy_card", a - cls.BUY_CARD_BASE)
        if cls.BUY_VOUCHER_BASE <= a < cls.BUY_VOUCHER_BASE + 10:
            return ("buy_voucher", a - cls.BUY_VOUCHER_BASE)
        raise ValueError(a)


@dataclass
class PlayerState:
    chips: int
    vouchers: List[str] = field(default_factory=list)
    jokers: List[int] = field(default_factory=list)
    deck: List[int] = field(default_factory=list)
    consumables: List[str] = field(default_factory=list)
    first_shop_buffoon_seen: bool = False
    shop_visits: int = 0
    spectral_rate: int = 0
    most_played_hand: Optional[str] = None


@dataclass
class ShopItem:
    item_type: ItemType
    name: str
    cost: int
    payload: Dict


@dataclass(frozen=True)
class PackDefinition:
    key: str
    name: str
    kind: str
    cost: int
    weight: float
    extra: int
    choose: int


@dataclass(frozen=True)
class VoucherDefinition:
    key: str
    name: str
    cost: int = 10
    requires: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsumableDefinition:
    key: str
    name: str
    set_name: str
    hand_type: Optional[str] = None
    softlock: bool = False
    hidden: bool = False


PACK_DEFINITIONS: Tuple[PackDefinition, ...] = (
    PackDefinition("p_arcana_normal_1", "Arcana Pack", "Arcana", 4, 1.0, 3, 1),
    PackDefinition("p_arcana_normal_2", "Arcana Pack", "Arcana", 4, 1.0, 3, 1),
    PackDefinition("p_arcana_normal_3", "Arcana Pack", "Arcana", 4, 1.0, 3, 1),
    PackDefinition("p_arcana_normal_4", "Arcana Pack", "Arcana", 4, 1.0, 3, 1),
    PackDefinition("p_arcana_jumbo_1", "Jumbo Arcana Pack", "Arcana", 6, 1.0, 5, 1),
    PackDefinition("p_arcana_jumbo_2", "Jumbo Arcana Pack", "Arcana", 6, 1.0, 5, 1),
    PackDefinition("p_arcana_mega_1", "Mega Arcana Pack", "Arcana", 8, 0.25, 5, 2),
    PackDefinition("p_arcana_mega_2", "Mega Arcana Pack", "Arcana", 8, 0.25, 5, 2),
    PackDefinition("p_celestial_normal_1", "Celestial Pack", "Celestial", 4, 1.0, 3, 1),
    PackDefinition("p_celestial_normal_2", "Celestial Pack", "Celestial", 4, 1.0, 3, 1),
    PackDefinition("p_celestial_normal_3", "Celestial Pack", "Celestial", 4, 1.0, 3, 1),
    PackDefinition("p_celestial_normal_4", "Celestial Pack", "Celestial", 4, 1.0, 3, 1),
    PackDefinition("p_celestial_jumbo_1", "Jumbo Celestial Pack", "Celestial", 6, 1.0, 5, 1),
    PackDefinition("p_celestial_jumbo_2", "Jumbo Celestial Pack", "Celestial", 6, 1.0, 5, 1),
    PackDefinition("p_celestial_mega_1", "Mega Celestial Pack", "Celestial", 8, 0.25, 5, 2),
    PackDefinition("p_celestial_mega_2", "Mega Celestial Pack", "Celestial", 8, 0.25, 5, 2),
    PackDefinition("p_standard_normal_1", "Standard Pack", "Standard", 4, 1.0, 3, 1),
    PackDefinition("p_standard_normal_2", "Standard Pack", "Standard", 4, 1.0, 3, 1),
    PackDefinition("p_standard_normal_3", "Standard Pack", "Standard", 4, 1.0, 3, 1),
    PackDefinition("p_standard_normal_4", "Standard Pack", "Standard", 4, 1.0, 3, 1),
    PackDefinition("p_standard_jumbo_1", "Jumbo Standard Pack", "Standard", 6, 1.0, 5, 1),
    PackDefinition("p_standard_jumbo_2", "Jumbo Standard Pack", "Standard", 6, 1.0, 5, 1),
    PackDefinition("p_standard_mega_1", "Mega Standard Pack", "Standard", 8, 0.25, 5, 2),
    PackDefinition("p_standard_mega_2", "Mega Standard Pack", "Standard", 8, 0.25, 5, 2),
    PackDefinition("p_buffoon_normal_1", "Buffoon Pack", "Buffoon", 4, 0.6, 2, 1),
    PackDefinition("p_buffoon_normal_2", "Buffoon Pack", "Buffoon", 4, 0.6, 2, 1),
    PackDefinition("p_buffoon_jumbo_1", "Jumbo Buffoon Pack", "Buffoon", 6, 0.6, 4, 1),
    PackDefinition("p_buffoon_mega_1", "Mega Buffoon Pack", "Buffoon", 8, 0.15, 4, 2),
    PackDefinition("p_spectral_normal_1", "Spectral Pack", "Spectral", 4, 0.3, 2, 1),
    PackDefinition("p_spectral_normal_2", "Spectral Pack", "Spectral", 4, 0.3, 2, 1),
    PackDefinition("p_spectral_jumbo_1", "Jumbo Spectral Pack", "Spectral", 6, 0.3, 4, 1),
    PackDefinition("p_spectral_mega_1", "Mega Spectral Pack", "Spectral", 8, 0.07, 4, 2),
)
PACK_DEFINITIONS_BY_KEY = {pack.key: pack for pack in PACK_DEFINITIONS}

VOUCHER_DEFINITIONS: Tuple[VoucherDefinition, ...] = (
    VoucherDefinition("v_overstock_norm", "Overstock"),
    VoucherDefinition("v_clearance_sale", "Clearance Sale"),
    VoucherDefinition("v_hone", "Hone"),
    VoucherDefinition("v_reroll_surplus", "Reroll Surplus"),
    VoucherDefinition("v_crystal_ball", "Crystal Ball"),
    VoucherDefinition("v_telescope", "Telescope"),
    VoucherDefinition("v_grabber", "Grabber"),
    VoucherDefinition("v_wasteful", "Wasteful"),
    VoucherDefinition("v_tarot_merchant", "Tarot Merchant"),
    VoucherDefinition("v_planet_merchant", "Planet Merchant"),
    VoucherDefinition("v_seed_money", "Seed Money"),
    VoucherDefinition("v_blank", "Blank"),
    VoucherDefinition("v_magic_trick", "Magic Trick"),
    VoucherDefinition("v_hieroglyph", "Hieroglyph"),
    VoucherDefinition("v_directors_cut", "Director's Cut"),
    VoucherDefinition("v_paint_brush", "Paint Brush"),
    VoucherDefinition("v_overstock_plus", "Overstock Plus", requires=("v_overstock_norm",)),
    VoucherDefinition("v_liquidation", "Liquidation", requires=("v_clearance_sale",)),
    VoucherDefinition("v_glow_up", "Glow Up", requires=("v_hone",)),
    VoucherDefinition("v_reroll_glut", "Reroll Glut", requires=("v_reroll_surplus",)),
    VoucherDefinition("v_omen_globe", "Omen Globe", requires=("v_crystal_ball",)),
    VoucherDefinition("v_observatory", "Observatory", requires=("v_telescope",)),
    VoucherDefinition("v_nacho_tong", "Nacho Tong", requires=("v_grabber",)),
    VoucherDefinition("v_recyclomancy", "Recyclomancy", requires=("v_wasteful",)),
    VoucherDefinition("v_tarot_tycoon", "Tarot Tycoon", requires=("v_tarot_merchant",)),
    VoucherDefinition("v_planet_tycoon", "Planet Tycoon", requires=("v_planet_merchant",)),
    VoucherDefinition("v_money_tree", "Money Tree", requires=("v_seed_money",)),
    VoucherDefinition("v_antimatter", "Antimatter", requires=("v_blank",)),
    VoucherDefinition("v_illusion", "Illusion", requires=("v_magic_trick",)),
    VoucherDefinition("v_petroglyph", "Petroglyph", requires=("v_hieroglyph",)),
    VoucherDefinition("v_retcon", "Retcon", requires=("v_directors_cut",)),
    VoucherDefinition("v_palette", "Palette", requires=("v_paint_brush",)),
)
VOUCHER_BY_KEY = {voucher.key: voucher for voucher in VOUCHER_DEFINITIONS}
VOUCHER_BY_NAME = {voucher.name: voucher for voucher in VOUCHER_DEFINITIONS}

TAROT_DEFINITIONS: Tuple[ConsumableDefinition, ...] = (
    ConsumableDefinition("c_fool", "The Fool", "Tarot"),
    ConsumableDefinition("c_magician", "The Magician", "Tarot"),
    ConsumableDefinition("c_high_priestess", "The High Priestess", "Tarot"),
    ConsumableDefinition("c_empress", "The Empress", "Tarot"),
    ConsumableDefinition("c_emperor", "The Emperor", "Tarot"),
    ConsumableDefinition("c_heirophant", "The Hierophant", "Tarot"),
    ConsumableDefinition("c_lovers", "The Lovers", "Tarot"),
    ConsumableDefinition("c_chariot", "The Chariot", "Tarot"),
    ConsumableDefinition("c_justice", "Justice", "Tarot"),
    ConsumableDefinition("c_hermit", "The Hermit", "Tarot"),
    ConsumableDefinition("c_wheel_of_fortune", "The Wheel of Fortune", "Tarot"),
    ConsumableDefinition("c_strength", "Strength", "Tarot"),
    ConsumableDefinition("c_hanged_man", "The Hanged Man", "Tarot"),
    ConsumableDefinition("c_death", "Death", "Tarot"),
    ConsumableDefinition("c_temperance", "Temperance", "Tarot"),
    ConsumableDefinition("c_devil", "The Devil", "Tarot"),
    ConsumableDefinition("c_tower", "The Tower", "Tarot"),
    ConsumableDefinition("c_star", "The Star", "Tarot"),
    ConsumableDefinition("c_moon", "The Moon", "Tarot"),
    ConsumableDefinition("c_sun", "The Sun", "Tarot"),
    ConsumableDefinition("c_judgement", "Judgement", "Tarot"),
    ConsumableDefinition("c_world", "The World", "Tarot"),
)

PLANET_DEFINITIONS: Tuple[ConsumableDefinition, ...] = (
    ConsumableDefinition("c_mercury", "Mercury", "Planet", "Pair"),
    ConsumableDefinition("c_venus", "Venus", "Planet", "Three of a Kind"),
    ConsumableDefinition("c_earth", "Earth", "Planet", "Full House"),
    ConsumableDefinition("c_mars", "Mars", "Planet", "Four of a Kind"),
    ConsumableDefinition("c_jupiter", "Jupiter", "Planet", "Flush"),
    ConsumableDefinition("c_saturn", "Saturn", "Planet", "Straight"),
    ConsumableDefinition("c_uranus", "Uranus", "Planet", "Two Pair"),
    ConsumableDefinition("c_neptune", "Neptune", "Planet", "Straight Flush"),
    ConsumableDefinition("c_pluto", "Pluto", "Planet", "High Card"),
    ConsumableDefinition("c_planet_x", "Planet X", "Planet", "Five of a Kind", softlock=True),
    ConsumableDefinition("c_ceres", "Ceres", "Planet", "Flush House", softlock=True),
    ConsumableDefinition("c_eris", "Eris", "Planet", "Flush Five", softlock=True),
)
PLANET_BY_HAND = {planet.hand_type: planet for planet in PLANET_DEFINITIONS if planet.hand_type}

SPECTRAL_DEFINITIONS: Tuple[ConsumableDefinition, ...] = (
    ConsumableDefinition("c_familiar", "Familiar", "Spectral"),
    ConsumableDefinition("c_grim", "Grim", "Spectral"),
    ConsumableDefinition("c_incantation", "Incantation", "Spectral"),
    ConsumableDefinition("c_talisman", "Talisman", "Spectral"),
    ConsumableDefinition("c_aura", "Aura", "Spectral"),
    ConsumableDefinition("c_wraith", "Wraith", "Spectral"),
    ConsumableDefinition("c_sigil", "Sigil", "Spectral"),
    ConsumableDefinition("c_ouija", "Ouija", "Spectral"),
    ConsumableDefinition("c_ectoplasm", "Ectoplasm", "Spectral"),
    ConsumableDefinition("c_immolate", "Immolate", "Spectral"),
    ConsumableDefinition("c_ankh", "Ankh", "Spectral"),
    ConsumableDefinition("c_deja_vu", "Deja Vu", "Spectral"),
    ConsumableDefinition("c_hex", "Hex", "Spectral"),
    ConsumableDefinition("c_trance", "Trance", "Spectral"),
    ConsumableDefinition("c_medium", "Medium", "Spectral"),
    ConsumableDefinition("c_cryptid", "Cryptid", "Spectral"),
    ConsumableDefinition("c_soul", "The Soul", "Spectral", hidden=True),
    ConsumableDefinition("c_black_hole", "Black Hole", "Spectral", hidden=True),
)

SHOWMAN_JOKER_ID = 121
CHAOS_THE_CLOWN_ID = 30
ASTRONOMER_JOKER_ID = 143

BASE_JOKER_RATE = 20.0
BASE_TAROT_RATE = 4.0
BASE_PLANET_RATE = 4.0
BASE_SPECTRAL_RATE = 0.0
BASE_PLAYING_CARD_RATE = 0.0
BASE_REROLL_COST = 5
BASE_SHOP_CARD_SLOTS = 2
SHOP_PACK_SLOTS = 2
SHOP_VOUCHER_SLOTS = 1


class Shop:
    """Generates inventory, processes purchases, handles rerolls & skip."""

    def __init__(self, ante: int, player: PlayerState, *, seed: Optional[int] = None):
        self.ante = ante
        self.player = player
        self.rng = random.Random(seed)
        self.inventory: List[ShopItem] = []
        self.reroll_cost_increase = 0
        self.free_rerolls_remaining = self._count_joker(CHAOS_THE_CLOWN_ID)
        self.reroll_cost = 0
        self.player.shop_visits += 1
        self._update_reroll_cost(skip_increment=True)
        self._generate_inventory()

    def _cost_mult(self) -> float:
        return 1.0

    def _owned_voucher_keys(self) -> set[str]:
        keys: set[str] = set()
        for voucher in self.player.vouchers:
            if voucher in VOUCHER_BY_NAME:
                keys.add(VOUCHER_BY_NAME[voucher].key)
            elif voucher in VOUCHER_BY_KEY:
                keys.add(voucher)
        return keys

    def _has_voucher(self, name_or_key: str) -> bool:
        return name_or_key in self.player.vouchers or name_or_key in self._owned_voucher_keys()

    def _count_joker(self, joker_id: int) -> int:
        return sum(1 for owned_id in self.player.jokers if owned_id == joker_id)

    def _has_showman(self) -> bool:
        return SHOWMAN_JOKER_ID in self.player.jokers

    def _discount_percent(self) -> int:
        if self._has_voucher("Liquidation") or self._has_voucher("v_liquidation"):
            return 50
        if self._has_voucher("Clearance Sale") or self._has_voucher("v_clearance_sale"):
            return 25
        return 0

    def _base_reroll_cost(self) -> int:
        cost = BASE_REROLL_COST
        if self._has_voucher("Reroll Surplus") or self._has_voucher("v_reroll_surplus"):
            cost -= 2
        if self._has_voucher("Reroll Glut") or self._has_voucher("v_reroll_glut"):
            cost -= 2
        return max(0, cost)

    def _shop_card_slots(self) -> int:
        slots = BASE_SHOP_CARD_SLOTS
        if self._has_voucher("Overstock") or self._has_voucher("v_overstock_norm"):
            slots += 1
        if self._has_voucher("Overstock Plus") or self._has_voucher("v_overstock_plus"):
            slots += 1
        return slots

    def _tarot_rate(self) -> float:
        if self._has_voucher("Tarot Tycoon") or self._has_voucher("v_tarot_tycoon"):
            return 32.0
        if self._has_voucher("Tarot Merchant") or self._has_voucher("v_tarot_merchant"):
            return 9.6
        return BASE_TAROT_RATE

    def _planet_rate(self) -> float:
        if self._has_voucher("Planet Tycoon") or self._has_voucher("v_planet_tycoon"):
            return 32.0
        if self._has_voucher("Planet Merchant") or self._has_voucher("v_planet_merchant"):
            return 9.6
        return BASE_PLANET_RATE

    def _playing_card_rate(self) -> float:
        if self._has_voucher("Magic Trick") or self._has_voucher("v_magic_trick"):
            return 4.0
        if self._has_voucher("Illusion") or self._has_voucher("v_illusion"):
            return 4.0
        return BASE_PLAYING_CARD_RATE

    def _spectral_rate(self) -> float:
        return float(getattr(self.player, "spectral_rate", BASE_SPECTRAL_RATE) or 0.0)

    def _is_astronomer_active(self) -> bool:
        return ASTRONOMER_JOKER_ID in self.player.jokers

    def _price(self, base_cost: int, *, edition: Edition = Edition.NONE, free: bool = False) -> int:
        if free:
            return 0
        extra_cost = 0
        if edition == Edition.FOIL:
            extra_cost += 2
        elif edition == Edition.HOLOGRAPHIC:
            extra_cost += 3
        elif edition == Edition.POLYCHROME:
            extra_cost += 5
        elif edition == Edition.NEGATIVE:
            extra_cost += 5
        discount = self._discount_percent()
        return max(1, math.floor((base_cost + extra_cost + 0.5) * (100 - discount) / 100))

    def _decode_card_index(self, card_index: int) -> Card:
        rank = Rank((card_index // 4) + 2)
        suit = Suit(card_index % 4)
        return Card(rank=rank, suit=suit)

    def _random_standard_card(self) -> Card:
        return self._decode_card_index(self.rng.randint(0, 51))

    def _weighted_choice(self, entries: Sequence[Tuple[object, float]]):
        total = sum(weight for _, weight in entries)
        if total <= 0:
            return entries[-1][0]
        poll = self.rng.random() * total
        running = 0.0
        for value, weight in entries:
            running += weight
            if poll <= running:
                return value
        return entries[-1][0]

    def _choose_from_pool(
        self,
        pool: Sequence,
        *,
        taken_keys: Optional[set[str]] = None,
        weight_attr: Optional[str] = None,
    ):
        taken_keys = taken_keys or set()
        eligible = []
        for entry in pool:
            key = getattr(entry, "key", None)
            if key and key in taken_keys and not self._has_showman():
                continue
            weight = getattr(entry, weight_attr) if weight_attr else 1.0
            eligible.append((entry, weight))
        if not eligible:
            eligible = [(entry, getattr(entry, weight_attr) if weight_attr else 1.0) for entry in pool]
        return self._weighted_choice(eligible)

    def _choose_joker(self, taken_keys: set[str]) -> JokerInfo:
        eligible: List[JokerInfo] = []
        owned = set(self.player.jokers)
        for joker in JOKER_LIBRARY:
            if joker.base_cost <= 0:
                continue
            if joker.id in owned and not self._has_showman():
                continue
            joker_key = f"j_{joker.id}"
            if joker_key in taken_keys and not self._has_showman():
                continue
            eligible.append(joker)
        if not eligible:
            eligible = [joker for joker in JOKER_LIBRARY if joker.base_cost > 0]
        return self.rng.choice(eligible)

    def _available_vouchers(self) -> List[VoucherDefinition]:
        owned_keys = self._owned_voucher_keys()
        available: List[VoucherDefinition] = []
        for voucher in VOUCHER_DEFINITIONS:
            if voucher.key in owned_keys:
                continue
            if any(requirement not in owned_keys for requirement in voucher.requires):
                continue
            available.append(voucher)
        return available or [VOUCHER_BY_KEY["v_blank"]]

    def _select_pack_definition(self) -> PackDefinition:
        if self.player.shop_visits == 1 and not self.player.first_shop_buffoon_seen:
            self.player.first_shop_buffoon_seen = True
            return self.rng.choice(
                (
                    PACK_DEFINITIONS_BY_KEY["p_buffoon_normal_1"],
                    PACK_DEFINITIONS_BY_KEY["p_buffoon_normal_2"],
                )
            )
        return self._choose_from_pool(PACK_DEFINITIONS, weight_attr="weight")

    def _make_pack_item(self, definition: PackDefinition) -> ShopItem:
        free = definition.kind == "Celestial" and self._is_astronomer_active()
        payload = {
            "pack_key": definition.key,
            "pack_kind": definition.kind,
            "pack_name": definition.name,
            "choose": definition.choose,
            "extra": definition.extra,
        }
        return ShopItem(
            item_type=ItemType.PACK,
            name=definition.name,
            cost=self._price(definition.cost, free=free),
            payload=payload,
        )

    def _make_voucher_item(self, voucher: VoucherDefinition) -> ShopItem:
        return ShopItem(
            item_type=ItemType.VOUCHER,
            name=voucher.name,
            cost=self._price(voucher.cost),
            payload={"voucher_key": voucher.key, "voucher": voucher.name},
        )

    def _make_joker_item(self, joker: JokerInfo) -> ShopItem:
        return ShopItem(
            item_type=ItemType.JOKER,
            name=joker.name,
            cost=self._price(joker.base_cost),
            payload={"joker_id": joker.id, "joker": joker},
        )

    def _make_consumable_item(self, consumable: ConsumableDefinition) -> ShopItem:
        free = consumable.set_name == "Planet" and self._is_astronomer_active()
        return ShopItem(
            item_type=ItemType.CARD,
            name=consumable.name,
            cost=self._price(3 if consumable.set_name != "Spectral" else 4, free=free),
            payload={
                "offer_set": consumable.set_name,
                "consumable": consumable.name,
                "consumable_key": consumable.key,
                "consumable_type": consumable.set_name,
            },
        )

    def _poll_standard_pack_edition(self) -> Edition:
        roll = self.rng.random()
        if roll > 0.988:
            return Edition.POLYCHROME
        if roll > 0.96:
            return Edition.HOLOGRAPHIC
        if roll > 0.92:
            return Edition.FOIL
        return Edition.NONE

    def _poll_illusion_shop_edition(self) -> Edition:
        roll = self.rng.random()
        if roll > 0.85:
            return Edition.POLYCHROME
        if roll > 0.5:
            return Edition.HOLOGRAPHIC
        return Edition.FOIL

    def _poll_standard_pack_seal(self) -> Seal:
        if self.rng.random() <= 0.8:
            return Seal.NONE
        seal_roll = self.rng.random()
        if seal_roll > 0.75:
            return Seal.RED
        if seal_roll > 0.5:
            return Seal.BLUE
        if seal_roll > 0.25:
            return Seal.GOLD
        return Seal.PURPLE

    def _poll_enhancement(self) -> Enhancement:
        return self.rng.choice(
            (
                Enhancement.BONUS,
                Enhancement.MULT,
                Enhancement.WILD,
                Enhancement.GLASS,
                Enhancement.STEEL,
                Enhancement.STONE,
                Enhancement.GOLD,
                Enhancement.LUCKY,
            )
        )

    def _make_playing_card_offer(self, *, from_standard_pack: bool) -> Dict:
        card = self._random_standard_card()
        enhancement = Enhancement.NONE
        edition = Edition.NONE
        seal = Seal.NONE

        if from_standard_pack:
            if self.rng.random() > 0.6:
                enhancement = self._poll_enhancement()
            edition = self._poll_standard_pack_edition()
            seal = self._poll_standard_pack_seal()
        else:
            if self._has_voucher("Illusion") or self._has_voucher("v_illusion"):
                if self.rng.random() > 0.6:
                    enhancement = self._poll_enhancement()
                if self.rng.random() > 0.8:
                    edition = self._poll_illusion_shop_edition()

        return {
            "offer_set": "Playing",
            "card": card,
            "card_index": int(card),
            "enhancement": enhancement,
            "edition": edition,
            "seal": seal,
        }

    def _choose_consumable(
        self,
        pool: Sequence[ConsumableDefinition],
        taken_keys: set[str],
        *,
        forced_key: Optional[str] = None,
    ) -> ConsumableDefinition:
        if forced_key:
            for entry in pool:
                if entry.key == forced_key:
                    return entry
        return self._choose_from_pool(pool, taken_keys=taken_keys)

    def _planet_pool(self) -> Tuple[ConsumableDefinition, ...]:
        hand_hint = getattr(self.player, "most_played_hand", None)
        return tuple(
            planet
            for planet in PLANET_DEFINITIONS
            if not planet.softlock or planet.hand_type == hand_hint
        )

    def _non_hidden_spectral_pool(self) -> Tuple[ConsumableDefinition, ...]:
        return tuple(spectral for spectral in SPECTRAL_DEFINITIONS if not spectral.hidden)

    def _roll_pack_special_consumable(self, base_kind: str) -> Optional[ConsumableDefinition]:
        if base_kind in {"Arcana", "Spectral"} and self.rng.random() > 0.997:
            return next(card for card in SPECTRAL_DEFINITIONS if card.key == "c_soul")
        if base_kind in {"Celestial", "Spectral"} and self.rng.random() > 0.997:
            return next(card for card in SPECTRAL_DEFINITIONS if card.key == "c_black_hole")
        return None

    def _generate_shop_card_offer(self, taken_keys: set[str]) -> ShopItem:
        rates = [
            ("Joker", BASE_JOKER_RATE),
            ("Tarot", self._tarot_rate()),
            ("Planet", self._planet_rate()),
            ("Playing", self._playing_card_rate()),
            ("Spectral", self._spectral_rate()),
        ]
        choice = self._weighted_choice(rates)

        if choice == "Joker":
            joker = self._choose_joker(taken_keys)
            taken_keys.add(f"j_{joker.id}")
            return self._make_joker_item(joker)

        if choice == "Tarot":
            consumable = self._choose_consumable(TAROT_DEFINITIONS, taken_keys)
            taken_keys.add(consumable.key)
            return self._make_consumable_item(consumable)

        if choice == "Planet":
            consumable = self._choose_consumable(self._planet_pool(), taken_keys)
            taken_keys.add(consumable.key)
            return self._make_consumable_item(consumable)

        if choice == "Spectral":
            consumable = self._choose_consumable(self._non_hidden_spectral_pool(), taken_keys)
            taken_keys.add(consumable.key)
            return self._make_consumable_item(consumable)

        payload = self._make_playing_card_offer(from_standard_pack=False)
        return ShopItem(
            item_type=ItemType.CARD,
            name=f"{payload['card'].rank.name} of {payload['card'].suit.name}",
            cost=self._price(1, edition=payload["edition"]),
            payload=payload,
        )

    def _refresh_inventory_costs(self) -> None:
        for item in self.inventory:
            if item.item_type == ItemType.PACK:
                pack = PACK_DEFINITIONS_BY_KEY[item.payload["pack_key"]]
                item.cost = self._price(pack.cost, free=pack.kind == "Celestial" and self._is_astronomer_active())
            elif item.item_type == ItemType.VOUCHER:
                voucher = VOUCHER_BY_KEY[item.payload["voucher_key"]]
                item.cost = self._price(voucher.cost)
            elif item.item_type == ItemType.JOKER:
                joker = item.payload["joker"]
                item.cost = self._price(joker.base_cost)
            elif item.payload.get("offer_set") == "Playing":
                item.cost = self._price(1, edition=item.payload.get("edition", Edition.NONE))
            else:
                item.cost = self._price(
                    3 if item.payload.get("offer_set") != "Spectral" else 4,
                    free=item.payload.get("offer_set") == "Planet" and self._is_astronomer_active(),
                )

    def _generate_inventory(self):
        self.inventory = self._generate_shop_card_items()

        for _ in range(SHOP_VOUCHER_SLOTS):
            voucher = self.rng.choice(self._available_vouchers())
            self.inventory.append(self._make_voucher_item(voucher))

        for _ in range(SHOP_PACK_SLOTS):
            self.inventory.append(self._make_pack_item(self._select_pack_definition()))

        self._refresh_inventory_costs()

    def _generate_shop_card_items(self) -> List[ShopItem]:
        taken_shop_keys: set[str] = set()
        shop_cards: List[ShopItem] = []

        for _ in range(self._shop_card_slots()):
            shop_cards.append(self._generate_shop_card_offer(taken_shop_keys))

        return shop_cards

    def _reroll_shop_cards(self) -> None:
        preserved_items = [item for item in self.inventory if item.item_type != ItemType.CARD and item.item_type != ItemType.JOKER]
        refreshed_shop_cards = self._generate_shop_card_items()
        self.inventory = refreshed_shop_cards + preserved_items
        self._refresh_inventory_costs()

    def get_observation(self) -> Dict:
        return {
            "shop_item_type": [item.item_type for item in self.inventory],
            "shop_cost": [item.cost for item in self.inventory],
            "shop_payload": [item.payload for item in self.inventory],
            "shop_reroll_cost": self.reroll_cost,
        }

    def _update_reroll_cost(self, *, skip_increment: bool) -> None:
        if self.free_rerolls_remaining > 0:
            self.reroll_cost = 0
            return
        if not skip_increment:
            self.reroll_cost_increase += 1
        self.reroll_cost = self._base_reroll_cost() + self.reroll_cost_increase

    def _pack_consumable_entry(self, consumable: ConsumableDefinition) -> Dict:
        return {
            "consumable": consumable.name,
            "consumable_key": consumable.key,
            "consumable_type": consumable.set_name,
        }

    def _generate_pack_contents(self, definition: PackDefinition) -> List[Dict]:
        contents: List[Dict] = []
        taken_keys: set[str] = set()

        for index in range(definition.extra):
            special_consumable = self._roll_pack_special_consumable(definition.kind)
            if special_consumable is not None:
                taken_keys.add(special_consumable.key)
                contents.append(self._pack_consumable_entry(special_consumable))
                continue

            if definition.kind == "Arcana":
                use_spectral = (
                    self._has_voucher("Omen Globe") or self._has_voucher("v_omen_globe")
                ) and self.rng.random() > 0.8
                pool = self._non_hidden_spectral_pool() if use_spectral else TAROT_DEFINITIONS
                consumable = self._choose_consumable(pool, taken_keys)
                taken_keys.add(consumable.key)
                contents.append(self._pack_consumable_entry(consumable))
            elif definition.kind == "Celestial":
                forced_key = None
                if index == 0 and (
                    self._has_voucher("Telescope") or self._has_voucher("v_telescope")
                ):
                    hand = getattr(self.player, "most_played_hand", None)
                    if hand in PLANET_BY_HAND:
                        forced_key = PLANET_BY_HAND[hand].key
                consumable = self._choose_consumable(self._planet_pool(), taken_keys, forced_key=forced_key)
                taken_keys.add(consumable.key)
                contents.append(self._pack_consumable_entry(consumable))
            elif definition.kind == "Spectral":
                consumable = self._choose_consumable(self._non_hidden_spectral_pool(), taken_keys)
                taken_keys.add(consumable.key)
                contents.append(self._pack_consumable_entry(consumable))
            elif definition.kind == "Standard":
                contents.append(self._make_playing_card_offer(from_standard_pack=True))
            elif definition.kind == "Buffoon":
                joker = self._choose_joker(taken_keys)
                taken_keys.add(f"j_{joker.id}")
                contents.append({"joker": joker, "joker_id": joker.id})

        return contents

    def step(self, action_id: int):
        verb, idx = ShopAction.decode(action_id)
        info: Dict = {}
        reward = 0.0

        if verb == "skip":
            return reward, True, info

        if verb == "reroll":
            cost = self.reroll_cost
            if self.player.chips < cost:
                return -1.0, False, {"error": "Insufficient chips for reroll"}
            self.player.chips -= cost
            if self.free_rerolls_remaining > 0:
                self.free_rerolls_remaining -= 1
                self._update_reroll_cost(skip_increment=True)
            else:
                self._update_reroll_cost(skip_increment=False)
            self._reroll_shop_cards()
            return 0.0, False, {
                "action": "reroll",
                "reroll_cost_paid": cost,
                "new_reroll_cost": self.reroll_cost,
                "free_rerolls_remaining": self.free_rerolls_remaining,
            }

        if idx < 0 or idx >= len(self.inventory):
            return -1.0, False, {"error": "Invalid shop index"}

        item = self.inventory[idx]
        if self.player.chips < item.cost:
            return -1.0, False, {"error": "Insufficient chips"}
        if verb == "buy_joker" and len(self.player.jokers) >= 5:
            return -1.0, False, {"error": "Joker slots full"}

        self.player.chips -= item.cost
        self.inventory.pop(idx)

        if verb == "buy_pack":
            definition = PACK_DEFINITIONS_BY_KEY[item.payload["pack_key"]]
            pack_contents = self._generate_pack_contents(definition)
            info.update(
                {
                    "pack_key": definition.key,
                    "pack_type": definition.name,
                    "pack_kind": definition.kind,
                    "pack_choose": definition.choose,
                    "pack_extra": definition.extra,
                    "new_cards": pack_contents,
                }
            )
        elif verb == "buy_card":
            offer_set = item.payload.get("offer_set")
            if offer_set == "Playing":
                self.player.deck.append(item.payload["card_index"])
                info["card_added"] = item.payload
            else:
                self.player.consumables.append(item.payload["consumable"])
                info["card_added"] = item.payload
                info["consumable_added"] = item.payload["consumable"]
        elif verb == "buy_joker":
            joker_id = item.payload["joker_id"]
            self.player.jokers.append(joker_id)
            info["joker_added"] = item.payload["joker"]
            self._refresh_inventory_costs()
        elif verb == "buy_voucher":
            voucher_name = item.payload["voucher"]
            if voucher_name not in self.player.vouchers:
                self.player.vouchers.append(voucher_name)
            self._update_reroll_cost(skip_increment=True)
            self._refresh_inventory_costs()
            info["voucher_added"] = voucher_name
        else:
            raise RuntimeError(verb)

        return reward, False, info

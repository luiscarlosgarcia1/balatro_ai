from __future__ import annotations

from datetime import datetime, timezone
import json

from ..models import (
    GameObservation,
    ObservedBlind,
    ObservedCard,
    ObservedConsumable,
    ObservedJoker,
    ObservedPackContents,
    ObservedReference,
    ObservedShopDiscount,
    ObservedShopItem,
    ObservedTag,
    ObservedVoucher,
)

class LiveObservationParser:
    def parse_file(self, path) -> GameObservation | None:
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        state = payload.get("state")
        if not isinstance(state, dict):
            state = payload
        if not isinstance(state, dict):
            return None

        cards_in_hand = self._parse_cards(state.get("cards_in_hand"))
        selected_cards = self._parse_references(state.get("selected_cards"))
        highlighted_card = self._parse_reference(state.get("highlighted_card"))
        cards_in_deck = self._parse_cards(state.get("cards_in_deck"))
        notes = state.get("notes")
        if not isinstance(notes, list):
            notes = []

        score_payload = state.get("score")
        if not isinstance(score_payload, dict):
            score_payload = {}

        interaction_phase = self._string_or_none(state.get("interaction_phase")) or "unknown"
        blinds = self._parse_live_blinds(state.get("blinds"))
        vouchers = self._parse_live_vouchers(state.get("vouchers"))
        shop_vouchers = self._parse_live_vouchers(state.get("shop_vouchers"))
        consumables = self._parse_live_consumables(state.get("consumables"))
        shop_items = self._parse_live_shop_items(state.get("shop_items"))
        shop_items = self._merge_shop_vouchers_into_shop_items(
            shop_items=shop_items,
            shop_vouchers=shop_vouchers,
            interaction_phase=interaction_phase,
        )
        shop_discounts = self._parse_live_shop_discounts(state.get("shop_discounts"))
        pack_contents = self._parse_live_pack_contents(state.get("pack_contents"))
        tags = self._parse_live_tags(state.get("tags"))
        jokers = self._parse_live_jokers(state.get("jokers"))

        seen_at_raw = state.get("seen_at")
        seen_at = None
        if isinstance(seen_at_raw, str):
            try:
                seen_at = datetime.fromisoformat(seen_at_raw)
            except ValueError:
                seen_at = None
        if seen_at is None:
            seen_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        return GameObservation(
            interaction_phase=interaction_phase,
            money=self._int_or_zero(state.get("money")),
            hands_left=self._int_or_zero(state.get("hands_left")),
            discards_left=self._int_or_zero(state.get("discards_left")),
            score_current=self._int_or_none(score_payload.get("current")),
            score_target=self._int_or_none(score_payload.get("target")),
            jokers=tuple(jokers),
            cards_in_hand=tuple(cards_in_hand),
            selected_cards=tuple(selected_cards),
            highlighted_card=highlighted_card,
            cards_in_deck=tuple(cards_in_deck),
            source=str(state.get("source", "live_export")),
            state_id=self._int_or_none(state.get("state_id")),
            blind_key=self._string_or_none(state.get("blind_key")),
            deck_key=self._string_or_none(state.get("deck_key")),
            stake_id=state.get("stake_id"),
            ante=self._int_or_none(state.get("ante")),
            round_count=self._int_or_none(state.get("round_count", state.get("round_number"))),
            blinds=tuple(blinds),
            joker_slots=self._int_or_none(state.get("joker_slots")),
            vouchers=tuple(vouchers),
            consumables=tuple(consumables),
            consumable_slots=self._int_or_none(state.get("consumable_slots")),
            reroll_cost=self._int_or_none(state.get("reroll_cost")),
            interest=self._int_or_none(state.get("interest")),
            inflation=self._int_or_none(state.get("inflation")),
            hand_size=self._int_or_none(state.get("hand_size")),
            shop_items=tuple(shop_items),
            shop_discounts=tuple(shop_discounts),
            pack_contents=pack_contents,
            tags=tuple(tags),
            notes=tuple(str(value) for value in notes if value is not None),
            seen_at=seen_at,
        )

    def _parse_cards(self, payload: object) -> list[ObservedCard]:
        cards: list[ObservedCard] = []
        if not isinstance(payload, list):
            return cards

        for item in payload:
            if not isinstance(item, dict):
                continue
            stickers = item.get("stickers")
            cards.append(
                ObservedCard(
                    card_key=self._string_or_none(item.get("card_key", item.get("code"))),
                    card_kind=self._string_or_none(item.get("card_kind", item.get("kind"))),
                    suit=self._string_or_none(item.get("suit")),
                    rank=self._string_or_none(item.get("rank")),
                    rarity=self._string_or_none(item.get("rarity")),
                    enhancement=self._string_or_none(item.get("enhancement")),
                    edition=self._string_or_none(item.get("edition")),
                    seal=self._string_or_none(item.get("seal")),
                    stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                    facing=self._string_or_none(item.get("facing")),
                    cost=self._int_or_none(item.get("cost")),
                    sell_price=self._int_or_none(item.get("sell_price")),
                    debuffed=bool(item.get("debuffed", False)),
                )
            )
        return cards

    def _parse_references(self, payload: object) -> list[ObservedReference]:
        references: list[ObservedReference] = []
        if not isinstance(payload, list):
            return references

        for item in payload:
            reference = self._parse_reference(item)
            if reference is not None:
                references.append(reference)
        return references

    def _parse_reference(self, payload: object) -> ObservedReference | None:
        if not isinstance(payload, dict):
            return None

        zone = self._string_or_none(payload.get("zone"))
        if not zone:
            return None

        reference = ObservedReference(
            zone=zone,
            card_key=self._string_or_none(payload.get("card_key")),
            joker_key=self._string_or_none(payload.get("joker_key")),
            consumable_key=self._string_or_none(payload.get("consumable_key")),
            pack_key=self._string_or_none(payload.get("pack_key")),
            voucher_key=self._string_or_none(payload.get("voucher_key")),
        )
        if any(
            value is not None
            for value in (
                reference.card_key,
                reference.joker_key,
                reference.consumable_key,
                reference.pack_key,
                reference.voucher_key,
            )
        ):
            return reference
        return None

    def _parse_live_vouchers(self, payload: object) -> list[ObservedVoucher]:
        vouchers: list[ObservedVoucher] = []
        if not isinstance(payload, list):
            return vouchers

        for item in payload:
            if not isinstance(item, dict):
                continue
            key = self._string_or_none(item.get("key"))
            if not key:
                continue
            vouchers.append(
                ObservedVoucher(
                    key=key,
                    cost=self._int_or_none(item.get("cost")),
                )
            )
        return vouchers

    def _parse_live_jokers(self, payload: object) -> list[ObservedJoker]:
        jokers: list[ObservedJoker] = []
        if not isinstance(payload, list):
            return jokers

        for item in payload:
            if not isinstance(item, dict):
                continue
            key = self._string_or_none(item.get("key"))
            if not key:
                continue
            stickers = item.get("stickers")
            jokers.append(
                ObservedJoker(
                    key=key,
                    rarity=self._string_or_none(item.get("rarity")),
                    edition=self._string_or_none(item.get("edition")),
                    sell_price=self._int_or_none(item.get("sell_price")),
                    debuffed=bool(item.get("debuffed", False)),
                    stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                )
            )
        return jokers

    def _parse_live_consumables(self, payload: object) -> list[ObservedConsumable]:
        consumables: list[ObservedConsumable] = []
        if not isinstance(payload, list):
            return consumables

        for item in payload:
            if not isinstance(item, dict):
                continue
            key = self._string_or_none(item.get("key"))
            if not key:
                continue
            stickers = item.get("stickers")
            consumables.append(
                ObservedConsumable(
                    key=key,
                    edition=self._string_or_none(item.get("edition")),
                    sell_price=self._int_or_none(item.get("sell_price")),
                    debuffed=bool(item.get("debuffed", False)),
                    stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                    cost=self._int_or_none(item.get("cost")),
                )
            )
        return consumables

    def _parse_live_tags(self, payload: object) -> list[ObservedTag]:
        tags: list[ObservedTag] = []
        if not isinstance(payload, list):
            return tags

        for item in payload:
            if not isinstance(item, dict):
                continue
            key = self._string_or_none(item.get("key"))
            if not key:
                continue
            tags.append(ObservedTag(key=key))
        return tags

    def _parse_live_shop_items(self, payload: object) -> list[ObservedShopItem]:
        shop_items: list[ObservedShopItem] = []
        if not isinstance(payload, list):
            return shop_items

        for item in payload:
            if not isinstance(item, dict):
                continue
            kind = self._string_or_none(item.get("kind"))
            name = self._string_or_none(item.get("name"))
            key = self._string_or_none(item.get("key"))
            if not key and not name:
                continue
            stickers = item.get("stickers")
            shop_items.append(
                ObservedShopItem(
                    kind=kind or "shop",
                    name=name or key or "shop_item",
                    key=key,
                    cost=self._int_or_none(item.get("cost")),
                    rarity=self._string_or_none(item.get("rarity")),
                    edition=self._string_or_none(item.get("edition")),
                    sell_price=self._int_or_none(item.get("sell_price")),
                    enhancement=self._string_or_none(item.get("enhancement")),
                    seal=self._string_or_none(item.get("seal")),
                    consumable_kind=self._string_or_none(item.get("consumable_kind")),
                    stickers=tuple(str(value) for value in stickers) if isinstance(stickers, list) else (),
                    debuffed=bool(item.get("debuffed", False)),
                    card_key=self._string_or_none(item.get("card_key")),
                    card_kind=self._string_or_none(item.get("card_kind")),
                    suit=self._string_or_none(item.get("suit")),
                    rank=self._string_or_none(item.get("rank")),
                    pack_key=self._string_or_none(item.get("pack_key")),
                    pack_kind=self._string_or_none(item.get("pack_kind")),
                )
            )
        return shop_items

    def _merge_shop_vouchers_into_shop_items(
        self,
        *,
        shop_items: list[ObservedShopItem],
        shop_vouchers: list[ObservedVoucher],
        interaction_phase: str,
    ) -> list[ObservedShopItem]:
        if interaction_phase != "shop" or not shop_vouchers:
            return shop_items

        merged = list(shop_items)
        seen = {
            item.key or item.name
            for item in merged
        }
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

    def _parse_live_shop_discounts(self, payload: object) -> list[ObservedShopDiscount]:
        shop_discounts: list[ObservedShopDiscount] = []
        if not isinstance(payload, list):
            return shop_discounts

        for item in payload:
            if not isinstance(item, dict):
                continue
            kind = self._string_or_none(item.get("kind"))
            if not kind:
                continue
            shop_discounts.append(
                ObservedShopDiscount(
                    kind=kind,
                    value=self._int_or_none(item.get("value")),
                )
            )
        return shop_discounts

    def _parse_live_pack_contents(self, payload: object) -> ObservedPackContents | None:
        if not isinstance(payload, dict):
            return None

        pack_key = self._string_or_none(payload.get("pack_key"))
        if not pack_key:
            return None

        return ObservedPackContents(
            pack_key=pack_key,
            pack_size=self._int_or_none(payload.get("pack_size")),
            choose_limit=self._int_or_none(payload.get("choose_limit")),
            choices_remaining=self._int_or_none(payload.get("choices_remaining")),
            skip_available=bool(payload.get("skip_available", False)),
            cards=tuple(self._parse_cards(payload.get("cards"))),
        )

    def _parse_live_blinds(self, payload: object) -> list[ObservedBlind]:
        blinds: list[ObservedBlind] = []
        if not isinstance(payload, list):
            return blinds

        for item in payload:
            if not isinstance(item, dict):
                continue
            key = self._string_or_none(item.get("key"))
            state = self._string_or_none(item.get("state"))
            if not key or not state:
                continue
            blinds.append(
                ObservedBlind(
                    key=key,
                    state=state,
                    tag_key=self._string_or_none(item.get("tag_key", item.get("tag"))),
                    tag_claimed=bool(item.get("tag_claimed", False)),
                )
            )
        return blinds

    def _int_or_zero(self, value: object) -> int:
        return self._int_or_none(value) or 0

    def _int_or_none(self, value: object) -> int | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        return None

    def _string_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        return str(value)

from __future__ import annotations

from datetime import datetime, timezone
import json

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

        hand_cards = self._parse_hand_cards(state.get("hand_cards"))
        notes = state.get("notes")
        if not isinstance(notes, list):
            notes = []

        deck_payload = state.get("deck")
        deck_name = None
        deck_key = None
        if isinstance(deck_payload, dict):
            deck_name = self._string_or_none(deck_payload.get("name"))
            deck_key = self._string_or_none(deck_payload.get("key"))

        blind_choices = self._parse_live_blind_choices(state.get("blind_choices"))
        vouchers = self._parse_live_vouchers(state.get("vouchers"))
        consumables_inventory = self._parse_live_consumables(state.get("consumables_inventory"))
        consumables_shop = self._parse_live_consumables(state.get("consumables_shop"))
        shop_items = self._parse_live_shop_items(state.get("shop_items"))
        tags = self._parse_live_tags(state.get("tags"))
        shop_packs = self._parse_live_booster_packs(state.get("shop_packs", state.get("booster_packs")))
        booster_packs = tuple(shop_packs)
        jokers, joker_details = self._parse_live_jokers(state.get("jokers"))
        skip_tag = self._parse_live_tag(state.get("skip_tag", state.get("claimed_skip_tag")))
        skip_tag_claimed_raw = state.get("skip_tag_claimed", state.get("claimed_skip_tag"))
        skip_tag_claimed = bool(skip_tag_claimed_raw) or skip_tag is not None

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
            phase=str(state.get("phase", state.get("state", "unknown"))),
            money=self._int_or_zero(state.get("money")),
            hands_left=self._int_or_zero(state.get("hands_left")),
            discards_left=self._int_or_zero(state.get("discards_left")),
            score_to_beat=self._int_or_zero(state.get("score_to_beat", state.get("target"))),
            current_score=self._int_or_zero(state.get("current_score", state.get("score"))),
            jokers=tuple(jokers),
            joker_details=tuple(joker_details),
            hand_cards=tuple(hand_cards),
            source=str(state.get("source", "live_export")),
            state_id=self._int_or_none(state.get("state_id")),
            ante=self._int_or_none(state.get("ante")),
            round_count=self._int_or_none(state.get("round_count", state.get("round_number"))),
            stake=self._string_or_none(state.get("stake", state.get("difficulty"))),
            blind_name=self._string_or_none(state.get("blind_name", state.get("blind"))),
            blind_key=self._string_or_none(state.get("blind_key")),
            blind_choices=tuple(blind_choices),
            deck_name=deck_name,
            deck_key=deck_key,
            vouchers=tuple(vouchers),
            consumables_inventory=tuple(consumables_inventory),
            consumables_shop=tuple(consumables_shop),
            consumable_capacity=self._int_or_none(state.get("consumable_capacity")),
            reroll_cost=self._int_or_none(state.get("reroll_cost")),
            shop_items=tuple(shop_items),
            shop_packs=tuple(shop_packs),
            tags=tuple(tags),
            booster_packs=tuple(booster_packs),
            skip_tag_claimed=skip_tag_claimed,
            skip_tag=skip_tag,
            interaction_phase=self._string_or_none(
                state.get("interaction_phase", state.get("pack_phase", state.get("subphase")))
            ),
            cards_in_hand=self._int_or_none(state.get("cards_in_hand")),
            jokers_count=self._int_or_none(state.get("jokers_count")),
            notes=tuple(str(value) for value in notes if value is not None),
            seen_at=seen_at,
        )

    def _parse_hand_cards(self, payload: object) -> list[ObservedCard]:
        hand_cards: list[ObservedCard] = []
        if not isinstance(payload, list):
            return hand_cards

        for item in payload:
            if not isinstance(item, dict):
                continue
            modifiers = item.get("modifiers")
            hand_cards.append(
                ObservedCard(
                    area=str(item.get("area", "hand")),
                    code=self._string_or_none(item.get("code")),
                    name=self._string_or_none(item.get("name")),
                    facing=self._string_or_none(item.get("facing")),
                    enhancement=self._string_or_none(item.get("enhancement")),
                    edition=self._string_or_none(item.get("edition")),
                    seal=self._string_or_none(item.get("seal")),
                    debuffed=bool(item.get("debuffed", False)),
                    modifiers=tuple(str(value) for value in modifiers) if isinstance(modifiers, list) else (),
                )
            )
        return hand_cards

    def _parse_live_vouchers(self, payload: object) -> list[ObservedVoucher]:
        vouchers: list[ObservedVoucher] = []
        if not isinstance(payload, list):
            return vouchers

        for item in payload:
            if not isinstance(item, dict):
                continue
            name = self._string_or_none(item.get("name"))
            if not name:
                continue
            vouchers.append(ObservedVoucher(name=name, key=self._string_or_none(item.get("key"))))
        return vouchers

    def _parse_live_jokers(self, payload: object) -> tuple[list[str], list[ObservedJoker]]:
        jokers: list[str] = []
        joker_details: list[ObservedJoker] = []
        if not isinstance(payload, list):
            return jokers, joker_details

        for item in payload:
            if item is None:
                continue
            if isinstance(item, dict):
                label = self._string_or_none(item.get("name")) or self._string_or_none(item.get("label"))
                if not label:
                    continue
                jokers.append(label)
                modifiers = item.get("modifiers")
                joker_details.append(
                    ObservedJoker(
                        name=label,
                        key=self._string_or_none(item.get("key")),
                        edition=self._string_or_none(item.get("edition")),
                        debuffed=bool(item.get("debuffed", False)),
                        modifiers=tuple(str(value) for value in modifiers) if isinstance(modifiers, list) else (),
                    )
                )
                continue
            jokers.append(str(item))
        return jokers, joker_details

    def _parse_live_consumables(self, payload: object) -> list[ObservedConsumable]:
        consumables: list[ObservedConsumable] = []
        if not isinstance(payload, list):
            return consumables

        for item in payload:
            if not isinstance(item, dict):
                continue
            kind = self._string_or_none(item.get("kind"))
            name = self._string_or_none(item.get("name"))
            if not kind or not name:
                continue
            consumables.append(
                ObservedConsumable(
                    kind=kind,
                    name=name,
                    key=self._string_or_none(item.get("key")),
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
            name = self._string_or_none(item.get("name"))
            if not name:
                continue
            tags.append(ObservedTag(name=name, key=self._string_or_none(item.get("key"))))
        return tags

    def _parse_live_tag(self, payload: object) -> ObservedTag | None:
        if payload is None:
            return None
        if isinstance(payload, dict):
            name = self._string_or_none(payload.get("name", payload.get("label")))
            key = self._string_or_none(payload.get("key"))
            if name:
                return ObservedTag(name=name, key=key)
            if key:
                return ObservedTag(name=key, key=key)
            return None
        if isinstance(payload, str):
            return ObservedTag(name=payload, key=payload)
        return None

    def _parse_live_shop_items(self, payload: object) -> list[ObservedShopItem]:
        shop_items: list[ObservedShopItem] = []
        if not isinstance(payload, list):
            return shop_items

        for item in payload:
            if not isinstance(item, dict):
                continue
            kind = self._string_or_none(item.get("kind"))
            name = self._string_or_none(item.get("name"))
            if not kind or not name:
                continue
            shop_items.append(
                ObservedShopItem(
                    kind=kind,
                    name=name,
                    key=self._string_or_none(item.get("key")),
                    cost=self._int_or_none(item.get("cost")),
                )
            )
        return shop_items

    def _parse_live_booster_packs(self, payload: object) -> list[ObservedBoosterPack]:
        booster_packs: list[ObservedBoosterPack] = []
        if not isinstance(payload, list):
            return booster_packs

        for item in payload:
            if not isinstance(item, dict):
                continue
            name = self._string_or_none(item.get("name"))
            if not name:
                continue
            booster_packs.append(
                ObservedBoosterPack(
                    name=name,
                    key=self._string_or_none(item.get("key")),
                    kind=self._string_or_none(item.get("kind")),
                    cost=self._int_or_none(item.get("cost")),
                )
            )
        return booster_packs

    def _parse_live_blind_choices(self, payload: object) -> list[ObservedBlindChoice]:
        blind_choices: list[ObservedBlindChoice] = []
        if not isinstance(payload, list):
            return blind_choices

        for item in payload:
            if not isinstance(item, dict):
                continue
            slot = self._string_or_none(item.get("slot"))
            key = self._string_or_none(item.get("key"))
            if not slot or not key:
                continue
            blind_choices.append(
                ObservedBlindChoice(
                    slot=slot,
                    key=key,
                    state=self._string_or_none(item.get("state")),
                    tag=self._string_or_none(item.get("tag")),
                )
            )
        return blind_choices

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

from __future__ import annotations

import json

from ...models import GameObservation, ObservedScore
from .coercion import int_or_none, int_or_zero, keyed_string_or_none, parse_seen_at, string_or_none
from .run_state import parse_interest, parse_pack_contents, parse_run_info
from .shop import merge_shop_vouchers_into_shop_items, parse_shop_items
from .zones import (
    parse_blinds,
    parse_cards,
    parse_consumables,
    parse_jokers,
    parse_references,
    parse_tags,
    parse_vouchers,
)


class LiveObservationParser:
    def parse_file(self, path) -> GameObservation | None:
        state = self._load_state(path)
        if state is None:
            return None
        return self._parse_state(state, path)

    def _load_state(self, path) -> dict[str, object] | None:
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
        return state

    def _parse_state(self, state: dict[str, object], path) -> GameObservation:
        cards_in_hand = parse_cards(state.get("cards_in_hand"))
        selected_cards = parse_references(state.get("selected_cards"))
        cards_in_deck = parse_cards(state.get("cards_in_deck"))

        score_payload = state.get("score")
        if not isinstance(score_payload, dict):
            score_payload = {}

        blinds = parse_blinds(state.get("blinds"))
        vouchers = parse_vouchers(state.get("vouchers"))
        shop_vouchers = parse_shop_items(state.get("shop_vouchers"))
        consumables = parse_consumables(state.get("consumables"))
        shop_items = parse_shop_items(state.get("shop_items"))
        shop_items = merge_shop_vouchers_into_shop_items(shop_items=shop_items, shop_vouchers=shop_vouchers)
        pack_contents = parse_pack_contents(state.get("pack_contents"))
        tags = parse_tags(state.get("tags"))
        jokers = parse_jokers(state.get("jokers"))
        interest = parse_interest(state.get("interest"))
        run_info = parse_run_info(state.get("run_info"))

        return GameObservation(
            state_id=int_or_zero(state.get("state_id")),
            interaction_phase=string_or_none(state.get("interaction_phase")),
            dollars=int_or_zero(state.get("dollars", state.get("money"))),
            hands_left=int_or_zero(state.get("hands_left")),
            discards_left=int_or_zero(state.get("discards_left")),
            score=ObservedScore(
                current=int_or_zero(score_payload.get("current")),
                target=int_or_zero(score_payload.get("target")),
            ),
            jokers=tuple(jokers),
            cards_in_hand=tuple(cards_in_hand),
            selected_cards=tuple(selected_cards),
            cards_in_deck=tuple(cards_in_deck),
            deck_key=keyed_string_or_none(state.get("deck_key")),
            stake_id=state.get("stake_id"),
            ante=int_or_none(state.get("ante")),
            round=int_or_none(state.get("round", state.get("round_count", state.get("round_number")))),
            run_info=run_info,
            blinds=tuple(blinds),
            joker_slots=int_or_none(state.get("joker_slots")),
            vouchers=tuple(vouchers),
            consumables=tuple(consumables),
            consumable_slots=int_or_none(state.get("consumable_slots")),
            reroll_cost=int_or_none(state.get("reroll_cost")),
            interest=interest,
            hand_size=int_or_none(state.get("hand_size")),
            shop_items=tuple(shop_items),
            pack_contents=pack_contents,
            tags=tuple(tags),
            seen_at=parse_seen_at(state, fallback_timestamp=path.stat().st_mtime),
        )

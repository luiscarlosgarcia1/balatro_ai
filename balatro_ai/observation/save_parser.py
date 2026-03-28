from __future__ import annotations

import re

from ..models import GameObservation, ObservedCard
from .save_decoder import SaveSnapshot


class SaveObservationParser:
    def parse_snapshot(self, snapshot: SaveSnapshot) -> GameObservation:
        # Transitional legacy bridge: save fallback still extracts a legacy
        # internal observation shape and relies on the canonical serializer to
        # produce the public contract.
        payload = snapshot.active_payload
        blind_block = self._extract_block(payload, "BLIND") or ""
        game_block = self._extract_block(payload, "GAME") or ""
        current_round_block = self._extract_block(game_block, "current_round") or ""
        round_resets_block = self._extract_block(game_block, "round_resets") or ""
        card_areas_block = self._extract_block(payload, "cardAreas") or ""
        pseudorandom_block = self._extract_block(game_block, "pseudorandom") or ""

        state_id = self._extract_int(payload, "STATE")
        blind_name = self._extract_top_level_string(blind_block, "name") or self._extract_string(blind_block, "name")
        blind_key = self._extract_top_level_string(blind_block, "config_blind") or self._extract_string(blind_block, "config_blind")
        money = self._extract_top_level_big_number(game_block, "dollars")
        if money is None:
            money = self._extract_big_number(game_block, "dollars") or 0
        hands_left = self._extract_int(current_round_block, "hands_left")
        discards_left = self._extract_int(current_round_block, "discards_left")
        score_target = self._extract_top_level_big_number(blind_block, "chips")
        if score_target is None:
            score_target = self._extract_big_number(blind_block, "chips")
        score_current = self._extract_top_level_big_number(game_block, "chips")
        if score_current is None:
            score_current = self._extract_big_number(game_block, "chips")
        ante = self._extract_int(round_resets_block, "ante")
        round_count = self._extract_int(game_block, "round")
        stake_id = self._extract_int(game_block, "stake")
        interest = self._extract_int(game_block, "interest_amount")
        inflation = self._extract_int(game_block, "inflation")
        cards_in_hand = self._extract_area_card_count(card_areas_block, "hand")
        joker_count = self._extract_area_card_count(card_areas_block, "jokers")
        seed = self._extract_string(pseudorandom_block, "seed")
        blind_in_progress = self._extract_top_level_bool(blind_block, "in_blind")
        if blind_in_progress is None:
            blind_in_progress = self._extract_bool(blind_block, "in_blind")
        blind_on_deck = self._extract_top_level_string(game_block, "blind_on_deck") or self._extract_string(game_block, "blind_on_deck")
        hand_cards = self._extract_area_cards(card_areas_block, "hand")

        interaction_phase = self._infer_phase(
            state_id=state_id,
            blind_in_progress=blind_in_progress,
            blind_on_deck=blind_on_deck,
            current_round_block=current_round_block,
            round_resets_block=round_resets_block,
        )

        notes: list[str] = [f"profile={snapshot.profile}", f"save={snapshot.save_path.name}"]
        if blind_name:
            notes.append(f"blind={blind_name}")
        if seed:
            notes.append(f"seed={seed}")
        if cards_in_hand is not None:
            notes.append(f"cards_in_hand={cards_in_hand}")
        if joker_count is not None:
            notes.append(f"jokers_count={joker_count}")

        return GameObservation(
            interaction_phase=interaction_phase,
            money=money,
            hands_left=hands_left or self._extract_int(round_resets_block, "hands") or 0,
            discards_left=discards_left or self._extract_int(round_resets_block, "discards") or 0,
            score_current=score_current,
            score_target=score_target,
            jokers=(),
            hand_cards=hand_cards,
            source="save_file",
            state_id=state_id,
            blind_key=blind_key,
            stake_id=stake_id,
            ante=ante,
            round_count=round_count,
            blinds=(),
            shop_vouchers=(),
            vouchers=(),
            consumables=(),
            consumable_slots=None,
            reroll_cost=None,
            interest=interest,
            inflation=inflation,
            hand_size=None,
            tags=(),
            skip_tags=(),
            booster_packs=(),
            joker_count=joker_count,
            notes=tuple(notes),
            seen_at=snapshot.modified_at,
        )

    def _infer_phase(
        self,
        *,
        state_id: int | None,
        blind_in_progress: bool | None,
        blind_on_deck: str | None,
        current_round_block: str,
        round_resets_block: str,
    ) -> str:
        if blind_in_progress:
            return "play_hand"

        hands_left = self._extract_int(current_round_block, "hands_left")
        discards_left = self._extract_int(current_round_block, "discards_left")
        round_blind_name = self._extract_string(self._extract_block(round_resets_block, "blind") or "", "name")
        if blind_on_deck and round_blind_name and hands_left is not None and discards_left is not None:
            return "blind_select"

        if state_id is None:
            return "unknown"
        return f"state_{state_id}"

    def _extract_area_card_count(self, card_areas_block: str, area_name: str) -> int | None:
        area_block = self._extract_block(card_areas_block, area_name)
        if not area_block:
            return None

        cards_block = self._extract_block(area_block, "cards") or ""
        search_start = 0
        if cards_block:
            search_start = area_block.find(cards_block) + len(cards_block)
        config_block = self._extract_block(area_block, "config", start=search_start) or area_block
        return self._extract_int(config_block, "card_count")

    def _extract_area_cards(self, card_areas_block: str, area_name: str) -> tuple[ObservedCard, ...]:
        area_block = self._extract_block(card_areas_block, area_name)
        if not area_block:
            return ()

        cards_block = self._extract_block(area_block, "cards") or ""
        cards: list[ObservedCard] = []
        for _, card_block in self._iter_child_blocks(cards_block):
            cards.append(self._build_card_summary(area_name, card_block))
        return tuple(cards)

    def _build_card_summary(self, area_name: str, card_block: str) -> ObservedCard:
        save_fields_block = self._extract_block(card_block, "save_fields") or ""
        base_block = self._extract_block(card_block, "base") or ""
        ability_block = self._extract_block(card_block, "ability") or ""
        edition_block = self._extract_block(card_block, "edition") or ""

        enhancement = self._extract_top_level_string(ability_block, "effect")
        if enhancement == "Base":
            enhancement = None

        modifiers: list[str] = []
        for key, label, default in (
            ("bonus", "bonus", 0),
            ("mult", "mult", 0),
            ("x_mult", "x_mult", 1),
            ("x_chips", "x_chips", 1),
            ("perma_bonus", "perma_bonus", 0),
            ("perma_mult", "perma_mult", 0),
            ("perma_x_mult", "perma_x_mult", 0),
            ("perma_x_chips", "perma_x_chips", 0),
            ("h_mult", "h_mult", 0),
            ("h_chips", "h_chips", 0),
            ("h_x_mult", "h_x_mult", 0),
            ("h_x_chips", "h_x_chips", 1),
            ("h_dollars", "h_dollars", 0),
            ("p_dollars", "p_dollars", 0),
            ("t_mult", "t_mult", 0),
            ("t_chips", "t_chips", 0),
            ("d_size", "d_size", 0),
            ("h_size", "h_size", 0),
        ):
            value = self._extract_top_level_number(ability_block, key)
            if value is not None and value != default:
                modifiers.append(f"{label}={self._format_number(value)}")

        if self._extract_top_level_bool(card_block, "debuff"):
            modifiers.append("debuffed")

        if self._extract_top_level_bool(ability_block, "played_this_ante"):
            modifiers.append("played_this_ante")

        return ObservedCard(
            area=area_name,
            code=self._extract_string(save_fields_block, "card"),
            name=self._extract_string(base_block, "name"),
            facing=self._extract_top_level_string(card_block, "facing"),
            enhancement=enhancement,
            edition=self._extract_top_level_string(edition_block, "type")
            or self._extract_top_level_string(edition_block, "key")
            or self._extract_top_level_string(edition_block, "name"),
            seal=self._extract_top_level_string(card_block, "seal"),
            debuffed=bool(self._extract_top_level_bool(card_block, "debuff")),
            modifiers=tuple(modifiers),
        )

    def _extract_string(self, text: str, key: str) -> str | None:
        match = re.search(rf'\["{re.escape(key)}"\]="((?:[^"\\]|\\.)*)"', text)
        if not match:
            return None
        return self._unescape(match.group(1))

    def _extract_top_level_string(self, text: str, key: str) -> str | None:
        raw = self._extract_top_level_raw_value(text, key)
        if raw is None:
            return None
        match = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', raw)
        if not match:
            return None
        return self._unescape(match.group(1))

    def _extract_int(self, text: str, key: str) -> int | None:
        match = re.search(rf'\["{re.escape(key)}"\]=(-?\d+)', text)
        if not match:
            return None
        return int(match.group(1))

    def _extract_bool(self, text: str, key: str) -> bool | None:
        match = re.search(rf'\["{re.escape(key)}"\]=(true|false)', text)
        if not match:
            return None
        return match.group(1) == "true"

    def _extract_top_level_bool(self, text: str, key: str) -> bool | None:
        raw = self._extract_top_level_raw_value(text, key)
        if raw is None:
            return None
        if raw == "true":
            return True
        if raw == "false":
            return False
        return None

    def _extract_big_number(self, text: str, key: str) -> int | None:
        match = re.search(rf'\["{re.escape(key)}"\]=to_big\(\{{(-?\d+)', text)
        if match:
            return int(match.group(1))
        return self._extract_int(text, key)

    def _extract_top_level_big_number(self, text: str, key: str) -> int | None:
        raw = self._extract_top_level_raw_value(text, key)
        if raw is None:
            return None
        match = re.fullmatch(r"to_big\(\{(-?\d+)(?:,\s*)?\},\s*1\)", raw)
        if match:
            return int(match.group(1))
        match = re.fullmatch(r"-?\d+", raw)
        if match:
            return int(raw)
        return None

    def _extract_top_level_number(self, text: str, key: str) -> float | int | None:
        raw = self._extract_top_level_raw_value(text, key)
        if raw is None:
            return None
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d+\.\d+", raw):
            return float(raw)
        return None

    def _extract_top_level_raw_value(self, text: str, key: str) -> str | None:
        marker = f'["{key}"]='
        depth = 0
        in_string = False
        escaped = False
        index = 0

        while index < len(text):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                index += 1
                continue
            if char == "{":
                depth += 1
                index += 1
                continue
            if char == "}":
                depth -= 1
                index += 1
                continue

            if depth == 1 and text.startswith(marker, index):
                value_start = index + len(marker)
                value_end = self._find_value_end(text, value_start)
                return text[value_start:value_end].strip()

            index += 1

        return None

    def _extract_block(self, text: str, key: str, start: int = 0) -> str | None:
        marker = f'["{key}"]={{'
        marker_start = text.find(marker, start)
        if marker_start == -1:
            return None

        brace_index = marker_start + len(marker) - 1
        return self._read_balanced_braces(text, brace_index)

    def _read_balanced_braces(self, text: str, start_index: int) -> str | None:
        end_index = self._find_balanced_brace_end(text, start_index)
        if end_index is None:
            return None
        return text[start_index : end_index + 1]

    def _find_balanced_brace_end(self, text: str, start_index: int) -> int | None:
        depth = 0
        in_string = False
        escaped = False

        for index in range(start_index, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index

        return None

    def _find_value_end(self, text: str, start_index: int) -> int:
        depth = 1
        in_string = False
        escaped = False

        for index in range(start_index, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                continue
            if char == "}":
                if depth == 1:
                    return index
                depth -= 1
                continue
            if char == "," and depth == 1:
                return index

        return len(text)

    def _iter_child_blocks(self, text: str) -> list[tuple[str, str]]:
        blocks: list[tuple[str, str]] = []
        depth = 0
        in_string = False
        escaped = False
        index = 0

        while index < len(text):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                index += 1
                continue
            if char == "{":
                depth += 1
                index += 1
                continue
            if char == "}":
                depth -= 1
                index += 1
                continue

            if char == "[" and depth == 1:
                end_bracket = text.find("]", index)
                if end_bracket != -1 and end_bracket + 2 < len(text) and text[end_bracket + 1 : end_bracket + 3] == "={":
                    key = text[index + 1 : end_bracket]
                    brace_index = end_bracket + 2
                    end_index = self._find_balanced_brace_end(text, brace_index)
                    if end_index is not None:
                        blocks.append((key, text[brace_index : end_index + 1]))
                        index = end_index + 1
                        continue

            index += 1

        return blocks

    def _format_number(self, value: float | int) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _unescape(self, value: str) -> str:
        return bytes(value, "utf-8").decode("unicode_escape")

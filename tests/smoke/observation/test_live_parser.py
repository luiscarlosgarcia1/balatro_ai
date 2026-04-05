from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation, ObservedScore
from balatro_ai.observation.parser import LiveObservationParser


class LiveParserSmokeTests(unittest.TestCase):
    def test_parse_wrapped_shop_items_into_typed_observation(self) -> None:
        payload = {
            "source": "live_state_exporter",
            "state_id": 41,
            "interaction_phase": "shop",
            "blind_key": "bl_small",
            "deck_key": "b_erratic",
            "score": {"current": 75, "target": 300},
            "money": 10,
            "hands_left": 4,
            "discards_left": 2,
            "shop_items": [
                {
                    "joker": {
                        "key": "j_blue_joker",
                        "instance_id": 101,
                        "eternal": True,
                        "sell_cost": 2,
                    }
                },
                {
                    "voucher": {
                        "key": "v_clearance_sale",
                        "cost": 10,
                    }
                },
                {
                    "pack": {
                        "key": "p_arcana_normal_1",
                        "instance_id": 202,
                        "cost": 4,
                    }
                },
                {
                    "joker": {
                        "cost": 99,
                    }
                },
            ],
        }

        observation = self.parse_payload(payload)

        self.assertIsInstance(observation, GameObservation)
        self.assertEqual(observation.state_id, 41)
        self.assertEqual(observation.blind_key, "bl_small")
        self.assertEqual(observation.deck_key, "b_erratic")
        self.assertEqual(observation.score, ObservedScore(current=75, target=300))
        self.assertEqual(observation.dollars, 10)
        self.assertEqual(observation.hands_left, 4)
        self.assertEqual(observation.discards_left, 2)
        self.assertEqual(observation.jokers, ())
        self.assertEqual(observation.cards_in_hand, ())
        self.assertEqual(observation.selected_cards, ())
        self.assertEqual(observation.cards_in_deck, ())
        self.assertEqual(len(observation.shop_items), 3)
        self.assertEqual(observation.shop_items[0].joker.key, "j_blue_joker")
        self.assertEqual(observation.shop_items[0].joker.instance_id, 101)
        self.assertTrue(observation.shop_items[0].joker.eternal)
        self.assertEqual(observation.shop_items[1].voucher.key, "v_clearance_sale")
        self.assertEqual(observation.shop_items[1].voucher.cost, 10)
        self.assertEqual(observation.shop_items[2].pack.key, "p_arcana_normal_1")
        self.assertEqual(observation.shop_items[2].pack.instance_id, 202)
        self.assertEqual(observation.shop_items[2].pack.cost, 4)

    def test_parse_missing_file_returns_none(self) -> None:
        root = self.make_fixture_root()
        try:
            missing_path = root / "missing_live_state.json"
            observation = LiveObservationParser().parse_file(missing_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

        self.assertIsNone(observation)

    def test_parse_invalid_json_returns_none(self) -> None:
        root = self.make_fixture_root()
        try:
            live_state_path = root / "live_state.json"
            live_state_path.write_text("{invalid", encoding="utf-8")
            observation = LiveObservationParser().parse_file(live_state_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

        self.assertIsNone(observation)

    def parse_payload(self, payload: dict[str, object]) -> GameObservation | None:
        root = self.make_fixture_root()
        try:
            live_state_path = root / "live_state.json"
            live_state_path.write_text(json.dumps(payload), encoding="utf-8")
            return LiveObservationParser().parse_file(live_state_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"live_parser_{uuid4().hex}"
        root.mkdir()
        return root

    def cleanup_fixture_base(self) -> None:
        base = Path("tests_tmp")
        try:
            base.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()

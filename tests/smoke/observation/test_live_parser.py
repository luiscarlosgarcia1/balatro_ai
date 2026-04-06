from __future__ import annotations

import json
import unittest

from balatro_ai.models import GameObservation, ObservedJoker, ObservedPack, ObservedScore, ObservedVoucher
from balatro_ai.observation.parser import LiveObservationParser
from tests.smoke.support import temporary_test_root


class LiveParserSmokeTests(unittest.TestCase):
    def test_parse_shop_items_into_concrete_typed_observation(self) -> None:
        payload = {
            "source": "live_state_exporter",
            "state_id": 41,
            "interaction_phase": "shop",
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
                        "cost": 6,
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
        self.assertIsInstance(observation.shop_items[0], ObservedJoker)
        self.assertEqual(observation.shop_items[0].key, "j_blue_joker")
        self.assertEqual(observation.shop_items[0].instance_id, 101)
        self.assertTrue(observation.shop_items[0].eternal)
        self.assertEqual(observation.shop_items[0].cost, 6)
        self.assertIsNone(observation.shop_items[0].sell_cost)
        self.assertIsInstance(observation.shop_items[1], ObservedVoucher)
        self.assertEqual(observation.shop_items[1].key, "v_clearance_sale")
        self.assertEqual(observation.shop_items[1].cost, 10)
        self.assertIsInstance(observation.shop_items[2], ObservedPack)
        self.assertEqual(observation.shop_items[2].key, "p_arcana_normal_1")
        self.assertEqual(observation.shop_items[2].instance_id, 202)
        self.assertEqual(observation.shop_items[2].cost, 4)

    def test_parse_missing_file_returns_none(self) -> None:
        with temporary_test_root("live_parser") as root:
            missing_path = root / "missing_live_state.json"
            observation = LiveObservationParser().parse_file(missing_path)

        self.assertIsNone(observation)

    def test_parse_invalid_json_returns_none(self) -> None:
        with temporary_test_root("live_parser") as root:
            live_state_path = root / "live_state.json"
            live_state_path.write_text("{invalid", encoding="utf-8")
            observation = LiveObservationParser().parse_file(live_state_path)

        self.assertIsNone(observation)

    def test_parse_deck_key_object_uses_nested_key(self) -> None:
        observation = self.parse_payload(
            {
                "state_id": 9,
                "deck_key": {
                    "key": "b_yellow",
                    "name": "Yellow Deck",
                },
                "score": {"current": 0, "target": 100},
                "dollars": 0,
                "hands_left": 0,
                "discards_left": 0,
            }
        )

        self.assertIsNotNone(observation)
        self.assertEqual(observation.deck_key, "b_yellow")

    def parse_payload(self, payload: dict[str, object]) -> GameObservation | None:
        with temporary_test_root("live_parser") as root:
            live_state_path = root / "live_state.json"
            live_state_path.write_text(json.dumps(payload), encoding="utf-8")
            return LiveObservationParser().parse_file(live_state_path)


if __name__ == "__main__":
    unittest.main()

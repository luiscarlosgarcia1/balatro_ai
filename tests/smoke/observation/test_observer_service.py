from __future__ import annotations

import json
import unittest

from balatro_ai.models import GameObservation, ObservedJoker, ObservedPack, ObservedScore, ObservedVoucher
from balatro_ai.observation import BalatroObserver, BalatroPaths
from tests.smoke.support import temporary_test_root


class ObserverServiceSmokeTests(unittest.TestCase):
    def test_observe_live_state_returns_concrete_shop_items(self) -> None:
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
                        "perishable": True,
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
                    "voucher": {
                        "cost": 50,
                    }
                },
            ],
        }
        with temporary_test_root("observer_service") as root:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(payload), encoding="utf-8")

            observation = BalatroObserver(paths=BalatroPaths(root=root)).observe()

        self.assertIsInstance(observation, GameObservation)
        self.assertEqual(observation.state_id, 41)
        self.assertEqual(observation.dollars, 10)
        self.assertEqual(observation.score, ObservedScore(current=75, target=300))
        self.assertEqual(len(observation.shop_items), 3)
        self.assertIsInstance(observation.shop_items[0], ObservedJoker)
        self.assertEqual(observation.shop_items[0].key, "j_blue_joker")
        self.assertTrue(observation.shop_items[0].perishable)
        self.assertIsInstance(observation.shop_items[1], ObservedVoucher)
        self.assertEqual(observation.shop_items[1].key, "v_clearance_sale")
        self.assertEqual(observation.shop_items[1].instance_id, -2)
        self.assertIsInstance(observation.shop_items[2], ObservedPack)
        self.assertEqual(observation.shop_items[2].key, "p_arcana_normal_1")

    def test_observe_raises_file_not_found_when_live_state_is_missing(self) -> None:
        with temporary_test_root("observer_service") as root:
            with self.assertRaises(FileNotFoundError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()

    def test_observe_raises_value_error_for_invalid_live_state_json(self) -> None:
        with temporary_test_root("observer_service") as root:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(ValueError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()

    def test_observe_raises_value_error_for_non_observation_payload(self) -> None:
        with temporary_test_root("observer_service") as root:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(["not", "an", "observation"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation, ObservedScore
from balatro_ai.observation import BalatroObserver, BalatroPaths


class ObserverServiceSmokeTests(unittest.TestCase):
    def test_observe_live_state_returns_wrapped_shop_items(self) -> None:
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
        root = self.make_fixture_root()
        try:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(payload), encoding="utf-8")

            observation = BalatroObserver(paths=BalatroPaths(root=root)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

        self.assertIsInstance(observation, GameObservation)
        self.assertEqual(observation.state_id, 41)
        self.assertEqual(observation.dollars, 10)
        self.assertEqual(observation.score, ObservedScore(current=75, target=300))
        self.assertEqual(len(observation.shop_items), 3)
        self.assertEqual(observation.shop_items[0].joker.key, "j_blue_joker")
        self.assertTrue(observation.shop_items[0].joker.perishable)
        self.assertEqual(observation.shop_items[1].voucher.key, "v_clearance_sale")
        self.assertEqual(observation.shop_items[2].pack.key, "p_arcana_normal_1")

    def test_observe_raises_file_not_found_when_live_state_is_missing(self) -> None:
        root = self.make_fixture_root()
        try:
            with self.assertRaises(FileNotFoundError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def test_observe_raises_value_error_for_invalid_live_state_json(self) -> None:
        root = self.make_fixture_root()
        try:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(ValueError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def test_observe_raises_value_error_for_non_observation_payload(self) -> None:
        root = self.make_fixture_root()
        try:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(["not", "an", "observation"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                BalatroObserver(paths=BalatroPaths(root=root)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"observer_service_{uuid4().hex}"
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

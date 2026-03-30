from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation
from balatro_ai.observation import BalatroObserver, BalatroPaths


class ObserverServiceSmokeTests(unittest.TestCase):
    def test_observe_live_state_returns_typed_observation(self) -> None:
        payload = {
            "state": {
                "source": "live_state_exporter",
                "state_id": 41,
                "interaction_phase": "shop",
                "blind_key": "bl_small",
                "deck_key": "b_erratic",
                "score": {"current": 75, "target": 300},
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
            }
        }
        root = self.make_fixture_root()
        try:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(payload), encoding="utf-8")

            observation = BalatroObserver(paths=BalatroPaths(root=root, profile=2)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

        self.assertIsInstance(observation, GameObservation)
        self.assertEqual(observation.source, "live_state_exporter")
        self.assertEqual(observation.state_id, 41)
        self.assertEqual(observation.interaction_phase, "shop")
        self.assertEqual(observation.score_current, 75)
        self.assertEqual(observation.score_target, 300)

    def test_observe_raises_file_not_found_when_live_state_is_missing(self) -> None:
        root = self.make_fixture_root()
        try:
            save_path = root / "1" / "save.jkr"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text("legacy save should not be consulted", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                BalatroObserver(paths=BalatroPaths(root=root, profile=1)).observe()
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
                BalatroObserver(paths=BalatroPaths(root=root, profile=2)).observe()
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
                BalatroObserver(paths=BalatroPaths(root=root, profile=2)).observe()
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

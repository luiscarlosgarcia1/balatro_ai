from __future__ import annotations

import json
import shutil
import unittest
import zlib
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

    def test_observe_save_fallback_returns_typed_observation(self) -> None:
        legacy_save_payload = (
            'return {["STATE"]=5,["BLIND"]={["config_blind"]="bl_big",["chips"]=to_big({300}, 1)},'
            '["GAME"]={["chips"]=to_big({120}, 1),["dollars"]=10,["current_round"]={["hands_left"]=3,["discards_left"]=1},'
            '["round_resets"]={["hands"]=4,["discards"]=2},["blind_on_deck"]="bl_big",["pseudorandom"]={["seed"]="seed42"}},'
            '["cardAreas"]={["hand"]={["cards"]={},["config"]={["card_count"]=2}},["jokers"]={["cards"]={},["config"]={["card_count"]=1}}}}'
        )
        root = self.make_fixture_root()
        try:
            save_path = root / "1" / "save.jkr"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(zlib.compress(legacy_save_payload.encode("utf-8")))

            observation = BalatroObserver(paths=BalatroPaths(root=root, profile=1)).observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

        self.assertIsInstance(observation, GameObservation)
        self.assertEqual(observation.source, "save_file")
        self.assertEqual(observation.state_id, 5)
        self.assertEqual(observation.interaction_phase, "state_5")
        self.assertEqual(observation.score_current, 120)
        self.assertEqual(observation.score_target, 300)

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

from __future__ import annotations

import unittest

import balatro_ai
import balatro_ai.observation as observation_api
from balatro_ai.observation.paths import BalatroPaths as PathsImpl
from balatro_ai.observation.service import BalatroObserver as ObserverImpl


class ObserverPublicImportsSmokeTests(unittest.TestCase):
    def test_balatro_paths_exposes_live_state_path(self) -> None:
        paths = PathsImpl()

        self.assertEqual(str(paths.live_state_path).replace("\\", "/").split("/")[-2:], ["ai", "live_state.json"])

    def test_package_root_exports_current_observer_surface(self) -> None:
        self.assertIs(balatro_ai.BalatroPaths, PathsImpl)
        self.assertIs(balatro_ai.BalatroObserver, ObserverImpl)

    def test_observation_package_exports_current_observer_surface(self) -> None:
        self.assertIs(observation_api.BalatroPaths, PathsImpl)
        self.assertIs(observation_api.BalatroObserver, ObserverImpl)


if __name__ == "__main__":
    unittest.main()

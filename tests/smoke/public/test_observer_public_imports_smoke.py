from __future__ import annotations

import unittest

import balatro_ai
import balatro_ai.observation as observation_api
from balatro_ai.observation.paths import BalatroPaths as PathsImpl
from balatro_ai.observation.service import BalatroObserver as ObserverImpl


class ObserverPublicImportsSmokeTests(unittest.TestCase):
    def test_package_root_exports_current_observer_surface(self) -> None:
        self.assertIs(balatro_ai.BalatroPaths, PathsImpl)
        self.assertIs(balatro_ai.BalatroObserver, ObserverImpl)
        self.assertFalse(hasattr(balatro_ai, "BalatroSaveObserver"))

    def test_observation_package_exports_current_observer_surface(self) -> None:
        self.assertIs(observation_api.BalatroPaths, PathsImpl)
        self.assertIs(observation_api.BalatroObserver, ObserverImpl)
        self.assertFalse(hasattr(observation_api, "BalatroSaveObserver"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import balatro_ai
import balatro_ai.observation as observation_api
from balatro_ai.observation.paths import BalatroPaths as PathsImpl
from balatro_ai.observation.service import BalatroSaveObserver as ObserverImpl


class ObserverPublicImportsSmokeTests(unittest.TestCase):
    def test_package_root_exports_current_observer_surface(self) -> None:
        self.assertIs(balatro_ai.BalatroPaths, PathsImpl)
        self.assertIs(balatro_ai.BalatroSaveObserver, ObserverImpl)

    def test_observation_package_exports_current_observer_surface(self) -> None:
        self.assertIs(observation_api.BalatroPaths, PathsImpl)
        self.assertIs(observation_api.BalatroSaveObserver, ObserverImpl)


if __name__ == "__main__":
    unittest.main()

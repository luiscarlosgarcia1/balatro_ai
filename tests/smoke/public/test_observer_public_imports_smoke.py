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
        self.assertFalse(hasattr(balatro_ai, "LightweightCapturePlan"))
        self.assertFalse(hasattr(balatro_ai, "CaptureBand"))
        self.assertFalse(hasattr(balatro_ai, "PixelRect"))
        self.assertFalse(hasattr(balatro_ai, "SavePayloadDecoder"))
        self.assertFalse(hasattr(balatro_ai, "SaveSnapshot"))

    def test_observation_package_exports_current_observer_surface(self) -> None:
        self.assertIs(observation_api.BalatroPaths, PathsImpl)
        self.assertIs(observation_api.BalatroObserver, ObserverImpl)
        self.assertFalse(hasattr(observation_api, "BalatroSaveObserver"))
        self.assertFalse(hasattr(observation_api, "LightweightCapturePlan"))
        self.assertFalse(hasattr(observation_api, "CaptureBand"))
        self.assertFalse(hasattr(observation_api, "PixelRect"))
        self.assertFalse(hasattr(observation_api, "SavePayloadDecoder"))
        self.assertFalse(hasattr(observation_api, "SaveSnapshot"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation
from obs_test import STATUS_LOG_NAME, append_status, write_observation


class ObsTestFileOutputSmokeTests(unittest.TestCase):
    def test_append_status_writes_log_file(self) -> None:
        root = self.make_fixture_root()
        try:
            log_path = root / STATUS_LOG_NAME
            append_status(log_path, "[obs_test] file-only status")

            self.assertTrue(log_path.exists())
            self.assertEqual(log_path.read_text(encoding="utf-8"), "[obs_test] file-only status\n")
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def test_write_observation_still_writes_report_file(self) -> None:
        root = self.make_fixture_root()
        try:
            observation = GameObservation(
                source="live_state_exporter",
                state_id=3,
                interaction_phase="shop",
                money=5,
                hands_left=4,
                discards_left=2,
            )

            write_observation(root, 1, observation)

            report_path = root / "observation_0001.txt"
            self.assertTrue(report_path.exists())
            self.assertIn("interaction_phase: shop", report_path.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"obs_test_output_{uuid4().hex}"
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

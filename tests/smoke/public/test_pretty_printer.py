from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation
from pretty_printer import render_observation, write_observation_print


class PrettyPrinterSmokeTests(unittest.TestCase):
    def test_render_observation_returns_readable_dataclass_tree(self) -> None:
        observation = GameObservation(
            source="mock",
            state_id=12,
            interaction_phase="shop",
            money=9,
            hands_left=0,
            discards_left=0,
        )

        rendered = render_observation(observation)

        self.assertTrue(rendered.startswith("GameObservation(\n"))
        self.assertIn("\n  interaction_phase='shop',", rendered)
        self.assertIn("\n  money=9,", rendered)
        self.assertTrue(rendered.endswith("\n)"))

    def test_write_observation_print_writes_readable_tree_to_txt_file(self) -> None:
        observation = GameObservation(
            source="mock",
            state_id=13,
            interaction_phase="blind_select",
            money=4,
            hands_left=4,
            discards_left=3,
        )
        root = self.make_fixture_root()
        try:
            output_path = write_observation_print(observation, output_dir=root / "prints")
            self.assertEqual(output_path.suffix, ".txt")
            self.assertEqual(output_path.parent.name, "prints")
            self.assertEqual(output_path.read_text(encoding="utf-8"), render_observation(observation))
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"pretty_printer_{uuid4().hex}"
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

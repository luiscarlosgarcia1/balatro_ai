from __future__ import annotations

import unittest

from balatro_ai.models import GameObservation, ObservedScore
from pretty_printer import render_observation, write_observation_print
from tests.smoke.support import temporary_test_root


class PrettyPrinterSmokeTests(unittest.TestCase):
    def test_render_observation_returns_readable_dataclass_tree(self) -> None:
        observation = GameObservation(
            state_id=12,
            dollars=9,
            hands_left=0,
            discards_left=0,
            score=ObservedScore(current=90, target=300),
        )

        rendered = render_observation(observation)

        self.assertTrue(rendered.startswith("GameObservation(\n"))
        self.assertIn("\n  dollars=9,", rendered)
        self.assertIn("\n  score=ObservedScore(", rendered)
        self.assertTrue(rendered.endswith("\n)"))

    def test_write_observation_print_writes_readable_tree_to_txt_file(self) -> None:
        observation = GameObservation(
            state_id=13,
            dollars=4,
            hands_left=4,
            discards_left=3,
            score=ObservedScore(current=0, target=300),
        )
        with temporary_test_root("pretty_printer") as root:
            output_path = write_observation_print(observation, output_dir=root / "prints")
            self.assertEqual(output_path.suffix, ".txt")
            self.assertEqual(output_path.parent.name, "prints")
            self.assertEqual(output_path.read_text(encoding="utf-8"), render_observation(observation))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from balatro_ai.models import GameObservation, ObservedInterest, ObservedReference
from obs_test import format_observation, write_observation


class ObservationFormatSmokeTests(unittest.TestCase):
    def test_format_observation_accepts_typed_observation(self) -> None:
        observation = GameObservation(
            source="live_state_exporter",
            state_id=7,
            interaction_phase="shop",
            blind_key="bl_small",
            deck_key="b_erratic",
            money=14,
            hands_left=4,
            discards_left=2,
            score_current=150,
            score_target=800,
            interest=ObservedInterest(amount=3, cap=25, no_interest=False),
            selected_cards=(ObservedReference(zone="cards_in_hand", card_key="s_a"),),
            notes=("seen_at=2026-03-26T00:00:00+00:00",),
        )

        formatted = format_observation(observation)

        self.assertIn("interaction_phase: shop", formatted)
        self.assertIn("score: 150/800", formatted)
        self.assertIn("interest: amount=3, cap=25, no_interest=false", formatted)
        self.assertIn("selected_cards:", formatted)
        self.assertIn("cards_in_hand: card_key=s_a", formatted)

    def test_write_observation_writes_text_report_instead_of_json(self) -> None:
        observation = GameObservation(
            source="live_state_exporter",
            state_id=8,
            interaction_phase="shop",
            money=10,
            hands_left=4,
            discards_left=2,
        )
        root = self.make_fixture_root()
        try:
            write_observation(root, 1, observation)
            txt_path = root / "observation_0001.txt"
            json_path = root / "observation_0001.json"
            self.assertTrue(txt_path.exists())
            self.assertFalse(json_path.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"observation_format_{uuid4().hex}"
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

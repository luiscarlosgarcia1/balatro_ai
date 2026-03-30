from __future__ import annotations

from datetime import datetime, timezone
import unittest

from balatro_ai.models import (
    GameObservation,
    ObservedCard,
    ObservedInterest,
    ObservedJoker,
    ObservedReference,
)
from balatro_ai.observation.canonical import CANONICAL_TOP_LEVEL_KEYS, serialize_observation


class ObservationExportSmokeTests(unittest.TestCase):
    def test_serialize_observation_exports_canonical_json_shape(self) -> None:
        observation = GameObservation(
            source="live_state_exporter",
            state_id=8,
            interaction_phase="shop",
            blind_key="bl_small",
            deck_key="b_erratic",
            money=14,
            hands_left=4,
            discards_left=2,
            score_current=150,
            score_target=800,
            joker_slots=5,
            jokers=(
                ObservedJoker(
                    key="j_greedy_joker",
                    rarity="Common",
                    edition="Foil",
                ),
            ),
            interest=ObservedInterest(amount=3, cap=25, no_interest=False),
            cards_in_hand=(
                ObservedCard(card_key="s_10", suit="Spades", rank="10"),
                ObservedCard(card_key="c_a", suit="Clubs", rank="Ace"),
            ),
            selected_cards=(
                ObservedReference(zone="cards_in_hand", card_key="s_10"),
            ),
            notes=("exporter=live_state_exporter",),
            seen_at=datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc),
        )

        payload = serialize_observation(observation)

        self.assertEqual(tuple(payload.keys()), CANONICAL_TOP_LEVEL_KEYS)
        self.assertEqual(payload["source"], "live_state_exporter")
        self.assertEqual(payload["state_id"], 8)
        self.assertEqual(payload["interaction_phase"], "shop")
        self.assertEqual(payload["score"], {"current": 150, "target": 800})
        self.assertEqual(payload["interest"], {"amount": 3, "cap": 25, "no_interest": False})
        self.assertEqual(
            payload["jokers"],
            [{"key": "j_greedy_joker", "rarity": "common", "edition": "foil"}],
        )
        self.assertEqual(
            payload["cards_in_hand"],
            [{"card_key": "c_a"}, {"card_key": "s_10"}],
        )
        self.assertEqual(
            payload["selected_cards"],
            [{"zone": "cards_in_hand", "card_key": "s_10"}],
        )
        self.assertEqual(
            payload["notes"],
            ["exporter=live_state_exporter", "seen_at=2026-03-30T12:00:00+00:00"],
        )


if __name__ == "__main__":
    unittest.main()

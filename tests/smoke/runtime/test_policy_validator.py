from __future__ import annotations

import unittest

from balatro_ai.models import GameObservation
from balatro_ai.policy import DemoPolicy, RuleBasedValidator


class DemoPolicySmokeTests(unittest.TestCase):
    def test_demo_policy_selects_blind_during_blind_select_phase(self) -> None:
        action = DemoPolicy().choose_action(
            GameObservation(
                source="mock",
                state_id=6,
                interaction_phase="blind_select",
                blind_key="bl_small",
                money=4,
                hands_left=4,
                discards_left=3,
            )
        )

        self.assertEqual(action.kind, "select_blind")
        self.assertEqual(action.target, "bl_small")

    def test_demo_policy_returns_continue_for_unhandled_phase(self) -> None:
        action = DemoPolicy().choose_action(
            GameObservation(
                source="mock",
                state_id=7,
                interaction_phase="reward",
                money=3,
                hands_left=0,
                discards_left=0,
            )
        )

        self.assertEqual(action.kind, "continue")


class RuleBasedValidatorSmokeTests(unittest.TestCase):
    def test_validator_rejects_invalid_action_for_phase(self) -> None:
        result = RuleBasedValidator().validate(
            GameObservation(
                source="mock",
                state_id=8,
                interaction_phase="shop",
                money=8,
                hands_left=0,
                discards_left=0,
            ),
            action=DemoPolicy().choose_action(
                GameObservation(
                    source="mock",
                    state_id=9,
                    interaction_phase="play_hand",
                    money=8,
                    hands_left=1,
                    discards_left=1,
                )
            ),
        )

        self.assertFalse(result.accepted)
        self.assertIn("not valid during phase 'shop'", result.notes[0])

    def test_validator_rejects_buy_joker_without_enough_money(self) -> None:
        result = RuleBasedValidator().validate(
            GameObservation(
                source="mock",
                state_id=10,
                interaction_phase="shop",
                money=3,
                hands_left=0,
                discards_left=0,
            ),
            action=DemoPolicy().choose_action(
                GameObservation(
                    source="mock",
                    state_id=11,
                    interaction_phase="shop",
                    money=8,
                    hands_left=0,
                    discards_left=0,
                )
            ),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.notes, ("Cannot buy a joker without enough money.",))


if __name__ == "__main__":
    unittest.main()

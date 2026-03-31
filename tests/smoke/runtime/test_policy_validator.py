from __future__ import annotations

import unittest

from balatro_ai.models import GameObservation, ObservedBlind, ObservedScore
from balatro_ai.policy import DemoPolicy, RuleBasedValidator


def make_observation(**overrides: object) -> GameObservation:
    payload: dict[str, object] = {
        "state_id": 0,
        "dollars": 0,
        "hands_left": 0,
        "discards_left": 0,
        "score": ObservedScore(current=0, target=0),
    }
    payload.update(overrides)
    return GameObservation(**payload)


class DemoPolicySmokeTests(unittest.TestCase):
    def test_demo_policy_selects_blind_during_blind_select_phase(self) -> None:
        action = DemoPolicy().choose_action(
            make_observation(
                state_id=6,
                blind_key="bl_small",
                dollars=4,
                hands_left=4,
                discards_left=3,
                blinds=(ObservedBlind(key="bl_small", state="upcoming"),),
            )
        )

        self.assertEqual(action.kind, "select_blind")
        self.assertEqual(action.target, "bl_small")

    def test_demo_policy_returns_continue_for_unhandled_phase(self) -> None:
        action = DemoPolicy().choose_action(
            make_observation(
                state_id=7,
                dollars=3,
                hands_left=0,
                discards_left=0,
            )
        )

        self.assertEqual(action.kind, "continue")


class RuleBasedValidatorSmokeTests(unittest.TestCase):
    def test_validator_rejects_invalid_action_for_phase(self) -> None:
        result = RuleBasedValidator().validate(
            make_observation(
                state_id=8,
                dollars=8,
                hands_left=0,
                discards_left=0,
                reroll_cost=5,
            ),
            action=DemoPolicy().choose_action(
                make_observation(
                    state_id=9,
                    dollars=8,
                    hands_left=1,
                    discards_left=1,
                )
            ),
        )

        self.assertFalse(result.accepted)
        self.assertIn("not valid during phase 'shop'", result.notes[0])

    def test_validator_rejects_buy_joker_without_enough_money(self) -> None:
        result = RuleBasedValidator().validate(
            make_observation(
                state_id=10,
                dollars=3,
                hands_left=0,
                discards_left=0,
                reroll_cost=5,
            ),
            action=DemoPolicy().choose_action(
                make_observation(
                    state_id=11,
                    dollars=8,
                    hands_left=0,
                    discards_left=0,
                    reroll_cost=5,
                )
            ),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.notes, ("Cannot buy a joker without enough money.",))


if __name__ == "__main__":
    unittest.main()

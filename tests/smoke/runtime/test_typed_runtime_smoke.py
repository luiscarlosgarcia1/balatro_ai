from __future__ import annotations

import unittest

from balatro_ai.models import GameAction, GameObservation
from balatro_ai.policy import DemoPolicy, RuleBasedValidator
from balatro_ai.runtime import EpisodeRunner, ScriptedObserver


class TypedRuntimeSmokeTests(unittest.TestCase):
    def test_runner_executes_typed_observation_flow_and_records_same_instance(self) -> None:
        observation = GameObservation(
            source="mock",
            state_id=1,
            interaction_phase="shop",
            money=6,
            hands_left=0,
            discards_left=0,
            score_current=90,
            score_target=300,
        )
        policy = RecordingDemoPolicy()
        validator = RecordingRuleBasedValidator()
        executor = RecordingExecutor()

        records = EpisodeRunner(
            observer=ScriptedObserver([observation]),
            policy=policy,
            validator=validator,
            executor=executor,
        ).run()

        self.assertIs(policy.observations[0], observation)
        self.assertIs(validator.observations[0], observation)
        self.assertEqual(executor.actions[0].kind, "buy_joker")
        self.assertIs(records[0].observation, observation)
        self.assertTrue(records[0].validation.accepted)

    def test_runner_skips_execution_when_typed_action_is_rejected(self) -> None:
        observation = GameObservation(
            source="mock",
            state_id=2,
            interaction_phase="shop",
            money=2,
            hands_left=0,
            discards_left=0,
            score_current=90,
            score_target=300,
        )
        executor = RecordingExecutor()

        records = EpisodeRunner(
            observer=ScriptedObserver([observation]),
            policy=InvalidShopPolicy(),
            validator=RuleBasedValidator(),
            executor=executor,
        ).run()

        self.assertFalse(records[0].validation.accepted)
        self.assertEqual(executor.actions, [])


class RecordingDemoPolicy(DemoPolicy):
    def __init__(self) -> None:
        self.observations: list[GameObservation] = []

    def choose_action(self, observation: GameObservation) -> GameAction:
        self.observations.append(observation)
        return super().choose_action(observation)


class RecordingRuleBasedValidator(RuleBasedValidator):
    def __init__(self) -> None:
        self.observations: list[GameObservation] = []

    def validate(self, observation: GameObservation, action: GameAction):
        self.observations.append(observation)
        return super().validate(observation, action)


class InvalidShopPolicy:
    def choose_action(self, observation: GameObservation) -> GameAction:
        return GameAction(kind="play_best_hand", reason="force rejection")


class RecordingExecutor:
    def __init__(self) -> None:
        self.actions: list[GameAction] = []

    def execute(self, action: GameAction) -> None:
        self.actions.append(action)


if __name__ == "__main__":
    unittest.main()

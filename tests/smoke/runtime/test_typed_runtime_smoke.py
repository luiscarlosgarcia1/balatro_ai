from __future__ import annotations

import importlib.util
from typing import get_type_hints
import unittest
from unittest.mock import patch

from balatro_ai.interfaces import Observer
from balatro_ai.models import GameAction, GameObservation
from balatro_ai.models import StepRecord
from balatro_ai.policy import DemoPolicy, RuleBasedValidator
from balatro_ai.runtime import EpisodeRunner, ScriptedObserver


class TypedRuntimeSmokeTests(unittest.TestCase):
    def test_typed_runtime_contract_uses_game_observation_for_observer_and_step_record(self) -> None:
        self.assertIs(get_type_hints(Observer.observe)["return"], GameObservation)
        self.assertIs(get_type_hints(StepRecord)["observation"], GameObservation)

    def test_python_side_observation_serializer_module_is_removed(self) -> None:
        self.assertIsNone(importlib.util.find_spec("balatro_ai.observation.canonical"))

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

        runner = EpisodeRunner(
            observer=ScriptedObserver([observation]),
            policy=policy,
            validator=validator,
            executor=executor,
        )

        with patch(
            "json.dumps",
            side_effect=AssertionError(
                "Typed runtime-policy-validator flow must not reintroduce Python-side JSON serialization."
            ),
        ):
            records = runner.run()

        self.assertIs(policy.observations[0], observation)
        self.assertIs(validator.observations[0], observation)
        self.assertIsInstance(policy.observations[0], GameObservation)
        self.assertIsInstance(validator.observations[0], GameObservation)
        self.assertEqual(executor.actions[0].kind, "buy_joker")
        self.assertIs(records[0].observation, observation)
        self.assertIsInstance(records[0].observation, GameObservation)
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

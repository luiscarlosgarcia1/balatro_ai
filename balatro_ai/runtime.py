from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .policy import DemoPolicy, RuleBasedValidator
from .interfaces import Executor, Observer, Policy, Validator
from .models import GameAction, GameObservation, ObservationPayload, RuntimeObservation, StepRecord


class ScriptedObserver:
    """Returns a fixed sequence of mock states for local development."""

    def __init__(self, observations: Iterable[RuntimeObservation]) -> None:
        self._observations = iter(observations)

    def observe(self) -> RuntimeObservation:
        return next(self._observations)


class LoggingExecutor:
    """Stands in for real keyboard and mouse automation."""

    def execute(self, action: GameAction) -> None:
        print(f"EXECUTE  kind={action.kind} target={action.target} reason={action.reason}")


@dataclass
class EpisodeRunner:
    """Runs one gameplay loop for a single Balatro-playing policy."""

    observer: Observer
    policy: Policy
    validator: Validator
    executor: Executor

    def run(self) -> list[StepRecord]:
        records: list[StepRecord] = []

        while True:
            try:
                observation = self.observer.observe()
            except StopIteration:
                break

            score_current, score_target = _observation_score(observation)
            print(
                "OBSERVE  "
                f"phase={_observation_phase(observation)} money={_observation_money(observation)} "
                f"hands={_observation_hands_left(observation)} discards={_observation_discards_left(observation)} "
                f"score={score_current}/{score_target}"
            )
            action = self.policy.choose_action(observation)
            validation = self.validator.validate(observation, action)

            print(
                f"DECIDE   kind={action.kind} accepted={validation.accepted} "
                f"notes={'; '.join(validation.notes)}"
            )

            if validation.accepted:
                self.executor.execute(action)
            else:
                print("SKIP     rejected action was not executed")

            records.append(
                StepRecord(
                    observation=observation,
                    action=action,
                    validation=validation,
                )
            )

        return records


def create_demo_runner() -> EpisodeRunner:
    observations = [
        {
            "source": "mock",
            "state_id": 1,
            "interaction_phase": "blind_select",
            "blind_key": "bl_small",
            "deck_key": None,
            "stake_id": None,
            "score": {"current": 0, "target": 300},
            "money": 4,
            "hands_left": 4,
            "discards_left": 3,
            "ante": None,
            "round_count": None,
            "joker_slots": None,
            "jokers": [],
            "consumable_slots": None,
            "consumables": [],
            "vouchers": [],
            "tags": [],
            "shop_items": [],
            "reroll_cost": None,
            "interest": None,
            "run_info": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "cards_in_deck": [],
            "blinds": [],
            "notes": ["Small blind available."],
        },
        {
            "source": "mock",
            "state_id": 2,
            "interaction_phase": "play_hand",
            "blind_key": "bl_small",
            "deck_key": None,
            "stake_id": None,
            "score": {"current": 90, "target": 300},
            "money": 4,
            "hands_left": 4,
            "discards_left": 3,
            "ante": None,
            "round_count": None,
            "joker_slots": None,
            "jokers": [{"key": "j_greedy_joker"}],
            "consumable_slots": None,
            "consumables": [],
            "vouchers": [],
            "tags": [],
            "shop_items": [],
            "reroll_cost": None,
            "interest": None,
            "run_info": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "cards_in_deck": [],
            "blinds": [],
            "notes": [],
        },
        {
            "source": "mock",
            "state_id": 3,
            "interaction_phase": "shop",
            "blind_key": None,
            "deck_key": None,
            "stake_id": None,
            "score": {"current": 420, "target": 300},
            "money": 6,
            "hands_left": 0,
            "discards_left": 0,
            "ante": None,
            "round_count": None,
            "joker_slots": None,
            "jokers": [{"key": "j_greedy_joker"}],
            "consumable_slots": None,
            "consumables": [],
            "vouchers": [],
            "tags": [],
            "shop_items": [],
            "reroll_cost": None,
            "interest": None,
            "run_info": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "cards_in_deck": [],
            "blinds": [],
            "notes": [],
        },
    ]
    return EpisodeRunner(
        observer=ScriptedObserver(observations),
        policy=DemoPolicy(),
        validator=RuleBasedValidator(),
        executor=LoggingExecutor(),
    )


def main() -> None:
    records = create_demo_runner().run()
    accepted = sum(1 for record in records if record.validation.accepted)
    print(f"SUMMARY  steps={len(records)} accepted_actions={accepted}")


def _observation_phase(observation: RuntimeObservation) -> str:
    if isinstance(observation, GameObservation):
        return observation.interaction_phase
    return str(observation.get("interaction_phase") or "unknown")


def _observation_money(observation: RuntimeObservation) -> int:
    if isinstance(observation, GameObservation):
        return observation.money
    return int(observation.get("money") or 0)


def _observation_hands_left(observation: RuntimeObservation) -> int:
    if isinstance(observation, GameObservation):
        return observation.hands_left
    return int(observation.get("hands_left") or 0)


def _observation_discards_left(observation: RuntimeObservation) -> int:
    if isinstance(observation, GameObservation):
        return observation.discards_left
    return int(observation.get("discards_left") or 0)


def _observation_score(observation: RuntimeObservation) -> tuple[int | None, int | None]:
    if isinstance(observation, GameObservation):
        return observation.score_current, observation.score_target
    score = observation.get("score") or {}
    return score.get("current"), score.get("target")

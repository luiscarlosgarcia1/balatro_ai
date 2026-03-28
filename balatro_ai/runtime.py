from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .policy import DemoPolicy, RuleBasedValidator
from .interfaces import Executor, Observer, Policy, Validator
from .models import GameAction, ObservationPayload, StepRecord


class ScriptedObserver:
    """Returns a fixed sequence of mock states for local development."""

    def __init__(self, observations: Iterable[ObservationPayload]) -> None:
        self._observations = iter(observations)

    def observe(self) -> ObservationPayload:
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

            score = observation.get("score") or {}
            print(
                "OBSERVE  "
                f"phase={observation.get('interaction_phase')} money={observation.get('money')} "
                f"hands={observation.get('hands_left')} discards={observation.get('discards_left')} "
                f"score={score.get('current')}/{score.get('target')}"
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
            "joker_count": 0,
            "jokers": [],
            "consumable_slots": None,
            "consumables": [],
            "shop_vouchers": [],
            "vouchers": [],
            "skip_tags": [],
            "tags": [],
            "shop_items": [],
            "shop_discounts": [],
            "reroll_cost": None,
            "interest": None,
            "inflation": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "highlighted_card": None,
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
            "joker_count": 1,
            "jokers": [{"key": "j_greedy_joker"}],
            "consumable_slots": None,
            "consumables": [],
            "shop_vouchers": [],
            "vouchers": [],
            "skip_tags": [],
            "tags": [],
            "shop_items": [],
            "shop_discounts": [],
            "reroll_cost": None,
            "interest": None,
            "inflation": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "highlighted_card": None,
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
            "joker_count": 1,
            "jokers": [{"key": "j_greedy_joker"}],
            "consumable_slots": None,
            "consumables": [],
            "shop_vouchers": [],
            "vouchers": [],
            "skip_tags": [],
            "tags": [],
            "shop_items": [],
            "shop_discounts": [],
            "reroll_cost": None,
            "interest": None,
            "inflation": None,
            "pack_contents": None,
            "hand_size": None,
            "cards_in_hand": [],
            "selected_cards": [],
            "highlighted_card": None,
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

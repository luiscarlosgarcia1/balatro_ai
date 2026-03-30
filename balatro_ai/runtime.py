from __future__ import annotations

from dataclasses import dataclass
from .interfaces import Executor, Observer, Policy, Validator
from .models import StepRecord


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

            print(
                "OBSERVE  "
                f"phase={observation.interaction_phase} money={observation.money} "
                f"hands={observation.hands_left} discards={observation.discards_left} "
                f"score={observation.score_current}/{observation.score_target}"
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

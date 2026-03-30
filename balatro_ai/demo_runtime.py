from __future__ import annotations

from typing import Iterable

from .models import GameAction, GameObservation, ObservedJoker
from .policy import DemoPolicy, RuleBasedValidator
from .runtime import EpisodeRunner


class ScriptedObserver:
    """Returns a fixed sequence of mock states for local development."""

    def __init__(self, observations: Iterable[GameObservation]) -> None:
        self._observations = iter(observations)

    def observe(self) -> GameObservation:
        return next(self._observations)


class LoggingExecutor:
    """Stands in for real keyboard and mouse automation."""

    def execute(self, action: GameAction) -> None:
        print(f"EXECUTE  kind={action.kind} target={action.target} reason={action.reason}")


def create_demo_runner() -> EpisodeRunner:
    observations = [
        GameObservation(
            source="mock",
            state_id=1,
            interaction_phase="blind_select",
            blind_key="bl_small",
            money=4,
            hands_left=4,
            discards_left=3,
            score_current=0,
            score_target=300,
            notes=("Small blind available.",),
        ),
        GameObservation(
            source="mock",
            state_id=2,
            interaction_phase="play_hand",
            blind_key="bl_small",
            money=4,
            hands_left=4,
            discards_left=3,
            score_current=90,
            score_target=300,
            jokers=(ObservedJoker(key="j_greedy_joker"),),
        ),
        GameObservation(
            source="mock",
            state_id=3,
            interaction_phase="shop",
            money=6,
            hands_left=0,
            discards_left=0,
            score_current=420,
            score_target=300,
            jokers=(ObservedJoker(key="j_greedy_joker"),),
        ),
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

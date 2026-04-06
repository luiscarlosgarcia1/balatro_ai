from __future__ import annotations

from typing import Iterable

from .models import GameAction, GameObservation, ObservedBlind, ObservedJoker, ObservedScore
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
            state_id=1,
            dollars=4,
            hands_left=4,
            discards_left=3,
            score=ObservedScore(current=0, target=300),
            blinds=(
                ObservedBlind(key="bl_small", state="Select"),
                ObservedBlind(key="bl_big", state="Upcoming"),
                ObservedBlind(key="bl_hook", state="Upcoming"),
            ),
        ),
        GameObservation(
            state_id=2,
            dollars=4,
            hands_left=4,
            discards_left=3,
            score=ObservedScore(current=90, target=300),
            jokers=(
                ObservedJoker(
                    instance_id=101,
                    key="j_greedy_joker",
                    eternal=False,
                    perishable=False,
                    rental=False,
                    perish_tally=None,
                ),
            ),
        ),
        GameObservation(
            state_id=3,
            dollars=6,
            hands_left=0,
            discards_left=0,
            score=ObservedScore(current=420, target=300),
            jokers=(
                ObservedJoker(
                    instance_id=101,
                    key="j_greedy_joker",
                    eternal=False,
                    perishable=False,
                    rental=False,
                    perish_tally=None,
                ),
            ),
            shop_items=(
                ObservedJoker(
                    instance_id=202,
                    key="j_banner",
                    eternal=False,
                    perishable=False,
                    rental=False,
                    perish_tally=None,
                ),
            ),
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

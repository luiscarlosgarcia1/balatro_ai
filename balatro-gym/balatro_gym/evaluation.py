"""Shared seed and terminal-outcome contracts for evaluation and training."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .policies.policy import Policy


MANIFEST_VERSION = "round-tactics-seeds/v1"
DEVELOPMENT_SEEDS = tuple(f"BLTDEV{index:02d}" for index in range(1, 21))
HELD_OUT_SEEDS = tuple(f"BLTEVL{index:02d}" for index in range(1, 81))

@dataclass(frozen=True)
class SeedManifest:
    """The immutable development and held-out seed partition."""

    version: str
    development_seeds: tuple[str, ...]
    held_out_seeds: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "development_seeds", tuple(self.development_seeds))
        object.__setattr__(self, "held_out_seeds", tuple(self.held_out_seeds))
        all_seeds = self.development_seeds + self.held_out_seeds
        if not self.version:
            raise ValueError("seed manifest requires a version")
        if not self.development_seeds or not self.held_out_seeds:
            raise ValueError("seed manifest requires development and held-out seeds")
        if len(all_seeds) != len(set(all_seeds)):
            raise ValueError("seed manifest partitions must not overlap")


@dataclass(frozen=True)
class EpisodeOutcome:
    """One terminal episode result, retained verbatim in evaluation artifacts."""

    seed: str
    terminal_reward: float
    won: bool
    hands_left: int


EpisodeRunner = Callable[["Policy", str], EpisodeOutcome]


DEFAULT_MANIFEST = SeedManifest(
    version=MANIFEST_VERSION,
    development_seeds=DEVELOPMENT_SEEDS,
    held_out_seeds=HELD_OUT_SEEDS,
)

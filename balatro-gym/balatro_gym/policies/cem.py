"""A deterministic development-only diagonal CEM trainer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from random import Random
from statistics import fmean

from balatro_gym.evaluation import (
    DEFAULT_MANIFEST,
    EpisodeOutcome,
    EpisodeRunner,
    SeedManifest,
)

from .linear import FEATURE_LAYOUT, LinearLegalActionPolicy, PolicyRevisionMetadata
from .policy import Policy


@dataclass(frozen=True)
class CEMConfig:
    """The settled reproducible CEM protocol settings."""

    generations: int = 100
    population_size: int = 64
    elite_count: int = 8
    smoothing_previous_weight: float = 0.7
    smoothing_elite_weight: float = 0.3
    initial_mean: float = 0.0
    initial_standard_deviation: float = 1.0
    standard_deviation_floor: float = 0.05
    rng_seed: int = 0

    def __post_init__(self) -> None:
        if self.generations < 1 or self.population_size < 1:
            raise ValueError("CEM generations and population size must be positive")
        if not 1 <= self.elite_count <= self.population_size:
            raise ValueError("CEM elite count must be within the population")
        if self.smoothing_previous_weight < 0 or self.smoothing_elite_weight < 0:
            raise ValueError("CEM smoothing weights must be non-negative")
        if self.smoothing_previous_weight + self.smoothing_elite_weight != 1:
            raise ValueError("CEM smoothing weights must sum to one")
        if self.initial_standard_deviation < 0 or self.standard_deviation_floor < 0:
            raise ValueError("CEM standard deviations must be non-negative")


@dataclass(frozen=True)
class TrainingCheckpoint:
    """The highest development-mean candidate and its exact reward vector."""

    generation: int
    candidate_index: int
    parameters: tuple[float, ...]
    development_mean_reward: float
    development_rewards: tuple[float, ...]
    outcomes: tuple[EpisodeOutcome, ...]


@dataclass(frozen=True)
class CEMTrainingResult:
    """A frozen best policy plus the protocol data that produced it."""

    policy: LinearLegalActionPolicy
    checkpoint: TrainingCheckpoint
    final_means: tuple[float, ...]
    final_standard_deviations: tuple[float, ...]


class CEMTrainer:
    """Optimize a replaceable policy only through the episode-runner seam."""

    def __init__(self) -> None:
        self._config = CEMConfig()
        self._manifest = DEFAULT_MANIFEST

    @classmethod
    def for_test(cls, config: CEMConfig, manifest: SeedManifest) -> CEMTrainer:
        """Create a reduced deterministic trainer solely for contract tests."""
        trainer = cls()
        trainer._config = config
        trainer._manifest = manifest
        return trainer

    def train(self, episode_runner: EpisodeRunner) -> CEMTrainingResult:
        means = (self._config.initial_mean,) * FEATURE_LAYOUT.parameter_count
        deviations = (
            max(self._config.initial_standard_deviation, self._config.standard_deviation_floor),
        ) * FEATURE_LAYOUT.parameter_count
        checkpoint: TrainingCheckpoint | None = None
        for generation in range(self._config.generations):
            candidates = self._sample(generation, means, deviations)
            evaluated = tuple(
                self._evaluate(
                    candidate, self._manifest.development_seeds, episode_runner
                )
                for candidate in candidates
            )
            best_index, best_outcomes = max(
                enumerate(evaluated),
                key=lambda item: (self._mean_reward(item[1]), -item[0]),
            )
            best_mean = self._mean_reward(best_outcomes)
            if checkpoint is None or best_mean > checkpoint.development_mean_reward:
                checkpoint = TrainingCheckpoint(
                    generation=generation,
                    candidate_index=best_index,
                    parameters=candidates[best_index],
                    development_mean_reward=best_mean,
                    development_rewards=tuple(
                        outcome.terminal_reward for outcome in best_outcomes
                    ),
                    outcomes=best_outcomes,
                )
            elite_indices = sorted(
                range(len(candidates)),
                key=lambda index: (-self._mean_reward(evaluated[index]), index),
            )[: self._config.elite_count]
            elites = tuple(candidates[index] for index in elite_indices)
            means, deviations = self._update(means, deviations, elites)
        assert checkpoint is not None
        metadata = PolicyRevisionMetadata(
            training_rng_seed=self._config.rng_seed,
            population_size=self._config.population_size,
            elite_count=self._config.elite_count,
            smoothing_previous_weight=self._config.smoothing_previous_weight,
            smoothing_elite_weight=self._config.smoothing_elite_weight,
            generation_count=self._config.generations,
            initial_mean=self._config.initial_mean,
            initial_standard_deviation=self._config.initial_standard_deviation,
            standard_deviation_floor=self._config.standard_deviation_floor,
            selected_checkpoint_generation=checkpoint.generation,
            selected_checkpoint_candidate_index=checkpoint.candidate_index,
            manifest_version=self._manifest.version,
            development_seeds=self._manifest.development_seeds,
        )
        return CEMTrainingResult(
            policy=LinearLegalActionPolicy(checkpoint.parameters, revision_metadata=metadata),
            checkpoint=checkpoint,
            final_means=means,
            final_standard_deviations=deviations,
        )

    def _sample(
        self, generation: int, means: Sequence[float], deviations: Sequence[float]
    ) -> tuple[tuple[float, ...], ...]:
        rng = Random(f"{self._config.rng_seed}:{generation}")
        return tuple(
            tuple(rng.gauss(mean, deviation) for mean, deviation in zip(means, deviations, strict=True))
            for _ in range(self._config.population_size)
        )

    @staticmethod
    def _evaluate(
        parameters: tuple[float, ...], seeds: Sequence[str], episode_runner: EpisodeRunner
    ) -> tuple[EpisodeOutcome, ...]:
        policy = LinearLegalActionPolicy(parameters)
        outcomes = tuple(episode_runner(policy, seed) for seed in seeds)
        if tuple(outcome.seed for outcome in outcomes) != tuple(seeds):
            raise ValueError("episode runner must return the requested development seeds")
        return outcomes

    def _update(
        self,
        means: Sequence[float],
        deviations: Sequence[float],
        elites: Sequence[Sequence[float]],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        elite_means = tuple(fmean(candidate[index] for candidate in elites) for index in range(FEATURE_LAYOUT.parameter_count))
        elite_deviations = tuple(
            sqrt(fmean((candidate[index] - elite_means[index]) ** 2 for candidate in elites))
            for index in range(FEATURE_LAYOUT.parameter_count)
        )
        updated_means = tuple(
            self._config.smoothing_previous_weight * previous
            + self._config.smoothing_elite_weight * elite
            for previous, elite in zip(means, elite_means, strict=True)
        )
        updated_deviations = tuple(
            max(
                self._config.standard_deviation_floor,
                self._config.smoothing_previous_weight * previous
                + self._config.smoothing_elite_weight * elite,
            )
            for previous, elite in zip(deviations, elite_deviations, strict=True)
        )
        return updated_means, updated_deviations

    @staticmethod
    def _mean_reward(outcomes: Sequence[EpisodeOutcome]) -> float:
        return fmean(outcome.terminal_reward for outcome in outcomes)

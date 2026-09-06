"""Versioned, auditable evaluation independent of a learning algorithm."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from statistics import fmean

from .evaluation import DEFAULT_MANIFEST, EpisodeOutcome, EpisodeRunner, SeedManifest
from .policies.policy import Policy


@dataclass(frozen=True)
class BootstrapInterval:
    """A deterministic percentile bootstrap interval."""

    lower: float
    upper: float


@dataclass(frozen=True)
class Scorecard:
    """Aggregate metrics for a set of per-seed terminal outcomes."""

    win_rate: float
    mean_terminal_reward: float
    terminal_reward_interval: BootstrapInterval
    mean_hands_left_when_won: float | None


@dataclass(frozen=True)
class PairedComparison:
    """Seed-aligned candidate-minus-baseline terminal reward analysis."""

    per_seed_terminal_reward_differences: tuple[float, ...]
    mean_terminal_reward_difference: float
    interval: BootstrapInterval


@dataclass(frozen=True)
class BenchmarkReport:
    """The complete auditable result of one frozen-policy evaluation."""

    manifest_version: str
    policy_revision: str
    baseline_revision: str
    development_outcomes: tuple[EpisodeOutcome, ...]
    baseline_development_outcomes: tuple[EpisodeOutcome, ...]
    held_out_executed: bool
    held_out_outcomes: tuple[EpisodeOutcome, ...]
    baseline_held_out_outcomes: tuple[EpisodeOutcome, ...]
    scorecard: Scorecard | None
    baseline_scorecard: Scorecard | None
    paired_comparison: PairedComparison | None
    improvement_criterion_met: bool


class Benchmark:
    """Evaluate a policy against the fixed baseline without optimizer knowledge."""

    def __init__(self, baseline: Policy, *, bootstrap_samples: int = 10_000) -> None:
        if bootstrap_samples < 1:
            raise ValueError("bootstrap_samples must be positive")
        self._baseline = baseline
        self._bootstrap_samples = bootstrap_samples
        self._held_out_policy_revisions: set[str] = set()

    def evaluate(
        self,
        policy: Policy,
        manifest: SeedManifest,
        episode_runner: EpisodeRunner,
    ) -> BenchmarkReport:
        baseline_development = self._run(
            self._baseline, manifest.development_seeds, episode_runner
        )
        development = self._run(policy, manifest.development_seeds, episode_runner)
        if self._mean_reward(development) <= self._mean_reward(baseline_development):
            return BenchmarkReport(
                manifest_version=manifest.version,
                policy_revision=self._revision(policy),
                baseline_revision=self._revision(self._baseline),
                development_outcomes=development,
                baseline_development_outcomes=baseline_development,
                held_out_executed=False,
                held_out_outcomes=(),
                baseline_held_out_outcomes=(),
                scorecard=None,
                baseline_scorecard=None,
                paired_comparison=None,
                improvement_criterion_met=False,
            )

        policy_revision = self._revision(policy)
        if policy_revision in self._held_out_policy_revisions:
            raise ValueError("held-out evaluation already recorded for this policy revision")
        self._held_out_policy_revisions.add(policy_revision)
        held_out = self._run(policy, manifest.held_out_seeds, episode_runner)
        baseline_held_out = self._run(
            self._baseline, manifest.held_out_seeds, episode_runner
        )
        scorecard = self._scorecard(held_out)
        baseline_scorecard = self._scorecard(baseline_held_out)
        paired = self._paired_comparison(held_out, baseline_held_out)
        improvement = (
            scorecard.win_rate > baseline_scorecard.win_rate
            and paired.interval.lower > 0
        )
        return BenchmarkReport(
            manifest_version=manifest.version,
            policy_revision=policy_revision,
            baseline_revision=self._revision(self._baseline),
            development_outcomes=development,
            baseline_development_outcomes=baseline_development,
            held_out_executed=True,
            held_out_outcomes=held_out,
            baseline_held_out_outcomes=baseline_held_out,
            scorecard=scorecard,
            baseline_scorecard=baseline_scorecard,
            paired_comparison=paired,
            improvement_criterion_met=improvement,
        )

    @staticmethod
    def _run(
        policy: Policy, seeds: Sequence[str], episode_runner: EpisodeRunner
    ) -> tuple[EpisodeOutcome, ...]:
        outcomes = tuple(episode_runner(policy, seed) for seed in seeds)
        if tuple(outcome.seed for outcome in outcomes) != tuple(seeds):
            raise ValueError("episode runner must return an outcome for its requested seed")
        return outcomes

    def _scorecard(self, outcomes: Sequence[EpisodeOutcome]) -> Scorecard:
        rewards = tuple(outcome.terminal_reward for outcome in outcomes)
        wins = tuple(outcome for outcome in outcomes if outcome.won)
        return Scorecard(
            win_rate=sum(outcome.won for outcome in outcomes) / len(outcomes),
            mean_terminal_reward=fmean(rewards),
            terminal_reward_interval=self._bootstrap_interval(rewards),
            mean_hands_left_when_won=(
                fmean(outcome.hands_left for outcome in wins) if wins else None
            ),
        )

    def _paired_comparison(
        self,
        outcomes: Sequence[EpisodeOutcome],
        baseline_outcomes: Sequence[EpisodeOutcome],
    ) -> PairedComparison:
        if tuple(outcome.seed for outcome in outcomes) != tuple(
            outcome.seed for outcome in baseline_outcomes
        ):
            raise ValueError("paired outcomes must have identical seed order")
        differences = tuple(
            outcome.terminal_reward - baseline.terminal_reward
            for outcome, baseline in zip(outcomes, baseline_outcomes, strict=True)
        )
        return PairedComparison(
            per_seed_terminal_reward_differences=differences,
            mean_terminal_reward_difference=fmean(differences),
            interval=self._bootstrap_interval(differences),
        )

    def _bootstrap_interval(self, values: Sequence[float]) -> BootstrapInterval:
        rng = Random(0)
        sample_means = sorted(
            fmean(values[rng.randrange(len(values))] for _ in values)
            for _ in range(self._bootstrap_samples)
        )
        lower_index = int(0.025 * (self._bootstrap_samples - 1))
        upper_index = int(0.975 * (self._bootstrap_samples - 1))
        return BootstrapInterval(sample_means[lower_index], sample_means[upper_index])

    @staticmethod
    def _mean_reward(outcomes: Sequence[EpisodeOutcome]) -> float:
        return fmean(outcome.terminal_reward for outcome in outcomes)

    @staticmethod
    def _revision(policy: Policy) -> str:
        return str(getattr(policy, "revision", type(policy).__name__))

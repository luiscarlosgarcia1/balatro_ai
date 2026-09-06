from __future__ import annotations

from dataclasses import dataclass

from balatro_gym.benchmark import Benchmark, EpisodeOutcome, SeedManifest
from balatro_gym.environments.live import LegalAction, RoundTacticsObservation


@dataclass(frozen=True)
class NamedPolicy:
    revision: str

    def select_action(
        self, observation: RoundTacticsObservation, legal_action_mask: tuple[LegalAction, ...]
    ) -> LegalAction:
        return legal_action_mask[0]


def fixture_manifest() -> SeedManifest:
    return SeedManifest(version="fixture/v1", development_seeds=("dev-1", "dev-2"), held_out_seeds=("test-1", "test-2"))


def test_benchmark_blocks_held_out_execution_until_policy_exceeds_baseline_development_reward() -> None:
    baseline = NamedPolicy("baseline/v1")
    candidate = NamedPolicy("candidate/v1")
    calls: list[tuple[str, str]] = []

    def episode_runner(policy: NamedPolicy, seed: str) -> EpisodeOutcome:
        calls.append((policy.revision, seed))
        reward = 0.5 if policy is baseline else 0.5
        return EpisodeOutcome(seed=seed, terminal_reward=reward, won=True, hands_left=2)

    report = Benchmark(baseline, bootstrap_samples=100).evaluate(
        candidate, fixture_manifest(), episode_runner
    )

    assert not report.held_out_executed
    assert report.held_out_outcomes == ()
    assert all(seed.startswith("dev-") for revision, seed in calls if revision == "candidate/v1")
    assert report.manifest_version == "fixture/v1"
    assert report.policy_revision == "candidate/v1"


def test_benchmark_records_auditable_held_out_scorecard_and_positive_paired_improvement() -> None:
    baseline = NamedPolicy("baseline/v1")
    candidate = NamedPolicy("candidate/v2")

    def episode_runner(policy: NamedPolicy, seed: str) -> EpisodeOutcome:
        baseline_reward = 0.0 if seed.startswith("dev-") else -1.0
        reward = baseline_reward if policy is baseline else 1.25
        return EpisodeOutcome(
            seed=seed,
            terminal_reward=reward,
            won=reward > 0,
            hands_left=2 if reward > 0 else 0,
        )

    report = Benchmark(baseline, bootstrap_samples=100).evaluate(
        candidate, fixture_manifest(), episode_runner
    )

    assert report.held_out_executed
    assert [outcome.seed for outcome in report.held_out_outcomes] == ["test-1", "test-2"]
    assert report.scorecard.win_rate == 1.0
    assert report.scorecard.mean_terminal_reward == 1.25
    assert report.scorecard.mean_hands_left_when_won == 2.0
    assert report.scorecard.terminal_reward_interval.lower == 1.25
    assert report.paired_comparison.mean_terminal_reward_difference == 2.25
    assert report.paired_comparison.interval.lower > 0
    assert report.improvement_criterion_met

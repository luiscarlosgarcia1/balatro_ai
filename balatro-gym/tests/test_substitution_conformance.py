"""Conformance coverage for replacement policies and optimizers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from balatro_gym.benchmark import Benchmark
from balatro_gym.episode_runner import RoundTacticsEpisodeRunner
from balatro_gym.evaluation import EpisodeOutcome, EpisodeRunner, SeedManifest
from balatro_gym.environments.live import (
    LegalAction,
    RoundTacticsEnvironment,
    RoundTacticsObservation,
)
from balatro_gym.policies import Policy

from round_tactics_support import selecting_hand_state


@dataclass(frozen=True)
class FirstAdmittedActionPolicy:
    """A replacement policy that depends only on the published policy contract."""

    revision: str = "conformance-first-admitted-action/v1"

    def select_action(
        self,
        observation: RoundTacticsObservation,
        legal_action_mask: Sequence[LegalAction],
    ) -> LegalAction:
        del observation
        return legal_action_mask[0]


@dataclass(frozen=True)
class LastAdmittedActionPolicy:
    """The baseline fixture intentionally selects the other admitted action."""

    revision: str = "conformance-last-admitted-action/v1"

    def select_action(
        self,
        observation: RoundTacticsObservation,
        legal_action_mask: Sequence[LegalAction],
    ) -> LegalAction:
        del observation
        return legal_action_mask[-1]


class DevelopmentOnlyOptimizer:
    """A minimal substitute optimizer using only the episode-runner seam."""

    def train(
        self, episode_runner: EpisodeRunner, manifest: SeedManifest
    ) -> FirstAdmittedActionPolicy:
        policy = FirstAdmittedActionPolicy()
        for seed in manifest.development_seeds:
            episode_runner(policy, seed)
        return policy


class ActionSensitiveBridge:
    """A controllable live-bridge stand-in whose result follows the submitted action."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def call(
        self, method: str, params: Mapping[str, object] | None = None
    ) -> Mapping[str, Any]:
        self.calls.append((method, params))
        if method == "menu":
            return {"state": "MENU"}
        if method == "start":
            return {"state": "BLIND_SELECT"}
        if method == "select":
            return selecting_hand_state(hand_size=1)
        if method == "play":
            state = selecting_hand_state(hand_size=1, hands_left=3)
            state["state"] = "ROUND_EVAL"
            return state
        if method == "discard":
            state = selecting_hand_state(hand_size=1, hands_left=3)
            state["state"] = "GAME_OVER"
            return state
        raise AssertionError(f"unexpected bridge method: {method}")


def test_substitute_policy_and_optimizer_preserve_environment_and_benchmark_contracts() -> None:
    manifest = SeedManifest(
        version="conformance/v1",
        development_seeds=("dev-1", "dev-2"),
        held_out_seeds=("held-1",),
    )
    observed_calls: list[tuple[str, str]] = []

    def episode_runner(policy: Policy, seed: str) -> EpisodeOutcome:
        observed_calls.append((policy.revision, seed))
        return RoundTacticsEpisodeRunner(
            RoundTacticsEnvironment(ActionSensitiveBridge())
        )(policy, seed)

    candidate = DevelopmentOnlyOptimizer().train(episode_runner, manifest)

    assert observed_calls == [
        ("conformance-first-admitted-action/v1", "dev-1"),
        ("conformance-first-admitted-action/v1", "dev-2"),
    ]

    benchmark = Benchmark(LastAdmittedActionPolicy(), bootstrap_samples=100)
    report = benchmark.evaluate(
        candidate, manifest, episode_runner
    )

    assert report.held_out_executed
    assert tuple(outcome.seed for outcome in report.development_outcomes) == (
        "dev-1",
        "dev-2",
    )
    assert tuple(outcome.seed for outcome in report.held_out_outcomes) == ("held-1",)
    assert report.manifest_version == "conformance/v1"
    assert report.policy_revision == "conformance-first-admitted-action/v1"
    assert report.baseline_revision == "conformance-last-admitted-action/v1"
    assert report.improvement_criterion_met

    with pytest.raises(ValueError, match="held-out evaluation already recorded"):
        benchmark.evaluate(candidate, manifest, episode_runner)

    gate_start = len(observed_calls)
    gated_report = Benchmark(FirstAdmittedActionPolicy(), bootstrap_samples=100).evaluate(
        LastAdmittedActionPolicy(), manifest, episode_runner
    )

    assert not gated_report.held_out_executed
    assert all(seed.startswith("dev-") for _, seed in observed_calls[gate_start:])

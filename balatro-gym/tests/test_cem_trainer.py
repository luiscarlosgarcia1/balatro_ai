from __future__ import annotations

from balatro_gym.benchmark import EpisodeOutcome, SeedManifest
from balatro_gym.policies import CEMConfig, CEMTrainer, FEATURE_LAYOUT


def test_cem_training_is_replayable_development_only_and_preserves_best_checkpoint() -> None:
    manifest = SeedManifest(
        version="fixture/v1",
        development_seeds=("dev-1", "dev-2"),
        held_out_seeds=("held-1",),
    )
    config = CEMConfig(generations=3, population_size=4, elite_count=2, rng_seed=9)
    evaluated_seeds: list[str] = []

    def episode_runner(policy: object, seed: str) -> EpisodeOutcome:
        evaluated_seeds.append(seed)
        parameters = getattr(policy, "parameters")
        reward = parameters[0] + (0.25 if seed == "dev-2" else 0.0)
        return EpisodeOutcome(seed, reward, reward > 0, 1)

    first = CEMTrainer.for_test(config, manifest).train(episode_runner)
    second = CEMTrainer.for_test(config, manifest).train(episode_runner)

    assert first.checkpoint == second.checkpoint
    assert first.policy.parameters == second.policy.parameters
    assert first.checkpoint.development_rewards == tuple(
        outcome.terminal_reward for outcome in first.checkpoint.outcomes
    )
    assert set(evaluated_seeds) == {"dev-1", "dev-2"}
    assert first.policy.revision_metadata.feature_layout_revision == FEATURE_LAYOUT.revision
    assert first.policy.revision_metadata.population_size == 4
    assert first.policy.revision_metadata.elite_count == 2
    assert first.policy.revision_metadata.manifest_version == "fixture/v1"
    assert first.policy.revision_metadata.development_seeds == ("dev-1", "dev-2")
    assert (
        first.policy.revision_metadata.selected_checkpoint_generation
        == first.checkpoint.generation
    )


def test_cem_applies_the_configured_variance_floor() -> None:
    manifest = SeedManifest(
        version="fixture/v1", development_seeds=("dev",), held_out_seeds=("held",)
    )
    config = CEMConfig(
        generations=1,
        population_size=2,
        elite_count=1,
        initial_standard_deviation=0.0,
        standard_deviation_floor=0.05,
    )

    result = CEMTrainer.for_test(config, manifest).train(
        lambda _policy, seed: EpisodeOutcome(seed, 0.0, False, 0),
    )

    assert result.final_standard_deviations == (0.05,) * FEATURE_LAYOUT.parameter_count


def test_benchmark_and_policy_packages_have_no_circular_import() -> None:
    import balatro_gym.benchmark
    import balatro_gym.policies

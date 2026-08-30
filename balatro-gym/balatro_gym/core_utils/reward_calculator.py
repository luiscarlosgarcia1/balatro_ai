"""Stable import boundary for provisional RL reward shaping."""

from balatro_gym.core_utils.provisional_reward_shaping import (
    ProvisionalRewardCalculator,
)


class RewardCalculator(ProvisionalRewardCalculator):
    """Public reward-calculation boundary for environment reward shaping."""


__all__ = ["RewardCalculator", "ProvisionalRewardCalculator"]

"""Legacy compatibility shim for provisional RL reward shaping."""

from balatro_gym.core_utils.provisional_reward_shaping import (
    ProvisionalRewardCalculator as RewardCalculator,
)

__all__ = ["RewardCalculator"]

"""Compatibility shim for legacy imports.

Canonical round progression lives in ``balatro_gym.core_utils.round_manager``.
The ``select_boss_blind`` re-export remains patchable for older tests that
targeted this subordinate module.
"""

from balatro_gym.core_utils.round_manager import RoundManager, RoundOutcome, select_boss_blind

__all__ = ["RoundManager", "RoundOutcome", "select_boss_blind"]

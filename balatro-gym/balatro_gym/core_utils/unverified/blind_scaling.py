"""Compatibility shim for legacy imports.

Canonical blind scaling lives in ``balatro_gym.core_utils.blind_scaling``.
"""

from balatro_gym.core_utils.blind_scaling import BLIND_CHIPS, get_blind_amount, get_blind_chips

__all__ = ["BLIND_CHIPS", "get_blind_amount", "get_blind_chips"]

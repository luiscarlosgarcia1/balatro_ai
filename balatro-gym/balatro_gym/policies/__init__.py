"""Replaceable policies for the Round Tactics boundary."""

from .baseline import DeterministicLegalHeuristic
from .policy import Policy

__all__ = ["DeterministicLegalHeuristic", "Policy"]

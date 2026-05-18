"""Lazy environment exports.

Avoid importing every environment variant at package import time, since some
legacy modules are incomplete and should not block the active env path.
"""

from importlib import import_module

__all__ = [
    "BalatroGameEnv",
    "LegacyBalatroEnv",
    "BalatroEnv",
    "BalatroEnvComplete",
    "BalatroSmallEnv",
    "EightCardDrawEnv",
]


def __getattr__(name: str):
    mapping = {
        "BalatroGameEnv": ("balatro_gym.environments.balatro_env", "BalatroEnv"),
        "LegacyBalatroEnv": ("balatro_gym.environments.balatro_env_2", "BalatroEnv"),
        "BalatroEnv": ("balatro_gym.environments.balatro_env_small", "BalatroEnv"),
        "BalatroEnvComplete": ("balatro_gym.environments.balatro_env_v2", "BalatroEnv"),
        "BalatroSmallEnv": ("balatro_gym.environments.balatro_small_env", "BalatroSmallEnv"),
        "EightCardDrawEnv": ("balatro_gym.environments.env", "EightCardDrawEnv"),
    }
    if name not in mapping:
        raise AttributeError(name)
    module_name, attr_name = mapping[name]
    module = import_module(module_name)
    return getattr(module, attr_name)

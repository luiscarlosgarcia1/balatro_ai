from .environments import BalatroEnv

__all__ = ["BalatroEnv"]


def make(id: str = "BalatroGym-v0", **kwargs):
    if id == "BalatroGym-v0":
        return BalatroEnv(**kwargs)
    raise ValueError(f"Unknown id {id}")

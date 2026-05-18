def make(id: str):
    if id == "EightCardDraw-v0":
        from .environments.env import EightCardDrawEnv
        return EightCardDrawEnv()
    raise ValueError(f"Unknown id {id}")

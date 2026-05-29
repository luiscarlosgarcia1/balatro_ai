from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
BALATRO_GYM_ROOT = REPO_ROOT / "balatro-gym"
BALATROBOT_SRC = REPO_ROOT / "balatrobot" / "src"

for path in (BALATRO_GYM_ROOT, BALATROBOT_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from balatrobot.manager import BalatroInstance
from balatro_gym.core.constants import Action, Phase
from balatro_gym.environments.live.balatro_live_env import BalatroLiveEnv


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _run_live_smoke() -> dict[str, int | float | bool | str]:
    port = _find_free_port()
    temp_root = REPO_ROOT / "balatro-gym" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=temp_root, prefix="live-smoke-") as logs_dir:
        async with BalatroInstance(
            port=port,
            fast=True,
            headless=True,
            no_shaders=True,
            fps_cap=5,
            gamespeed=16,
            animation_fps=1,
            logs_path=logs_dir,
        ) as instance:
            env = BalatroLiveEnv(port=instance.port, timeout=60.0, max_episode_steps=32)

            obs, info = env.reset()
            _assert(info.get("state") == "BLIND_SELECT", f"unexpected reset state: {info}")
            _assert(int(obs["phase"]) == int(Phase.BLIND_SELECT), "reset phase did not match BLIND_SELECT")

            blind_action = next(
                (
                    Action.SELECT_BLIND_BASE + slot
                    for slot in range(3)
                    if obs["action_mask"][Action.SELECT_BLIND_BASE + slot]
                ),
                None,
            )
            _assert(blind_action is not None, "no live blind selection action available")

            obs, reward, terminated, truncated, info = env.step(blind_action)
            _assert(not terminated, f"terminated after blind selection: {info}")
            _assert(not truncated, f"truncated after blind selection: {info}")
            _assert(info.get("action") == "select_blind", f"unexpected blind info: {info}")
            _assert(int(obs["phase"]) == int(Phase.PLAY), f"unexpected post-select phase: {obs['phase']}")

            hand_size = int(obs["hand_size"])
            _assert(hand_size > 0, "live hand was empty after blind selection")

            cards_to_select = min(5, hand_size)
            for card_index in range(cards_to_select):
                obs, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE + card_index)
                _assert(not terminated, f"terminated while selecting cards: {info}")
                _assert(not truncated, f"truncated while selecting cards: {info}")

            _assert(bool(obs["action_mask"][Action.PLAY_HAND]), "play action was not legal after selecting cards")
            obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)
            _assert(not truncated, f"truncated after playing hand: {info}")
            _assert("score_delta" in info, f"play call did not return score info: {info}")

            return {
                "port": instance.port,
                "reset_state": "BLIND_SELECT",
                "post_play_phase": int(obs["phase"]),
                "reward": float(reward),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "score_delta": int(info["score_delta"]),
                "progress": float(info["progress"]),
            }


def main() -> None:
    result = asyncio.run(_run_live_smoke())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

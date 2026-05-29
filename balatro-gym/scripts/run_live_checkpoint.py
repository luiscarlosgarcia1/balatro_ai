from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch
from sb3_contrib import RecurrentPPO
from stable_baselines3.common.utils import obs_as_tensor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize


REPO_ROOT = Path(__file__).resolve().parents[2]
BALATRO_GYM_ROOT = REPO_ROOT / "balatro-gym"
BALATROBOT_SRC = REPO_ROOT / "balatrobot" / "src"

for path in (BALATRO_GYM_ROOT, BALATROBOT_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from balatrobot.manager import BalatroInstance
from balatro_gym.environments.live.balatro_live_env import BalatroLiveEnv
from balatro_gym.training.train_balatro_agent import BalatroFeaturesExtractor


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_model_path(model_path: str) -> Path:
    path = Path(model_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {path}")
    return path


def _resolve_vec_normalize_path(model_path: Path, vec_normalize_path: str | None) -> Path | None:
    if vec_normalize_path:
        candidate = Path(vec_normalize_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"VecNormalize stats not found: {candidate}")
        return candidate

    candidate = model_path.with_name("vec_normalize.pkl")
    return candidate if candidate.exists() else None


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _make_initial_lstm_state(model: RecurrentPPO, batch_size: int = 1) -> tuple[torch.Tensor, torch.Tensor]:
    shape = model.policy.lstm_hidden_state_shape
    return (
        torch.zeros((shape[0], batch_size, shape[2]), dtype=torch.float32, device=model.device),
        torch.zeros((shape[0], batch_size, shape[2]), dtype=torch.float32, device=model.device),
    )


def _legal_policy_action(
    model: RecurrentPPO,
    obs: dict[str, np.ndarray],
    lstm_state: tuple[torch.Tensor, torch.Tensor],
    episode_start: np.ndarray,
    deterministic: bool,
) -> tuple[int, tuple[torch.Tensor, torch.Tensor], bool]:
    obs_tensor = obs_as_tensor(obs, model.device)
    episode_starts = torch.as_tensor(episode_start, dtype=torch.float32, device=model.device)

    with torch.no_grad():
        distribution, next_lstm_state = model.policy.get_distribution(obs_tensor, lstm_state, episode_starts)

    action_mask = np.asarray(obs["action_mask"], dtype=bool)
    if action_mask.ndim == 1:
        action_mask = action_mask.reshape(1, -1)

    logits = distribution.distribution.logits
    legal_mask = torch.as_tensor(action_mask, dtype=torch.bool, device=model.device)
    if not bool(legal_mask.any()):
        raise RuntimeError("Live env returned no legal actions")

    raw_action = int(distribution.get_actions(deterministic=deterministic).cpu().numpy().reshape(-1)[0])
    raw_action_legal = bool(action_mask.reshape(-1)[raw_action])

    masked_logits = logits.masked_fill(~legal_mask, torch.finfo(logits.dtype).min)
    if deterministic:
        action_tensor = masked_logits.argmax(dim=1)
    else:
        action_tensor = torch.distributions.Categorical(logits=masked_logits).sample()

    action = int(action_tensor.cpu().numpy().reshape(-1)[0])
    return action, next_lstm_state, raw_action_legal


async def _run_live_episode(args: argparse.Namespace) -> dict[str, object]:
    model_path = _resolve_model_path(args.model_path)
    vec_normalize_path = _resolve_vec_normalize_path(model_path, args.vec_normalize_path)
    port = args.port or _find_free_port()

    temp_root = REPO_ROOT / "balatro-gym" / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=temp_root, prefix="live-checkpoint-") as logs_dir:
        async with BalatroInstance(
            port=port,
            fast=True,
            headless=not args.show_window,
            no_shaders=True,
            fps_cap=args.fps_cap,
            gamespeed=args.gamespeed,
            animation_fps=args.animation_fps,
            logs_path=logs_dir,
        ) as instance:
            base_env = DummyVecEnv(
                [lambda: BalatroLiveEnv(port=instance.port, timeout=args.timeout, max_episode_steps=args.steps)]
            )
            vec_env = base_env
            if vec_normalize_path is not None:
                vec_env = VecNormalize.load(str(vec_normalize_path), vec_env)
                vec_env.training = False
                vec_env.norm_reward = False

            model = RecurrentPPO.load(str(model_path), env=vec_env)

            obs = vec_env.reset()
            lstm_state = _make_initial_lstm_state(model)
            episode_start = np.array([True], dtype=bool)
            raw_illegal_predictions = 0
            steps_run = 0
            final_reward = 0.0
            last_info: dict[str, object] = {}
            terminated = False
            truncated = False

            for step in range(args.steps):
                action, lstm_state, raw_action_legal = _legal_policy_action(
                    model=model,
                    obs=obs,
                    lstm_state=lstm_state,
                    episode_start=episode_start,
                    deterministic=args.deterministic,
                )
                if not raw_action_legal:
                    raw_illegal_predictions += 1

                obs, rewards, dones, infos = vec_env.step(np.array([action], dtype=np.int64))
                info = infos[0]
                done = bool(dones[0])
                steps_run = step + 1
                final_reward = float(rewards[0])
                last_info = info
                terminated = done and not bool(info.get("TimeLimit.truncated", False))
                truncated = bool(info.get("TimeLimit.truncated", False))
                episode_start = np.array([done], dtype=bool)

                print(
                    json.dumps(
                        {
                            "step": steps_run,
                            "action": action,
                            "reward": final_reward,
                            "done": done,
                            "phase": int(np.asarray(obs["phase"]).reshape(-1)[0]),
                            "raw_action_legal": raw_action_legal,
                            "info_keys": sorted(info.keys()),
                        },
                        sort_keys=True,
                    )
                )

                if done:
                    break

            vec_env.close()

    return {
        "model_path": str(model_path),
        "vec_normalize_path": str(vec_normalize_path) if vec_normalize_path is not None else None,
        "steps_run": steps_run,
        "terminated": terminated,
        "truncated": truncated,
        "final_reward": final_reward,
        "raw_illegal_predictions": raw_illegal_predictions,
        "last_info": _json_safe(last_info),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a trained recurrent PPO checkpoint on BalatroLiveEnv.")
    parser.add_argument("--model-path", required=True, help="Path to a RecurrentPPO .zip checkpoint")
    parser.add_argument(
        "--vec-normalize-path",
        default=None,
        help="Optional path to vec_normalize.pkl. Defaults to sibling of --model-path when present.",
    )
    parser.add_argument("--steps", type=int, default=32, help="Maximum live steps to run")
    parser.add_argument("--port", type=int, default=None, help="Optional explicit balatrobot port")
    parser.add_argument("--timeout", type=float, default=60.0, help="BalatroLiveEnv timeout in seconds")
    parser.add_argument("--fps-cap", type=int, default=5, help="Balatro render FPS cap")
    parser.add_argument("--gamespeed", type=int, default=16, help="Balatro gamespeed multiplier")
    parser.add_argument("--animation-fps", type=int, default=1, help="Balatro animation FPS")
    parser.add_argument("--deterministic", action="store_true", help="Use deterministic policy actions")
    parser.add_argument("--show-window", action="store_true", help="Run with a visible Balatro window")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(_run_live_episode(args))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sb3_contrib import RecurrentPPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize


REPO_ROOT = Path(__file__).resolve().parents[2]
BALATRO_GYM_ROOT = REPO_ROOT / "balatro-gym"
if str(BALATRO_GYM_ROOT) not in sys.path:
    sys.path.insert(0, str(BALATRO_GYM_ROOT))

from balatro_gym.environments.balatro_env_small import BalatroEnv


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


def _run_eval(args: argparse.Namespace) -> dict[str, object]:
    model_path = _resolve_model_path(args.model_path)
    vec_normalize_path = _resolve_vec_normalize_path(model_path, args.vec_normalize_path)

    base_env = DummyVecEnv([lambda: BalatroEnv(seed=args.seed)])
    vec_env = base_env
    if vec_normalize_path is not None:
        vec_env = VecNormalize.load(str(vec_normalize_path), vec_env)
        vec_env.training = False
        vec_env.norm_reward = False

    model = RecurrentPPO.load(str(model_path), env=vec_env)

    episode_summaries: list[dict[str, object]] = []
    total_raw_illegal_predictions = 0

    for episode_idx in range(args.episodes):
        obs = vec_env.reset()
        lstm_state = None
        episode_start = np.array([True], dtype=bool)
        last_info: dict[str, object] = {}
        beat_blind = False
        max_progress = 0.0
        steps_run = 0
        final_reward = 0.0
        terminated = False
        truncated = False
        raw_illegal_predictions = 0

        for step in range(args.steps):
            action, lstm_state = model.predict(
                obs,
                state=lstm_state,
                episode_start=episode_start,
                deterministic=args.deterministic,
            )
            action = int(np.asarray(action).reshape(-1)[0])

            action_mask = np.asarray(obs["action_mask"], dtype=bool).reshape(-1)
            if not bool(action_mask[action]):
                raw_illegal_predictions += 1

            obs, rewards, dones, infos = vec_env.step(np.array([action], dtype=np.int64))
            info = infos[0]
            done = bool(dones[0])
            steps_run = step + 1
            final_reward = float(rewards[0])
            last_info = info
            beat_blind = beat_blind or bool(info.get("beat_blind", False))
            if "progress" in info:
                max_progress = max(max_progress, float(info["progress"]))
            terminated = done and not bool(info.get("TimeLimit.truncated", False))
            truncated = bool(info.get("TimeLimit.truncated", False))
            episode_start = np.array([done], dtype=bool)

            if done:
                break

        total_raw_illegal_predictions += raw_illegal_predictions
        episode_summaries.append(
            {
                "episode": episode_idx + 1,
                "steps_run": steps_run,
                "terminated": terminated,
                "truncated": truncated,
                "final_reward": final_reward,
                "raw_illegal_predictions": raw_illegal_predictions,
                "beat_blind": beat_blind,
                "failed": bool(last_info.get("failed", False)),
                "final_score": int(last_info.get("final_score", 0)),
                "max_progress": max_progress,
                "progress": float(last_info.get("progress", 0.0))
                if "progress" in last_info
                else None,
                "last_info_keys": sorted(last_info.keys()),
            }
        )

    vec_env.close()

    beat_blind_count = sum(1 for ep in episode_summaries if ep["beat_blind"])
    avg_steps = float(np.mean([ep["steps_run"] for ep in episode_summaries])) if episode_summaries else 0.0
    avg_final_reward = float(np.mean([ep["final_reward"] for ep in episode_summaries])) if episode_summaries else 0.0
    progress_values = [ep["progress"] for ep in episode_summaries if ep["progress"] is not None]
    avg_progress = float(np.mean(progress_values)) if progress_values else 0.0
    max_progress_values = [float(ep["max_progress"]) for ep in episode_summaries]
    avg_max_progress = float(np.mean(max_progress_values)) if max_progress_values else 0.0

    return {
        "model_path": str(model_path),
        "vec_normalize_path": str(vec_normalize_path) if vec_normalize_path is not None else None,
        "episodes": args.episodes,
        "steps_per_episode": args.steps,
        "beat_blind_count": beat_blind_count,
        "beat_blind_rate": beat_blind_count / max(1, args.episodes),
        "avg_steps": avg_steps,
        "avg_final_reward": avg_final_reward,
        "avg_progress": avg_progress,
        "avg_max_progress": avg_max_progress,
        "raw_illegal_predictions": total_raw_illegal_predictions,
        "episode_summaries": _json_safe(episode_summaries),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a recurrent PPO checkpoint on the Balatro simulation env.")
    parser.add_argument("--model-path", required=True, help="Path to a RecurrentPPO .zip checkpoint")
    parser.add_argument(
        "--vec-normalize-path",
        default=None,
        help="Optional path to vec_normalize.pkl. Defaults to sibling of --model-path when present.",
    )
    parser.add_argument("--episodes", type=int, default=10, help="Number of episodes to evaluate")
    parser.add_argument("--steps", type=int, default=256, help="Maximum steps per episode")
    parser.add_argument("--seed", type=int, default=123, help="Environment seed")
    parser.add_argument("--deterministic", action="store_true", help="Use deterministic policy actions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = _run_eval(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

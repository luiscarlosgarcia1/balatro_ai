from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BALATRO_GYM_ROOT = REPO_ROOT / "balatro-gym"
if str(BALATRO_GYM_ROOT) not in sys.path:
    sys.path.insert(0, str(BALATRO_GYM_ROOT))

from balatro_gym.core.constants import Action, Phase
from balatro_gym.environments.balatro_env_small import BalatroEnv
from balatro_gym.training.greedy_expert import best_play_sequence, default_phase_action


def run_eval(episodes: int, steps: int, seed: int) -> dict[str, object]:
    episode_summaries: list[dict[str, object]] = []

    for episode_idx in range(episodes):
        env = BalatroEnv(seed=seed + episode_idx)
        obs, _ = env.reset(seed=seed + episode_idx)
        terminated = False
        truncated = False
        last_info: dict[str, object] = {}
        steps_run = 0
        beat_blind = False

        while steps_run < steps and not (terminated or truncated):
            phase = int(obs["phase"])
            if phase == Phase.PLAY:
                action_sequence = best_play_sequence(env)
                for action in action_sequence:
                    obs, reward, terminated, truncated, info = env.step(action)
                    last_info = info
                    steps_run += 1
                    beat_blind = beat_blind or bool(info.get("beat_blind", False))
                    if terminated or truncated or int(obs["phase"]) != Phase.PLAY or steps_run >= steps:
                        break
            else:
                action = default_phase_action(obs)
                obs, reward, terminated, truncated, info = env.step(action)
                last_info = info
                steps_run += 1
                beat_blind = beat_blind or bool(info.get("beat_blind", False))

        episode_summaries.append(
            {
                "episode": episode_idx + 1,
                "steps_run": steps_run,
                "beat_blind": beat_blind,
                "terminated": terminated,
                "truncated": truncated,
                "final_score": int(last_info.get("final_score", 0)),
                "round_chips_scored": int(env.state.round_chips_scored),
                "chips_needed": int(env.state.chips_needed),
            }
        )

    beat_blind_count = sum(1 for episode in episode_summaries if episode["beat_blind"])
    avg_steps = sum(int(ep["steps_run"]) for ep in episode_summaries) / max(1, len(episode_summaries))

    return {
        "episodes": episodes,
        "steps_per_episode": steps,
        "seed": seed,
        "beat_blind_count": beat_blind_count,
        "beat_blind_rate": beat_blind_count / max(1, episodes),
        "avg_steps": avg_steps,
        "episode_summaries": episode_summaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a greedy best-immediate-hand policy on the Balatro sim.")
    parser.add_argument("--episodes", type=int, default=20, help="Number of episodes to evaluate")
    parser.add_argument("--steps", type=int, default=128, help="Maximum steps per episode")
    parser.add_argument("--seed", type=int, default=123, help="Base environment seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(run_eval(args.episodes, args.steps, args.seed), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

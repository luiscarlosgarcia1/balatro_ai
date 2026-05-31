"""Train RecurrentPPO agents on the Balatro simulation environment."""

from __future__ import annotations

import json
import importlib.util
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import torch
import torch.nn as nn
from gymnasium import spaces
from sb3_contrib import RecurrentPPO
from sb3_contrib.common.maskable.distributions import MaskableCategoricalDistribution
from sb3_contrib.common.recurrent.policies import RecurrentMultiInputActorCriticPolicy
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.distributions import CategoricalDistribution
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from balatro_gym.environments.balatro_env_small import BalatroEnv


class BalatroFeaturesExtractor(BaseFeaturesExtractor):
    """Feature extractor for Balatro's dict observation space.

    The maintained MVP path uses RecurrentPPO with ``MultiInputLstmPolicy``.
    This extractor keeps the hand representation structured via card one-hot
    encoding while flattening the remaining scalar/vector game state features,
    including the current legal-action mask. RecurrentPPO does not natively
    enforce the mask, but exposing it during training lets the policy learn
    to suppress illegal logits instead of only being corrected at runtime.
    """

    def __init__(self, observation_space: spaces.Dict, features_dim: int = 512):
        super().__init__(observation_space, features_dim)

        self.hand_key = "hand"
        self.flat_keys = [
            key for key in observation_space.spaces.keys()
            if key != self.hand_key
        ]

        hand_space = observation_space[self.hand_key]
        self.hand_slots = int(np.prod(hand_space.shape))
        self.card_vocab_size = int(np.max(hand_space.high)) + 1

        flat_dim = sum(self._flat_dim(observation_space[key]) for key in self.flat_keys)

        self.hand_net = nn.Sequential(
            nn.Linear(self.hand_slots * self.card_vocab_size, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
        )
        self.flat_net = nn.Sequential(
            nn.Linear(flat_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
        )
        self.combined_net = nn.Sequential(
            nn.Linear(256, features_dim),
            nn.ReLU(),
            nn.Linear(features_dim, features_dim),
            nn.ReLU(),
        )

    @staticmethod
    def _flat_dim(space: spaces.Space) -> int:
        return int(np.prod(space.shape)) if space.shape else 1

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        hand = observations[self.hand_key].long()
        batch_size = hand.shape[0]

        hand_one_hot = torch.zeros(
            batch_size,
            self.hand_slots,
            self.card_vocab_size,
            device=hand.device,
        )
        for i in range(self.hand_slots):
            valid_cards = hand[:, i] >= 0
            if valid_cards.any():
                hand_one_hot[valid_cards, i, hand[valid_cards, i]] = 1.0

        hand_features = self.hand_net(hand_one_hot.reshape(batch_size, -1))
        flat_features = torch.cat(
            [observations[key].float().reshape(batch_size, -1) for key in self.flat_keys],
            dim=1,
        )
        state_features = self.flat_net(flat_features)

        return self.combined_net(torch.cat([hand_features, state_features], dim=1))


class MaskedMultiInputLstmPolicy(RecurrentMultiInputActorCriticPolicy):
    """Recurrent multi-input policy that enforces ``action_mask`` during PPO."""

    def _extract_action_mask(self, obs: dict[str, torch.Tensor]) -> torch.Tensor | None:
        if not isinstance(self.action_space, spaces.Discrete) or "action_mask" not in obs:
            return None

        action_mask = obs["action_mask"]
        if action_mask is None:
            return None

        legal_mask = action_mask.to(device=self.device, dtype=torch.bool).reshape(-1, self.action_space.n)
        empty_rows = ~legal_mask.any(dim=1)
        if empty_rows.any():
            # Recurrent PPO pads minibatches with zero observations; those rows are
            # ignored by the loss mask and should not force an invalid categorical.
            legal_mask = legal_mask.clone()
            legal_mask[empty_rows] = True
        return legal_mask

    def _mask_distribution(
        self,
        distribution: CategoricalDistribution,
        action_mask: torch.Tensor | None,
    ) -> CategoricalDistribution:
        if action_mask is None or not isinstance(distribution, CategoricalDistribution):
            return distribution

        masked_distribution = MaskableCategoricalDistribution(self.action_space.n)
        masked_distribution.proba_distribution(distribution.distribution.logits.reshape(-1, self.action_space.n))
        masked_distribution.apply_masking(action_mask)
        return masked_distribution

    def forward(
        self,
        obs: dict[str, torch.Tensor],
        lstm_states,
        episode_starts: torch.Tensor,
        deterministic: bool = False,
    ):
        features = self.extract_features(obs)
        if self.share_features_extractor:
            pi_features = vf_features = features
        else:
            pi_features, vf_features = features

        latent_pi, lstm_states_pi = self._process_sequence(pi_features, lstm_states.pi, episode_starts, self.lstm_actor)
        if self.lstm_critic is not None:
            latent_vf, lstm_states_vf = self._process_sequence(vf_features, lstm_states.vf, episode_starts, self.lstm_critic)
        elif self.shared_lstm:
            latent_vf = latent_pi.detach()
            lstm_states_vf = (lstm_states_pi[0].detach(), lstm_states_pi[1].detach())
        else:
            latent_vf = self.critic(vf_features)
            lstm_states_vf = lstm_states_pi

        latent_pi = self.mlp_extractor.forward_actor(latent_pi)
        latent_vf = self.mlp_extractor.forward_critic(latent_vf)

        values = self.value_net(latent_vf)
        distribution = self._mask_distribution(
            self._get_action_dist_from_latent(latent_pi),
            self._extract_action_mask(obs),
        )
        actions = distribution.get_actions(deterministic=deterministic)
        log_prob = distribution.log_prob(actions)
        actions = actions.reshape((-1, *self.action_space.shape))
        return actions, values, log_prob, type(lstm_states)(lstm_states_pi, lstm_states_vf)

    def evaluate_actions(self, obs: dict[str, torch.Tensor], actions: torch.Tensor, lstm_states, episode_starts: torch.Tensor):
        features = self.extract_features(obs)
        if self.share_features_extractor:
            pi_features = vf_features = features
        else:
            pi_features, vf_features = features

        latent_pi, _ = self._process_sequence(pi_features, lstm_states.pi, episode_starts, self.lstm_actor)
        if self.lstm_critic is not None:
            latent_vf, _ = self._process_sequence(vf_features, lstm_states.vf, episode_starts, self.lstm_critic)
        elif self.shared_lstm:
            latent_vf = latent_pi.detach()
        else:
            latent_vf = self.critic(vf_features)

        latent_pi = self.mlp_extractor.forward_actor(latent_pi)
        latent_vf = self.mlp_extractor.forward_critic(latent_vf)

        distribution = self._mask_distribution(
            self._get_action_dist_from_latent(latent_pi),
            self._extract_action_mask(obs),
        )
        log_prob = distribution.log_prob(actions)
        values = self.value_net(latent_vf)
        return values, log_prob, distribution.entropy()

    def get_distribution(self, obs: dict[str, torch.Tensor], lstm_states, episode_starts: torch.Tensor):
        distribution, next_lstm_states = super().get_distribution(obs, lstm_states, episode_starts)
        return self._mask_distribution(distribution, self._extract_action_mask(obs)), next_lstm_states


class BalatroMetricsCallback(BaseCallback):
    """Track episode-level metrics during training."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.writer = None

    def _on_training_start(self) -> None:
        log_dir = getattr(self.logger, "dir", None) or getattr(self.model, "tensorboard_log", None)
        if log_dir is not None and hasattr(torch.utils, "tensorboard"):
            self.writer = torch.utils.tensorboard.SummaryWriter(log_dir=log_dir)

    def _on_step(self) -> bool:
        for i, done in enumerate(self.locals["dones"]):
            if not done:
                continue

            info = self.locals["infos"][i]
            ep_info = info.get("episode", {})
            ep_return = ep_info.get("r", 0.0)
            ep_length = ep_info.get("l", 0)
            ante = info.get("ante", 1)
            final_score = info.get("final_score", 0)

            print(
                f"[step {self.num_timesteps:>7d}] "
                f"return={ep_return:>8.2f} len={ep_length:>5d} "
                f"ante={ante} score={final_score}"
            )

            if self.writer is not None:
                self.writer.add_scalar("balatro/episode_return", ep_return, self.num_timesteps)
                self.writer.add_scalar("balatro/episode_length", ep_length, self.num_timesteps)
                self.writer.add_scalar("balatro/episode_ante", ante, self.num_timesteps)
                self.writer.add_scalar("balatro/episode_score", final_score, self.num_timesteps)

        return True

    def _on_training_end(self) -> None:
        if self.writer is not None:
            self.writer.close()


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, type):
        return f"{value.__module__}.{value.__qualname__}"
    if callable(value):
        module = getattr(value, "__module__", None)
        qualname = getattr(value, "__qualname__", getattr(value, "__name__", repr(value)))
        return f"{module}.{qualname}" if module else qualname
    return value


def _merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _short_budget_hyperparams(total_timesteps: int, n_envs: int) -> dict[str, Any]:
    """Use a smaller rollout/update recipe when validating short masked-policy runs."""

    if total_timesteps > 20_000:
        return {}

    per_env_budget = max(total_timesteps // max(n_envs, 1), 1)
    n_steps = max(32, min(256, per_env_budget))
    batch_size = min(256, n_steps * max(n_envs, 1))
    return {
        "n_steps": n_steps,
        "batch_size": batch_size,
        "n_epochs": 4,
        "ent_coef": 0.001,
    }


def _tensorboard_log_dir(save_path: Path) -> str | None:
    """Disable tensorboard logging when the optional dependency is unavailable."""
    return str(save_path / "tb_logs") if importlib.util.find_spec("tensorboard") else None


def train_balatro_agent(
    total_timesteps: int = 1_000_000,
    n_envs: int = 8,
    seed: int = 42,
    save_dir: str = str(REPO_ROOT / "artifacts" / "models"),
    checkpoint_freq: int = 10_000,
    hyperparams: dict[str, Any] | None = None,
):
    """Train a Balatro agent with sb3-contrib RecurrentPPO."""

    save_root = Path(save_dir)
    save_path = save_root / f"recurrent_ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_path.mkdir(parents=True, exist_ok=True)

    n_envs = max(1, int(n_envs))

    def make_env(rank: int):
        def _init():
            return Monitor(BalatroEnv(seed=seed + rank))

        return _init

    if n_envs > 1:
        env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
    else:
        env = DummyVecEnv([make_env(0)])

    env = VecNormalize(env, norm_obs=False, norm_reward=True)

    default_hyperparams = {
        "learning_rate": 3e-4,
        "n_steps": 2048,
        "batch_size": 64,
        "n_epochs": 10,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "clip_range": 0.2,
        "ent_coef": 0.01,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
        "policy_kwargs": {
            "features_extractor_class": BalatroFeaturesExtractor,
            "features_extractor_kwargs": {"features_dim": 512},
            "net_arch": {"pi": [256, 256], "vf": [256, 256]},
        },
    }
    algo_hyperparams = _merge_dicts(
        default_hyperparams,
        _merge_dicts(_short_budget_hyperparams(total_timesteps, n_envs), hyperparams or {}),
    )

    if total_timesteps <= 20_000:
        print(
            "Applying short-budget PPO defaults: "
            f"n_steps={algo_hyperparams['n_steps']}, "
            f"batch_size={algo_hyperparams['batch_size']}, "
            f"n_epochs={algo_hyperparams['n_epochs']}, "
            f"ent_coef={algo_hyperparams['ent_coef']}"
        )

    model = RecurrentPPO(
        MaskedMultiInputLstmPolicy,
        env,
        verbose=1,
        tensorboard_log=_tensorboard_log_dir(save_path),
        **algo_hyperparams,
    )

    callback_save_freq = max(checkpoint_freq // n_envs, 1)
    callbacks = CallbackList(
        [
            CheckpointCallback(
                save_freq=callback_save_freq,
                save_path=str(save_path / "checkpoints"),
                name_prefix="recurrent_ppo_checkpoint",
            ),
            BalatroMetricsCallback(),
        ]
    )

    print("\nStarting RecurrentPPO training...")
    print(f"Total timesteps: {total_timesteps:,}")
    print(f"Number of environments: {n_envs}")
    print(f"Save directory: {save_path}")

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            log_interval=10,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")

    model.save(str(save_path / "recurrent_ppo_final"))
    env.save(str(save_path / "vec_normalize.pkl"))

    config = {
        "algorithm": "sb3_contrib.RecurrentPPO",
        "policy": f"{MaskedMultiInputLstmPolicy.__module__}.{MaskedMultiInputLstmPolicy.__qualname__}",
        "total_timesteps": total_timesteps,
        "n_envs": n_envs,
        "seed": seed,
        "checkpoint_freq": checkpoint_freq,
        "hyperparams": _make_json_safe(algo_hyperparams),
        "save_path": str(save_path),
    }
    with open(save_path / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"\nTraining complete. Model saved to {save_path}")
    return model, save_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train a Balatro agent with RecurrentPPO")
    parser.add_argument("--timesteps", type=int, default=1_000_000, help="Total training timesteps")
    parser.add_argument("--n-envs", type=int, default=8, help="Number of parallel environments")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--save-dir",
        type=str,
        default=str(REPO_ROOT / "artifacts" / "models"),
        help="Directory for checkpoints, logs, and final model artifacts",
    )
    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=10_000,
        help="Approximate checkpoint interval in environment timesteps",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Run a short 10k-timestep smoke test",
    )

    args = parser.parse_args()
    timesteps = 10_000 if args.quick_test else args.timesteps

    _, save_path = train_balatro_agent(
        total_timesteps=timesteps,
        n_envs=args.n_envs,
        seed=args.seed,
        save_dir=args.save_dir,
        checkpoint_freq=args.checkpoint_freq,
    )

    print(f"Artifacts written to: {save_path}")

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


def _load_train_module_with_stubs(monkeypatch: pytest.MonkeyPatch, module_name: str):
    class _FakeModule:
        def __init__(self, *args, **kwargs):
            pass

    class _FakeNNModule(_FakeModule):
        pass

    class _FakeLinear(_FakeModule):
        pass

    class _FakeReLU(_FakeModule):
        pass

    class _FakeSequential(_FakeModule):
        def __init__(self, *layers):
            self.layers = layers

    class _FakeSummaryWriter:
        def __init__(self, log_dir=None):
            self.log_dir = log_dir

        def add_scalar(self, *args, **kwargs):
            pass

        def close(self):
            pass

    torch_module = types.ModuleType("torch")
    torch_nn_module = types.ModuleType("torch.nn")
    torch_nn_module.Module = _FakeNNModule
    torch_nn_module.Linear = _FakeLinear
    torch_nn_module.ReLU = _FakeReLU
    torch_nn_module.Sequential = _FakeSequential
    torch_module.nn = torch_nn_module
    torch_module.Tensor = object
    torch_module.utils = types.SimpleNamespace(
        tensorboard=types.SimpleNamespace(SummaryWriter=_FakeSummaryWriter)
    )

    class _FakeWrapper:
        def __init__(self, env):
            self.env = env

        def __getattr__(self, name):
            return getattr(self.env, name)

    gym_module = types.ModuleType("gymnasium")
    gym_module.Wrapper = _FakeWrapper
    gym_module.Env = object
    gym_module.spaces = types.SimpleNamespace(Dict=dict)

    vec_env_module = types.ModuleType("stable_baselines3.common.vec_env")

    class _FakeDummyVecEnv:
        created = []

        def __init__(self, env_fns):
            self.env_fns = env_fns
            self.envs = [fn() for fn in env_fns]
            type(self).created.append(self)

        def save(self, path):
            Path(path).write_text("vecnorm")

    class _FakeSubprocVecEnv(_FakeDummyVecEnv):
        pass

    class _FakeVecNormalize:
        created = []

        def __init__(self, env, norm_obs=False, norm_reward=True):
            self.env = env
            self.norm_obs = norm_obs
            self.norm_reward = norm_reward
            type(self).created.append(self)

        def save(self, path):
            Path(path).write_text("vecnorm")

    vec_env_module.DummyVecEnv = _FakeDummyVecEnv
    vec_env_module.SubprocVecEnv = _FakeSubprocVecEnv
    vec_env_module.VecNormalize = _FakeVecNormalize

    callbacks_module = types.ModuleType("stable_baselines3.common.callbacks")

    class _FakeBaseCallback:
        def __init__(self, verbose=0):
            self.verbose = verbose

    class _FakeCheckpointCallback:
        def __init__(self, save_freq, save_path, name_prefix):
            self.save_freq = save_freq
            self.save_path = save_path
            self.name_prefix = name_prefix

    class _FakeCallbackList:
        def __init__(self, callbacks):
            self.callbacks = callbacks

    callbacks_module.BaseCallback = _FakeBaseCallback
    callbacks_module.CheckpointCallback = _FakeCheckpointCallback
    callbacks_module.CallbackList = _FakeCallbackList

    monitor_module = types.ModuleType("stable_baselines3.common.monitor")

    class _FakeMonitor:
        def __init__(self, env):
            self.env = env

        def __getattr__(self, name):
            return getattr(self.env, name)

    monitor_module.Monitor = _FakeMonitor

    evaluation_module = types.ModuleType("stable_baselines3.common.evaluation")
    evaluation_module.evaluate_policy = lambda *args, **kwargs: (0.0, 0.0)

    distributions_module = types.ModuleType("stable_baselines3.common.distributions")

    class _FakeCategoricalDistribution:
        def __init__(self, *args, **kwargs):
            pass

    distributions_module.CategoricalDistribution = _FakeCategoricalDistribution

    torch_layers_module = types.ModuleType("stable_baselines3.common.torch_layers")

    class _FakeBaseFeaturesExtractor:
        def __init__(self, observation_space, features_dim):
            self.observation_space = observation_space
            self.features_dim = features_dim

    torch_layers_module.BaseFeaturesExtractor = _FakeBaseFeaturesExtractor

    sb3_contrib_module = types.ModuleType("sb3_contrib")
    sb3_contrib_common_module = types.ModuleType("sb3_contrib.common")
    sb3_contrib_common_maskable_module = types.ModuleType("sb3_contrib.common.maskable")
    sb3_contrib_common_maskable_distributions_module = types.ModuleType("sb3_contrib.common.maskable.distributions")
    sb3_contrib_common_recurrent_module = types.ModuleType("sb3_contrib.common.recurrent")
    sb3_contrib_common_recurrent_policies_module = types.ModuleType("sb3_contrib.common.recurrent.policies")

    class _FakeRecurrentPPO:
        created = []

        def __init__(self, policy, env, verbose=0, tensorboard_log=None, **kwargs):
            self.policy = policy
            self.env = env
            self.verbose = verbose
            self.tensorboard_log = tensorboard_log
            self.kwargs = kwargs
            self.learn_calls = []
            type(self).created.append(self)

        def learn(self, total_timesteps, callback=None, log_interval=None, progress_bar=None):
            self.learn_calls.append(
                {
                    "total_timesteps": total_timesteps,
                    "callback": callback,
                    "log_interval": log_interval,
                    "progress_bar": progress_bar,
                }
            )
            return self

        def save(self, path):
            Path(path).write_text("model")

    sb3_contrib_module.RecurrentPPO = _FakeRecurrentPPO

    class _FakeMaskableCategoricalDistribution:
        def __init__(self, action_dim):
            self.action_dim = action_dim

        def proba_distribution(self, logits):
            self.logits = logits
            return self

        def apply_masking(self, masks):
            self.masks = masks

    class _FakeRecurrentMultiInputActorCriticPolicy:
        def __init__(self, *args, **kwargs):
            pass

    sb3_contrib_common_maskable_distributions_module.MaskableCategoricalDistribution = _FakeMaskableCategoricalDistribution
    sb3_contrib_common_recurrent_policies_module.RecurrentMultiInputActorCriticPolicy = _FakeRecurrentMultiInputActorCriticPolicy
    sb3_contrib_common_maskable_module.distributions = sb3_contrib_common_maskable_distributions_module
    sb3_contrib_common_recurrent_module.policies = sb3_contrib_common_recurrent_policies_module
    sb3_contrib_common_module.maskable = sb3_contrib_common_maskable_module
    sb3_contrib_common_module.recurrent = sb3_contrib_common_recurrent_module
    sb3_contrib_module.common = sb3_contrib_common_module

    balatro_env_module = types.ModuleType("balatro_gym.environments.balatro_env_small")

    class _FakeBalatroEnv:
        def __init__(self, seed=None):
            self.seed = seed
            self.state = types.SimpleNamespace(ante=1)

        def reset(self, **kwargs):
            return {"phase": 0, "action_mask": [1, 0, 0]}, {"seed": self.seed}

        def step(self, action):
            return {"phase": 0, "action_mask": [1, 0, 0]}, 0.0, False, False, {}

    balatro_env_module.BalatroEnv = _FakeBalatroEnv
    balatro_env_module.make_balatro_env = lambda **kwargs: (lambda: _FakeBalatroEnv(**kwargs))

    constants_module = types.ModuleType("balatro_gym.core.constants")

    class _FakeAction:
        PLAY_HAND = 0
        DISCARD = 1
        SHOP_REROLL = 2
        SHOP_END = 3
        SKIP_BLIND = 4
        SKIP_PACK = 5
        SELECT_CARD_BASE = 10
        USE_CONSUMABLE_BASE = 20
        SHOP_BUY_BASE = 30
        SELL_JOKER_BASE = 40
        SELL_CONSUMABLE_BASE = 50
        SELECT_BLIND_BASE = 60
        SELECT_FROM_PACK_BASE = 70

    class _FakeActionCounts:
        SELECT_CARD_COUNT = 8
        USE_CONSUMABLE_COUNT = 5
        SHOP_BUY_COUNT = 10
        SELL_JOKER_COUNT = 5
        SELL_CONSUMABLE_COUNT = 5
        SELECT_BLIND_COUNT = 3
        SELECT_FROM_PACK_COUNT = 5

    constants_module.Action = _FakeAction
    constants_module.ActionCounts = _FakeActionCounts

    stable_baselines3_module = types.ModuleType("stable_baselines3")
    stable_baselines3_common_module = types.ModuleType("stable_baselines3.common")
    stable_baselines3_common_module.vec_env = vec_env_module
    stable_baselines3_common_module.callbacks = callbacks_module
    stable_baselines3_common_module.monitor = monitor_module
    stable_baselines3_common_module.evaluation = evaluation_module
    stable_baselines3_common_module.distributions = distributions_module
    stable_baselines3_common_module.torch_layers = torch_layers_module
    stable_baselines3_module.common = stable_baselines3_common_module

    balatro_gym_module = types.ModuleType("balatro_gym")
    balatro_gym_environments_module = types.ModuleType("balatro_gym.environments")
    balatro_gym_core_module = types.ModuleType("balatro_gym.core")
    balatro_gym_environments_module.balatro_env_small = balatro_env_module
    balatro_gym_core_module.constants = constants_module
    balatro_gym_module.environments = balatro_gym_environments_module
    balatro_gym_module.core = balatro_gym_core_module

    package_modules = {
        "torch": torch_module,
        "torch.nn": torch_nn_module,
        "gymnasium": gym_module,
        "stable_baselines3": stable_baselines3_module,
        "stable_baselines3.common": stable_baselines3_common_module,
        "stable_baselines3.common.vec_env": vec_env_module,
        "stable_baselines3.common.callbacks": callbacks_module,
        "stable_baselines3.common.monitor": monitor_module,
        "stable_baselines3.common.evaluation": evaluation_module,
        "stable_baselines3.common.distributions": distributions_module,
        "stable_baselines3.common.torch_layers": torch_layers_module,
        "sb3_contrib": sb3_contrib_module,
        "sb3_contrib.common": sb3_contrib_common_module,
        "sb3_contrib.common.maskable": sb3_contrib_common_maskable_module,
        "sb3_contrib.common.maskable.distributions": sb3_contrib_common_maskable_distributions_module,
        "sb3_contrib.common.recurrent": sb3_contrib_common_recurrent_module,
        "sb3_contrib.common.recurrent.policies": sb3_contrib_common_recurrent_policies_module,
        "balatro_gym": balatro_gym_module,
        "balatro_gym.environments": balatro_gym_environments_module,
        "balatro_gym.environments.balatro_env_small": balatro_env_module,
        "balatro_gym.core": balatro_gym_core_module,
        "balatro_gym.core.constants": constants_module,
    }

    for name, module in package_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    trainer_path = PACKAGE_ROOT / "balatro_gym" / "training" / "train_balatro_agent.py"
    spec = importlib.util.spec_from_file_location(module_name, trainer_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_train_balatro_agent_imports_and_constructs_with_stubs(monkeypatch, tmp_path):
    module = _load_train_module_with_stubs(monkeypatch, "train_balatro_agent_stubbed")

    model, save_path = module.train_balatro_agent(
        total_timesteps=0,
        n_envs=1,
        checkpoint_freq=1,
        save_dir=str(tmp_path),
    )

    assert model.policy.__name__ == "MaskedMultiInputLstmPolicy"
    assert model.learn_calls[0]["total_timesteps"] == 0
    assert model.learn_calls[0]["callback"].__class__.__name__ == "_FakeCallbackList"
    assert model.learn_calls[0]["log_interval"] == 10
    assert save_path.exists()

    config = json.loads((save_path / "config.json").read_text())
    assert config["algorithm"] == "sb3_contrib.RecurrentPPO"
    assert config["policy"].endswith(".MaskedMultiInputLstmPolicy")
    assert config["n_envs"] == 1
    assert (save_path / "recurrent_ppo_final").exists()
    assert (save_path / "vec_normalize.pkl").exists()


def test_train_balatro_agent_applies_short_budget_defaults(monkeypatch, tmp_path):
    module = _load_train_module_with_stubs(monkeypatch, "train_balatro_agent_short_budget")

    model, _ = module.train_balatro_agent(
        total_timesteps=10_000,
        n_envs=1,
        checkpoint_freq=1,
        save_dir=str(tmp_path),
    )

    assert model.kwargs["n_steps"] == 128
    assert model.kwargs["batch_size"] == 128
    assert model.kwargs["n_epochs"] == 6
    assert model.kwargs["learning_rate"] == 1e-4
    assert model.kwargs["ent_coef"] == 0.02
    assert model.kwargs["target_kl"] == 0.03


def test_real_small_env_reset_step_smoke():
    np = pytest.importorskip("numpy")
    pytest.importorskip("gymnasium")

    from balatro_gym.environments.balatro_env_small import BalatroEnv

    env = BalatroEnv(seed=123)
    obs, info = env.reset()

    assert isinstance(info, dict)
    assert env.observation_space.contains(obs)

    first_action = int(np.flatnonzero(obs["action_mask"])[0])
    next_obs, reward, terminated, truncated, step_info = env.step(first_action)

    assert env.observation_space.contains(next_obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(step_info, dict)

    if not terminated and not truncated:
        second_action = int(np.flatnonzero(next_obs["action_mask"])[0])
        final_obs, final_reward, final_terminated, final_truncated, final_info = env.step(second_action)
        assert env.observation_space.contains(final_obs)
        assert isinstance(final_reward, float)
        assert isinstance(final_terminated, bool)
        assert isinstance(final_truncated, bool)
        assert isinstance(final_info, dict)


def test_real_trainer_module_import_smoke():
    pytest.importorskip("numpy")
    pytest.importorskip("gymnasium")
    pytest.importorskip("torch")
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("sb3_contrib")

    module = importlib.import_module("balatro_gym.training.train_balatro_agent")

    assert callable(module.train_balatro_agent)
    assert callable(module.BalatroFeaturesExtractor)
    assert callable(module.BalatroMetricsCallback)
    assert callable(module.MaskedMultiInputLstmPolicy)
    assert module.RecurrentPPO.__name__ == "RecurrentPPO"


def test_masked_policy_respects_action_mask():
    np = pytest.importorskip("numpy")
    torch = pytest.importorskip("torch")
    pytest.importorskip("gymnasium")
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("sb3_contrib")

    from sb3_contrib.common.recurrent.type_aliases import RNNStates

    from balatro_gym.environments.balatro_env_small import BalatroEnv
    from balatro_gym.training.train_balatro_agent import BalatroFeaturesExtractor, MaskedMultiInputLstmPolicy

    env = BalatroEnv(seed=123)
    obs, _ = env.reset()

    legal_action = int(np.flatnonzero(obs["action_mask"])[0])
    forced_mask = np.zeros_like(obs["action_mask"])
    forced_mask[legal_action] = 1
    obs["action_mask"] = forced_mask

    policy = MaskedMultiInputLstmPolicy(
        env.observation_space,
        env.action_space,
        lr_schedule=lambda _: 0.0,
        features_extractor_class=BalatroFeaturesExtractor,
        features_extractor_kwargs={"features_dim": 64},
        net_arch={"pi": [64], "vf": [64]},
        lstm_hidden_size=32,
    )

    obs_tensor = {
        key: torch.as_tensor(np.expand_dims(value, axis=0))
        for key, value in obs.items()
    }
    hidden_shape = policy.lstm_hidden_state_shape
    actor_state = (
        torch.zeros(hidden_shape, dtype=torch.float32),
        torch.zeros(hidden_shape, dtype=torch.float32),
    )
    critic_state = (
        torch.zeros(hidden_shape, dtype=torch.float32),
        torch.zeros(hidden_shape, dtype=torch.float32),
    )
    lstm_states = RNNStates(actor_state, critic_state)
    episode_starts = torch.ones((1,), dtype=torch.float32)

    with torch.no_grad():
        distribution, _ = policy.get_distribution(obs_tensor, actor_state, episode_starts)
        actions, _, log_prob, _ = policy(obs_tensor, lstm_states, episode_starts, deterministic=False)

    probs = distribution.distribution.probs.squeeze(0)
    assert int(actions.cpu().numpy().reshape(-1)[0]) == legal_action
    assert torch.isclose(probs.sum(), torch.tensor(1.0, dtype=probs.dtype))
    assert torch.isclose(probs[legal_action], torch.tensor(1.0, dtype=probs.dtype))
    assert torch.isfinite(log_prob).all()


def test_features_extractor_keeps_action_mask_out_of_learned_flat_features():
    pytest.importorskip("gymnasium")

    from balatro_gym.core_utils.mvp_contract import create_mvp_observation_space
    from balatro_gym.training.train_balatro_agent import BalatroFeaturesExtractor

    observation_space = create_mvp_observation_space()
    extractor = BalatroFeaturesExtractor(observation_space, features_dim=32)
    assert "action_mask" not in extractor.flat_keys
    assert "selected_cards" in extractor.flat_keys


def test_greedy_expert_prefers_direct_subset_play_action_when_available(monkeypatch):
    from balatro_gym.training import greedy_expert

    monkeypatch.setattr(greedy_expert, "_direct_play_block", lambda: (100, 218))

    obs = {
        "action_mask": np.zeros(400, dtype=np.int8),
    }
    direct_action = 100 + 9
    obs["action_mask"][direct_action] = 1
    obs["action_mask"][greedy_expert.Action.SELECT_CARD_BASE + 0] = 1
    obs["action_mask"][greedy_expert.Action.SELECT_CARD_BASE + 2] = 1
    obs["action_mask"][greedy_expert.Action.PLAY_HAND] = 1

    chosen_actions = greedy_expert.best_play_actions_for_combo(obs, (0, 2))

    assert chosen_actions == [direct_action]


def test_real_recurrent_ppo_training_smoke(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("gymnasium")
    pytest.importorskip("torch")
    pytest.importorskip("stable_baselines3")
    pytest.importorskip("sb3_contrib")

    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))

    module = importlib.import_module("balatro_gym.training.train_balatro_agent")

    _, save_path = module.train_balatro_agent(
        total_timesteps=8,
        n_envs=1,
        seed=123,
        checkpoint_freq=1_000,
        save_dir=str(tmp_path / "models"),
        hyperparams={
            "n_steps": 4,
            "batch_size": 4,
            "n_epochs": 1,
            "policy_kwargs": {
                "features_extractor_kwargs": {"features_dim": 64},
                "net_arch": {"pi": [64], "vf": [64]},
                "lstm_hidden_size": 64,
            },
        },
    )

    assert (save_path / "recurrent_ppo_final.zip").exists()
    assert (save_path / "vec_normalize.pkl").exists()
    assert (save_path / "config.json").exists()

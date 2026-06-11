from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable

from balatro_gym.core.constants import Action, Phase
from balatro_gym.core_utils.card_adapter import CardAdapter
from balatro_gym.environments.balatro_env_small import BalatroEnv


@dataclass
class GreedyExpertStep:
    observation: dict
    action: int


_DIRECT_PLAY_BASE_CANDIDATES = (
    "PLAY_SUBSET_BASE",
    "DIRECT_PLAY_BASE",
    "PLAY_COMBO_BASE",
    "PLAY_SELECTION_BASE",
)
_DIRECT_PLAY_COUNT_CANDIDATES = (
    "PLAY_SUBSET_COUNT",
    "DIRECT_PLAY_COUNT",
    "PLAY_COMBO_COUNT",
    "PLAY_SELECTION_COUNT",
)


def _copy_observation(obs: dict) -> dict:
    return {
        key: value.copy() if hasattr(value, "copy") else value
        for key, value in obs.items()
    }


def _legal_actions(obs: dict) -> list[int]:
    return [action for action, enabled in enumerate(obs["action_mask"]) if enabled]


def _legacy_play_sequence_for_combo(combo: tuple[int, ...]) -> list[int]:
    return [Action.SELECT_CARD_BASE + idx for idx in combo] + [Action.PLAY_HAND]


def _direct_play_block() -> tuple[int, int] | None:
    base = next((getattr(Action, name, None) for name in _DIRECT_PLAY_BASE_CANDIDATES if hasattr(Action, name)), None)
    count = next((getattr(Action, name, None) for name in _DIRECT_PLAY_COUNT_CANDIDATES if hasattr(Action, name)), None)
    if base is None or count is None:
        return None
    return int(base), int(count)


def _subset_action_combos(max_hand_size: int) -> Iterable[tuple[int, ...]]:
    capped_hand_size = min(max_hand_size, Action.SELECT_CARD_COUNT)
    max_cards_to_play = min(5, capped_hand_size)
    for count in range(1, max_cards_to_play + 1):
        yield from itertools.combinations(range(capped_hand_size), count)


def direct_play_action_for_combo(obs: dict, combo: tuple[int, ...]) -> int | None:
    block = _direct_play_block()
    if block is None:
        return None

    base, count = block
    combo_to_offset = {
        subset: offset
        for offset, subset in enumerate(_subset_action_combos(Action.SELECT_CARD_COUNT))
    }
    offset = combo_to_offset.get(tuple(combo))
    if offset is None or offset >= count:
        return None

    action = base + offset
    legal_actions = _legal_actions(obs)
    return action if action in legal_actions else None


def best_play_actions_for_combo(obs: dict, combo: tuple[int, ...]) -> list[int]:
    direct_action = direct_play_action_for_combo(obs, combo)
    if direct_action is not None:
        return [direct_action]
    return _legacy_play_sequence_for_combo(combo)


def best_play_sequence(env: BalatroEnv) -> list[int]:
    hand_len = min(len(env.state.hand_indexes), Action.SELECT_CARD_COUNT)
    best_choice: tuple[int, int, tuple[int, ...]] | None = None

    for count in range(1, min(5, hand_len) + 1):
        for combo in itertools.combinations(range(hand_len), count):
            selected_cards = []
            selected_game_cards = []

            for idx in combo:
                card_idx = env.state.hand_indexes[idx]
                card = env.state.deck[card_idx]
                selected_game_cards.append(card)
                selected_cards.append(CardAdapter.to_scoring_format(card, card_idx, env.state))

            hand_type, _ = env.game._classify_hand(selected_game_cards)
            hand_type_name = hand_type.name.replace("_", " ").title()

            if not env.play_handler._check_boss_blind_can_play(selected_game_cards, hand_type_name):
                continue

            score, _ = env.play_handler._score_hand(selected_cards, hand_type, hand_type_name)
            score = env.play_handler._apply_boss_blind_scoring(
                score,
                selected_game_cards,
                hand_type,
                hand_type_name,
            )

            candidate = (score, count, combo)
            if best_choice is None or candidate > best_choice:
                best_choice = candidate

    if best_choice is None:
        obs = env.obs_builder.build_observation(env.state)
        legal_actions = _legal_actions(obs)
        if Action.DISCARD in legal_actions:
            return [Action.DISCARD]
        card_actions = [
            action
            for action in legal_actions
            if Action.SELECT_CARD_BASE <= action < Action.SELECT_CARD_BASE + Action.SELECT_CARD_COUNT
        ]
        if card_actions:
            return [card_actions[0]]
        if legal_actions:
            return [legal_actions[0]]
        raise RuntimeError("Greedy expert found no legal action in play phase")

    _, _, combo = best_choice
    obs = env.obs_builder.build_observation(env.state)
    return best_play_actions_for_combo(obs, combo)


def default_phase_action(obs: dict) -> int:
    valid_actions = _legal_actions(obs)
    if not valid_actions:
        raise RuntimeError("Observation exposed no legal actions")

    blind_actions = [
        action
        for action in valid_actions
        if Action.SELECT_BLIND_BASE <= action < Action.SELECT_BLIND_BASE + Action.SELECT_BLIND_COUNT
    ]
    if blind_actions:
        return blind_actions[0]

    return valid_actions[0]


def collect_greedy_demonstrations(
    *,
    target_steps: int,
    seed: int,
    max_steps_per_episode: int = 128,
) -> tuple[list[GreedyExpertStep], dict[str, float]]:
    demonstrations: list[GreedyExpertStep] = []
    episodes = 0
    beat_blind_count = 0
    total_steps = 0

    while len(demonstrations) < target_steps:
        env = BalatroEnv(seed=seed + episodes)
        obs, _ = env.reset(seed=seed + episodes)
        done = False
        steps_run = 0
        beat_blind = False

        while not done and steps_run < max_steps_per_episode and len(demonstrations) < target_steps:
            phase = int(obs["phase"])
            if phase == Phase.PLAY:
                for action in best_play_sequence(env):
                    demonstrations.append(GreedyExpertStep(observation=_copy_observation(obs), action=int(action)))
                    obs, reward, terminated, truncated, info = env.step(action)
                    done = terminated or truncated
                    beat_blind = beat_blind or bool(info.get("beat_blind", False))
                    steps_run += 1
                    if done or int(obs["phase"]) != Phase.PLAY or len(demonstrations) >= target_steps:
                        break
            else:
                action = default_phase_action(obs)
                demonstrations.append(GreedyExpertStep(observation=_copy_observation(obs), action=int(action)))
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                beat_blind = beat_blind or bool(info.get("beat_blind", False))
                steps_run += 1

        episodes += 1
        total_steps += steps_run
        beat_blind_count += int(beat_blind)

    stats = {
        "episodes": float(episodes),
        "avg_steps": total_steps / max(1, episodes),
        "beat_blind_rate": beat_blind_count / max(1, episodes),
        "samples": float(len(demonstrations)),
    }
    return demonstrations, stats

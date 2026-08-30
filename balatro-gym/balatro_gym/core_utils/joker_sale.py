from __future__ import annotations

from typing import Any, Dict, Tuple

from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState


def sell_joker(
    state: UnifiedGameState,
    joker_idx: int,
    *,
    boss_blind_manager: BossBlindManager | None = None,
    game: Any | None = None,
    rng: DeterministicRNG | None = None,
) -> Tuple[Any, int, Dict[str, int | str]]:
    """Sell one joker and apply shared boss/joker side effects."""
    if joker_idx in state.eternal_jokers:
        raise ValueError("Cannot sell eternal jokers")
    invisible_ready = (
        0 <= joker_idx < len(state.jokers)
        and state.jokers[joker_idx].name == "Invisible Joker"
        and state.invisible_joker_rounds.get(joker_idx, 0) >= 2
    )

    sold_joker = state.remove_joker(joker_idx)
    if sold_joker is None:
        raise ValueError("Failed to remove joker")

    sell_value = _calculate_sell_value(sold_joker)
    state.money += sell_value
    state.jokers_sold += 1

    effects: Dict[str, int | str] = {}
    if (
        state.active_boss_blind == BossBlindType.THE_VERDANT
        and boss_blind_manager is not None
        and boss_blind_manager.active_blind is not None
    ):
        boss_blind_manager.disable_boss_blind(
            state,
            game,
            preserve_boss_round_identity=True,
        )

    if (
        sold_joker.name == "Luchador"
        and boss_blind_manager is not None
        and boss_blind_manager.active_blind is not None
    ):
        boss_blind_manager.disable_boss_blind(
            state,
            game,
            preserve_boss_round_identity=True,
        )
        effects["luchador_effect"] = "Boss blind disabled this round"
    elif sold_joker.name == "Swashbuckler":
        bonus = state.jokers_sold
        state.money += bonus
        effects["swashbuckler_bonus"] = bonus
    elif sold_joker.name == "Invisible Joker":
        duplicate = _duplicate_invisible_target(state, rng, ready=invisible_ready)
        if duplicate is not None:
            effects["invisible_duplicate"] = duplicate.name

    return sold_joker, sell_value, effects


def _calculate_sell_value(joker: Any) -> int:
    base_value = max(3, joker.base_cost // 2)
    special_sell_values = {
        "Egg": 5,
        "Gift Card": 0,
    }
    return special_sell_values.get(joker.name, base_value)


def _duplicate_invisible_target(
    state: UnifiedGameState,
    rng: DeterministicRNG | None,
    *,
    ready: bool,
):
    if not ready or not state.jokers:
        return None

    target_indexes = list(range(len(state.jokers)))
    target_idx = (
        rng.choice("joker_effects", target_indexes)
        if rng is not None
        else target_indexes[0]
    )
    target_joker = state.jokers[target_idx]
    if not state.add_joker(target_joker):
        return None

    dest_idx = len(state.jokers) - 1
    state.copy_joker_modifiers(target_idx, dest_idx, copy_negative=False)
    if target_joker.name == "Invisible Joker":
        state.invisible_joker_rounds[dest_idx] = 0
    else:
        state.invisible_joker_rounds.pop(dest_idx, None)
    return target_joker

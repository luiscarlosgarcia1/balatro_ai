from __future__ import annotations

from typing import Any, Dict, Tuple

from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType
from balatro_gym.core_utils.state import UnifiedGameState


def sell_joker(
    state: UnifiedGameState,
    joker_idx: int,
    *,
    boss_blind_manager: BossBlindManager | None = None,
    game: Any | None = None,
) -> Tuple[Any, int, Dict[str, int | str]]:
    """Sell one joker and apply shared boss/joker side effects."""
    if joker_idx in state.eternal_jokers:
        raise ValueError("Cannot sell eternal jokers")

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

    return sold_joker, sell_value, effects


def _calculate_sell_value(joker: Any) -> int:
    base_value = max(3, joker.base_cost // 2)
    special_sell_values = {
        "Egg": 5,
        "Gift Card": 0,
    }
    return special_sell_values.get(joker.name, base_value)

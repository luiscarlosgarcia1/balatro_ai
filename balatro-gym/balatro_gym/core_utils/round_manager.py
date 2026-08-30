"""Canonical round progression helpers for verified round-eval behavior.

The cashout rows implemented here are limited to behavior with direct parity
evidence from Balatro's round-evaluation flow in
``balatro_unpacked/functions/state_events.lua`` plus the boss-handling effects
used by this environment stack.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Literal

from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.boss_blinds import BOSS_BLINDS, BossBlindManager, BossBlindType, select_boss_blind
from balatro_gym.core.cards import Enhancement, EnhancementEffects, Rank, Seal, SealEffects
from balatro_gym.core.constants import Phase
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects

RoundOutcome = Literal["noop", "round_eval", "shop", "won", "game_over"]


def _legacy_select_boss_blind(
    ante: int,
    rng: DeterministicRNG | None,
    bosses_used: dict[BossBlindType, int],
) -> BossBlindType:
    """Preserve legacy monkeypatching against the subordinate unverified shim."""
    selector = select_boss_blind
    try:
        from balatro_gym.core_utils.unverified import round_manager as legacy_round_manager

        selector = getattr(legacy_round_manager, "select_boss_blind", select_boss_blind)
    except Exception:
        pass

    try:
        return selector(ante, rng=rng, bosses_used=bosses_used)
    except TypeError:
        return selector(ante, rng=rng)


class RoundManager:
    """Advance rounds and apply the verified round-eval/cashout subset."""

    def __init__(
        self,
        state: UnifiedGameState,
        game: BalatroGame,
        joker_effects_engine: CompleteJokerEffects,
        boss_blind_manager: BossBlindManager | None = None,
        rng: DeterministicRNG | None = None,
    ):
        self.state = state
        self.game = game
        self.joker_effects_engine = joker_effects_engine
        self.boss_blind_manager = boss_blind_manager
        self.rng = rng

    def advance_round(self) -> RoundOutcome:
        """Compatibility wrapper: enter round eval, then cash out."""
        outcome = self.enter_round_eval()
        if outcome == "round_eval":
            return self.cash_out()
        return outcome

    def enter_round_eval(self) -> RoundOutcome:
        """Apply end-of-round effects and expose the round evaluation phase."""
        blind_cleared = self.state.round_chips_scored >= self.state.chips_needed
        failed_blind = self.state.hands_left <= 0 and not blind_cleared

        completed_round = self.state.round
        completed_round_discards_used = self.state.discards_used_this_round
        cashout_disabled_joker_indexes = set(self.state.boss_disabled_joker_indexes)
        end_effects = self.joker_effects_engine.end_of_round_effects(self.state.to_dict())
        for effect in end_effects:
            joker_idx = effect.get("add_sell_value_to_joker_index")
            if joker_idx is not None:
                self.state.add_joker_sell_value_bonus(int(joker_idx), int(effect.get("sell_value_bonus", 0) or 0))
            if effect.get("add_sell_value_to_all_owned"):
                self.state.add_sell_value_bonus_to_all_owned(
                    int(effect.get("sell_value_bonus", 0) or 0)
                )
        mr_bones_saved = False
        if failed_blind and not any(effect.get("saved") for effect in end_effects):
            mr_bones_saved = self._try_save_with_mr_bones()
            if mr_bones_saved:
                end_effects.append({"saved": True, "saved_by": "Mr. Bones"})
        for effect in sorted(
            end_effects,
            key=lambda item: int(item.get("destroy_joker_index", -1)),
            reverse=True,
        ):
            joker_index = effect.get("destroy_joker_index")
            if joker_index is not None:
                self.state.remove_joker(int(joker_index))
                continue

            joker_name = effect.get("destroy_joker")
            if joker_name:
                for idx in range(len(self.state.jokers) - 1, -1, -1):
                    if self.state.jokers[idx].name == joker_name:
                        self.state.remove_joker(idx)
                        break

        boss_round_type = self.state.active_boss_blind

        if failed_blind and not any(effect.get("saved") for effect in end_effects):
            if boss_round_type is not None:
                self._disable_active_boss_blind(
                    restore_round_resources=boss_round_type == BossBlindType.THE_MANACLE
                )
            return self.game_over()

        gold_money = 0
        held_card_indexes = self.state.last_held_card_indexes
        if held_card_indexes is not None:
            for idx in held_card_indexes:
                card_state = self.state.card_states.get(idx)
                enhancement = self._enum_value(
                    card_state.enhancement if card_state else Enhancement.NONE,
                    Enhancement,
                )
                if enhancement == Enhancement.GOLD:
                    gold_money += EnhancementEffects.get_gold_value(enhancement)
        self.state.money += gold_money
        self._create_planets_from_held_blue_seals()

        cleared_boss_blind = False
        if boss_round_type is not None:
            cleared_boss_blind = blind_cleared
            boss_reward = BOSS_BLINDS[boss_round_type].money_reward if blind_cleared else 0
            self._disable_active_boss_blind(
                restore_round_resources=boss_round_type == BossBlindType.THE_MANACLE
            )
        else:
            boss_reward = 0

        self.state.game_over = False
        self.state.won = self.state.won or (
            int(self.state.ante) == int(self.state.win_ante)
            and cleared_boss_blind
        )

        self.state.round_chips_scored = 0
        self.state.best_hand_this_ante = 0
        self.state.hands_played_ante = 0
        self.state.selected_cards = []
        self.state.face_down_cards = []

        if self.state.round == 3:
            self.state.ante += 1
            self.state.round = 1
            self.state.reset_ante_state()
        else:
            self.state.round += 1
            self.state.reset_round_state()
            if self.state.round == 3:
                self.state.pending_boss_blind = _legacy_select_boss_blind(
                    self.state.ante,
                    self.rng,
                    self.state.bosses_used,
                )

        self.state.round_eval_cashout = self._cashout_amount(
            blind_cleared,
            completed_round,
            boss_reward,
            completed_round_discards_used,
            cashout_disabled_joker_indexes,
        )
        self.state.round_eval_completed_round = completed_round
        if completed_round == 3:
            self.state.increase_rocket_payouts()
        self.state.phase = Phase.ROUND_EVAL

        if hasattr(self.game, "blind_index"):
            self.game.blind_index = max(0, min(2, int(self.state.round) - 1))
        return "round_eval"

    def cash_out(self) -> RoundOutcome:
        """Pay the staged round evaluation dollars and enter the shop."""
        if self.state.phase != Phase.ROUND_EVAL:
            return "noop"

        self.state.money += self.state.round_eval_cashout
        self.state.round_eval_cashout = 0
        self.state.round_eval_completed_round = None
        self.state.round_chips_scored = 0
        self.state.hands_left = self._base_round_hands()
        self.state.discards_left = self._base_round_discards()
        self.state.selected_cards = []
        self.state.phase = Phase.SHOP

        self.game.round_hands = self.state.hands_left
        self.game.round_discards = self.state.discards_left
        return "won" if self.state.won else "shop"

    def game_over(self) -> RoundOutcome:
        """Enter the terminal game-over phase after a failed blind."""
        self.state.game_over = True
        self.state.phase = Phase.GAME_OVER
        self.state.selected_cards = []
        return "game_over"

    def _disable_active_boss_blind(self, *, restore_round_resources: bool = False) -> None:
        """Use shared boss cleanup when available, otherwise fall back to legacy reset."""
        if not self.boss_blind_manager:
            return

        disable = getattr(self.boss_blind_manager, "disable_boss_blind", None)
        if callable(disable):
            disable(
                self.state,
                self.game,
                restore_round_resources=restore_round_resources,
                draw_restored_manacle_card=False,
                restore_chip_thresholds=False,
            )
            return

        deactivate = getattr(self.boss_blind_manager, "deactivate", None)
        if callable(deactivate):
            deactivate()

        self.state.active_boss_blind = None
        self.state.boss_blind_active = False
        self.state.face_down_cards = []
        self.state.boss_disabled_joker_indexes = []
        self.state.hidden_joker_indexes = []
        self.state.boss_forced_selected_card = None
        self.state.disabled_joker_slots = 0

    def _try_save_with_mr_bones(self) -> bool:
        """Consume an active Mr. Bones when the failed blind met the save threshold."""
        chips_needed = int(self.state.chips_needed or 0)
        if chips_needed <= 0:
            return False
        if self.state.round_chips_scored / chips_needed < 0.25:
            return False

        for joker_index in range(len(self.state.jokers) - 1, -1, -1):
            if joker_index in self.state.boss_disabled_joker_indexes:
                continue
            joker = self.state.jokers[joker_index]
            if joker.name != "Mr. Bones":
                continue
            removed = self.state.remove_joker(joker_index)
            return removed is not None
        return False

    def _base_round_hands(self) -> int:
        """Return the persistent hands-per-round baseline after voucher effects."""
        bonus = 0
        for voucher_name in self.state.vouchers:
            if voucher_name in {"Grabber", "Nacho Tong"}:
                bonus += 1
        passive_bonus = self.state._passive_joker_bonuses()[1]
        return max(0, 4 + bonus + passive_bonus)

    def _base_round_discards(self) -> int:
        """Return the persistent discards-per-round baseline after voucher effects."""
        bonus = 0
        for voucher_name in self.state.vouchers:
            if voucher_name in {"Wasteful", "Recyclomancy"}:
                bonus += 1
        passive_bonus = self.state._passive_joker_bonuses()[2]
        return max(0, 3 + bonus + passive_bonus)

    @staticmethod
    def _enum_value(value: IntEnum | str, enum_type: type[IntEnum]) -> IntEnum:
        if isinstance(value, enum_type):
            return value
        if isinstance(value, IntEnum):
            return enum_type.__members__.get(value.name, enum_type.NONE)
        if isinstance(value, str):
            key = value.strip().replace(" ", "_").replace("-", "_").upper()
            return enum_type.__members__.get(key, enum_type.NONE)
        return enum_type.NONE

    def _create_planets_from_held_blue_seals(self) -> None:
        """Create last-hand planet cards from blue-sealed cards held at round end."""
        if not self.state.last_hand_played:
            return

        held_card_indexes = self.state.last_held_card_indexes
        if held_card_indexes is None:
            return

        for idx in held_card_indexes:
            if self.state.active_consumable_count() >= self.state.consumable_slots:
                return
            card_state = self.state.card_states.get(idx)
            seal = self._enum_value(card_state.seal if card_state else Seal.NONE, Seal)
            if seal != Seal.BLUE:
                continue
            planet = SealEffects.get_planet_created(seal, self.state.last_hand_played)
            if planet:
                self.state.add_consumable(planet)

    def _cashout_amount(
        self,
        blind_cleared: bool,
        completed_round: int,
        boss_reward: int,
        completed_round_discards_used: int,
        disabled_joker_indexes: set[int] | None = None,
    ) -> int:
        """Return the verified round-eval cashout amount."""
        return (
            self._blind_reward(blind_cleared, completed_round, boss_reward)
            + self._remaining_hand_payout()
            + self._remaining_discard_payout()
            + self._joker_dollar_rows(completed_round_discards_used, disabled_joker_indexes)
            + self._interest_payout(disabled_joker_indexes)
        )

    def _blind_reward(self, blind_cleared: bool, completed_round: int, boss_reward: int) -> int:
        """Return the fixed blind reward row from round evaluation."""
        if not blind_cleared:
            return 0
        if completed_round == 1:
            return 3
        if completed_round == 2:
            return 4
        return boss_reward or 5

    def _interest_payout(self, disabled_joker_indexes: set[int] | None = None) -> int:
        """Return interest based on current money and supported modifiers."""
        if self.state.money < 5 or getattr(self.state, "no_interest", False):
            return 0

        disabled = (
            disabled_joker_indexes
            if disabled_joker_indexes is not None
            else set(self.state.boss_disabled_joker_indexes)
        )
        interest_amount = 1 + sum(
            1
            for joker_idx, joker in enumerate(self.state.jokers)
            if joker.name == "To the Moon" and joker_idx not in disabled
        )
        interest_cap_units = self._interest_cap_dollars() // 5
        return interest_amount * min(self.state.money // 5, interest_cap_units)

    def _remaining_hand_payout(self) -> int:
        """Return remaining-hands cashout unless a modifier disables it."""
        if self.state.no_extra_hand_money or self.state.hands_left <= 0:
            return 0
        return self.state.hands_left * (self.state.money_per_hand or 1)

    def _remaining_discard_payout(self) -> int:
        """Return discard cashout only when a modifier enables it."""
        if self.state.money_per_discard is None or self.state.discards_left <= 0:
            return 0
        return self.state.discards_left * self.state.money_per_discard

    def _joker_dollar_rows(
        self,
        completed_round_discards_used: int,
        disabled_joker_indexes: set[int] | None = None,
    ) -> int:
        """Return supported Joker dollar rows from round evaluation."""
        disabled = (
            disabled_joker_indexes
            if disabled_joker_indexes is not None
            else set(self.state.boss_disabled_joker_indexes)
        )
        total = 0
        for joker_idx, joker in enumerate(self.state.jokers):
            if joker_idx in disabled:
                continue
            total += self._joker_dollar_bonus(joker_idx, joker.name, completed_round_discards_used)
        return total

    def _joker_dollar_bonus(self, joker_idx: int, joker_name: str, completed_round_discards_used: int) -> int:
        """Return a source-backed round-end dollar bonus for one Joker."""
        if joker_name == "Golden Joker":
            return 4
        if joker_name == "Cloud 9":
            return sum(1 for card in self.state.deck if card.rank == Rank.NINE)
        if joker_name == "Rocket":
            return self.state.get_rocket_payout(joker_idx)
        if joker_name == "Satellite":
            return len(self.state.unique_planet_cards_used)
        if joker_name in {"Delayed Grat.", "Delayed Gratification"}:
            if completed_round_discards_used == 0 and self.state.discards_left > 0:
                return self.state.discards_left * 2
        return 0

    def _interest_cap_dollars(self) -> int:
        """Return the dollar threshold cap used for end-of-round interest."""
        if "Money Tree" in self.state.vouchers:
            return 100
        if "Seed Money" in self.state.vouchers:
            return 50
        return 25


__all__ = ["RoundManager", "RoundOutcome", "select_boss_blind"]

"""Round progression helpers for the refactored environment stack."""

from __future__ import annotations

from balatro_gym.core.boss_blinds import select_boss_blind
from balatro_gym.core.boss_blinds import BossBlindManager
from balatro_gym.core.cards import Enhancement, EnhancementEffects, Rank
from balatro_gym.core.constants import Phase
from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects


class RoundManager:
    """Advance rounds and apply end-of-round state transitions."""

    def __init__(
        self,
        state: UnifiedGameState,
        game: BalatroGame,
        joker_effects_engine: CompleteJokerEffects,
        boss_blind_manager: BossBlindManager | None = None,
    ):
        self.state = state
        self.game = game
        self.joker_effects_engine = joker_effects_engine
        self.boss_blind_manager = boss_blind_manager

    def advance_round(self) -> None:
        """Apply end-of-round effects and move to the next blind/shop."""
        completed_round = self.state.round
        completed_round_discards_used = self.state.discards_used_this_round
        end_effects = self.joker_effects_engine.end_of_round_effects(self.state.to_dict())
        for effect in end_effects:
            joker_name = effect.get("destroy_joker")
            if joker_name:
                self.state.jokers = [j for j in self.state.jokers if j.name != joker_name]

        gold_money = 0
        for idx in self.state.hand_indexes:
            card_state = self.state.card_states.get(idx)
            if card_state and card_state.enhancement == Enhancement.GOLD:
                gold_money += EnhancementEffects.get_gold_value(card_state.enhancement)
        self.state.money += gold_money

        if self.state.boss_blind_active and self.boss_blind_manager and self.boss_blind_manager.active_blind:
            boss_reward = self.boss_blind_manager.active_blind.money_reward
            self.boss_blind_manager.deactivate()
            self.state.active_boss_blind = None
            self.state.boss_blind_active = False
            self.state.face_down_cards = []
        else:
            boss_reward = 0

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
                self.state.pending_boss_blind = select_boss_blind(self.state.ante)

        self.state.money += self._cashout_amount(completed_round, boss_reward, completed_round_discards_used)
        if completed_round == 3:
            self.state.increase_rocket_payouts()
        self.state.hands_left = self._base_round_hands()
        self.state.discards_left = self._base_round_discards()
        self.state.phase = Phase.SHOP

        self.game.round_hands = self.state.hands_left
        self.game.round_discards = self.state.discards_left

    def _base_round_hands(self) -> int:
        """Return the persistent hands-per-round baseline after voucher effects."""
        bonus = 0
        for voucher_name in self.state.vouchers:
            if voucher_name in {"Grabber", "Nacho Tong"}:
                bonus += 1
        return 4 + bonus

    def _base_round_discards(self) -> int:
        """Return the persistent discards-per-round baseline after voucher effects."""
        bonus = 0
        for voucher_name in self.state.vouchers:
            if voucher_name in {"Wasteful", "Recyclomancy"}:
                bonus += 1
        return 3 + bonus

    def _cashout_amount(self, completed_round: int, boss_reward: int, completed_round_discards_used: int) -> int:
        """Return round-eval cashout dollars for the cleared blind."""
        return (
            self._blind_reward(completed_round, boss_reward)
            + self._remaining_hand_payout()
            + self._remaining_discard_payout()
            + self._joker_dollar_rows(completed_round_discards_used)
            + self._interest_payout()
        )

    def _blind_reward(self, completed_round: int, boss_reward: int) -> int:
        """Return the fixed reward for the cleared blind."""
        if completed_round == 1:
            return 3
        if completed_round == 2:
            return 4
        return boss_reward or 5

    def _interest_payout(self) -> int:
        """Return interest based on current money and economy modifiers."""
        interest_units = self.state.money // 5
        interest_cap = self._interest_cap()
        base_interest = min(interest_units, interest_cap)
        to_the_moon_count = sum(1 for joker in self.state.jokers if joker.name == "To the Moon")
        return base_interest * (1 + to_the_moon_count)

    def _remaining_hand_payout(self) -> int:
        """Return the default $1-per-hand cashout row."""
        return self.state.hands_left

    def _remaining_discard_payout(self) -> int:
        """Return discard cashout only when a modifier enables it."""
        if self.state.money_per_discard is None or self.state.discards_left <= 0:
            return 0
        return self.state.discards_left * self.state.money_per_discard

    def _joker_dollar_rows(self, completed_round_discards_used: int) -> int:
        """Return round-end joker dollar rows that materially affect economy."""
        total = 0
        for joker_idx, joker in enumerate(self.state.jokers):
            total += self._joker_dollar_bonus(joker_idx, joker.name, completed_round_discards_used)
        return total

    def _joker_dollar_bonus(self, joker_idx: int, joker_name: str, completed_round_discards_used: int) -> int:
        """Return a supported end-of-round dollar bonus for one joker."""
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

    def _interest_cap(self) -> int:
        """Return the per-round interest cap after voucher upgrades."""
        if "Money Tree" in self.state.vouchers:
            return 20
        if "Seed Money" in self.state.vouchers:
            return 10
        return 5

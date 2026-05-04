"""Round progression helpers for the refactored environment stack."""

from __future__ import annotations

from balatro_gym.core.boss_blinds import BossBlindManager
from balatro_gym.core.cards import Enhancement, EnhancementEffects
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
            self.state.money += self.boss_blind_manager.active_blind.money_reward
            self.boss_blind_manager.deactivate()
            self.state.active_boss_blind = None
            self.state.boss_blind_active = False
            self.state.face_down_cards = []

        self.state.round_chips_scored = 0
        self.state.best_hand_this_ante = 0
        self.state.hands_played_ante = 0
        self.state.selected_cards = []

        if self.state.round == 3:
            self.state.ante += 1
            self.state.round = 1
            self.state.reset_ante_state()
        else:
            self.state.round += 1
            self.state.reset_round_state()

        self.state.money += 25 * self.state.round + (10 if self.state.round == 3 else 0)
        self.state.hands_left = 4
        self.state.discards_left = 3
        self.state.phase = Phase.SHOP

        self.game.round_hands = self.state.hands_left
        self.game.round_discards = self.state.discards_left

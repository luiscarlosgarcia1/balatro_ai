"""Reward shaping helpers used by the small integrated environment."""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from balatro_gym.scoring.scoring_engine import HandType


class RewardCalculator:
    """Compute a structured reward breakdown for played hands."""

    def calculate_play_reward(
        self,
        *,
        old_score: int,
        new_score: int,
        chips_needed: int,
        final_score: int,
        hand_type: HandType,
        cards_played: int,
        ante: int,
        hands_left: int,
        joker_names: List[str],
        selected_game_cards: List[object],
    ) -> Dict[str, float]:
        old_progress = min(1.0, old_score / max(1, chips_needed))
        new_progress = min(1.0, new_score / max(1, chips_needed))

        progress_reward = 15.0 * new_progress

        milestone_reward = 0.0
        if old_progress < 0.25 <= new_progress:
            milestone_reward = 5.0
        elif old_progress < 0.5 <= new_progress:
            milestone_reward = 10.0
        elif old_progress < 0.75 <= new_progress:
            milestone_reward = 15.0
        elif old_progress < 1.0 <= new_progress:
            milestone_reward = 25.0

        if ante <= 3:
            score_reward = min(10.0, final_score / 100.0)
        else:
            score_reward = min(10.0, 3.0 * np.log10(max(1, final_score)))

        hand_quality_values = {
            HandType.HIGH_CARD: 0.1,
            HandType.ONE_PAIR: 0.5,
            HandType.TWO_PAIR: 1.0,
            HandType.THREE_KIND: 2.0,
            HandType.STRAIGHT: 2.5,
            HandType.FLUSH: 2.5,
            HandType.FULL_HOUSE: 3.5,
            HandType.FOUR_KIND: 5.0,
            HandType.STRAIGHT_FLUSH: 7.0,
            HandType.FIVE_KIND: 10.0,
        }
        hand_quality_reward = hand_quality_values.get(hand_type, 0.0)

        efficiency_reward = 0.0
        if hand_type >= HandType.THREE_KIND and cards_played <= 3:
            efficiency_reward = 2.0
        elif hand_type >= HandType.FLUSH and cards_played == 5:
            efficiency_reward = 1.0
        elif cards_played <= 4 and hands_left <= 2:
            efficiency_reward = 1.5

        synergy_reward = 0.0
        if hand_type == HandType.FLUSH and any(
            name in ["Smeared Joker", "Four Fingers", "Shortcut"]
            for name in joker_names
        ):
            synergy_reward += 2.0

        if hand_type in [HandType.ONE_PAIR, HandType.TWO_PAIR, HandType.THREE_KIND]:
            if any(
                name in ["Odd Todd", "Even Steven", "Jolly Joker", "Zany Joker"]
                for name in joker_names
            ):
                synergy_reward += 1.5

        face_cards = sum(
            1 for card in selected_game_cards if getattr(card.rank, "value", 0) >= 11
        )
        if face_cards > 0 and any(
            name in ["Scary Face", "Smiley Face", "Business Card"]
            for name in joker_names
        ):
            synergy_reward += 0.5 * face_cards

        strategy_reward = 0.0
        if new_progress > 0.7 and hands_left >= 3:
            strategy_reward = 2.0
        elif new_progress < 0.3 and hand_type >= HandType.FLUSH:
            strategy_reward = 3.0

        ante_bonus = min(5.0, (ante - 3) * 0.5) if ante >= 4 else 0.0

        total_reward = (
            progress_reward
            + milestone_reward
            + score_reward
            + hand_quality_reward * 2.0
            + efficiency_reward * 1.5
            + synergy_reward * 3.0
            + strategy_reward * 2.0
            + ante_bonus
        )

        return {
            "progress": progress_reward,
            "milestone": milestone_reward,
            "score": score_reward,
            "hand_quality": hand_quality_reward,
            "efficiency": efficiency_reward,
            "synergy": synergy_reward,
            "strategy": strategy_reward,
            "ante_bonus": ante_bonus,
            "total_reward": min(total_reward, 100.0),
        }
